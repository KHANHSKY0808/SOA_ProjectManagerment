from datetime import timedelta
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from django.db import OperationalError, connection
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from . import clients, services
from .enrichment import topic_response
from types import SimpleNamespace
from .models import Topic

CLIENT_CONFIG = {"DISCOVERY_ENABLED": False, "BASE_URL": "http://academic.test:8002",
                 "TIMEOUT_SECONDS": 2, "FAILURE_THRESHOLD": 3, "COOLDOWN_SECONDS": 10}
REFERENCE = [("major_id", "majors", "major_id", "1")]


class TopicPersistenceTests(TransactionTestCase):
    # All fixtures, including foreign-owner tables, exist ONLY in Django's disposable DB.
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with connection.cursor() as cursor:
            cursor.execute('CREATE TABLE Users (UserId TEXT PRIMARY KEY)')
            cursor.execute('CREATE TABLE Majors (MajorId TEXT PRIMARY KEY)')
            cursor.execute('CREATE TABLE Lecturers (LecturerId TEXT PRIMARY KEY)')
            cursor.execute('CREATE TABLE Topics (\n                TopicId TEXT PRIMARY KEY NOT NULL, TopicName TEXT NOT NULL,\n                Description TEXT, FileUrl TEXT, MajorId TEXT NOT NULL REFERENCES Majors(MajorId),\n                req_GPA REAL NOT NULL DEFAULT 0, studentQuota INTEGER NOT NULL DEFAULT 1, Status INTEGER, AdvisorId TEXT REFERENCES Lecturers(LecturerId),\n                CreatedAt TEXT, UpdatedAt TEXT, UpdatedBy TEXT REFERENCES Users(UserId))')
            cursor.execute('CREATE TABLE Registrations (RegistrationId TEXT PRIMARY KEY, TopicId TEXT REFERENCES Topics(TopicId))')

    @classmethod
    def tearDownClass(cls):
        with connection.cursor() as cursor:
            for table in ("Registrations", "Topics", "Lecturers", "Majors", "Users"):
                cursor.execute(f'DROP TABLE "{table}"')
        super().tearDownClass()

    def setUp(self):
        self.client = APIClient()
        self.authenticate(1)
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO Users VALUES ('admin')")
            cursor.execute("INSERT INTO Majors VALUES ('1')")
            cursor.execute("INSERT INTO Lecturers VALUES ('GV001')")
        self.data = {"topic_id": "DT001", "name": "SOA project", "major_id": "1", "advisor_id": "GV001"}
        self.names_patch = patch.object(clients.academic_names_client, "display_names", return_value={
            "major_names": {"1": "Information Technology"}, "advisor_names": {"GV001": "Nguyen An"}})
        self.names = self.names_patch.start()
        self.addCleanup(self.names_patch.stop)
        self.validation = patch.object(services.academic_client, "validate")
        self.academic = self.validation.start()
        cleanup = patch.object(services.registration_cleanup_client, "purge", return_value=0)
        self.cleanup = cleanup.start()
        self.addCleanup(cleanup.stop)
        self.network = patch.object(clients, "fetch_json", side_effect=AssertionError("Live network forbidden"))
        self.network.start()

    def tearDown(self):
        self.validation.stop()
        self.network.stop()
        with connection.cursor() as cursor:
            for table in ("Registrations", "Topics", "Lecturers", "Majors", "Users"):
                cursor.execute(f'DELETE FROM "{table}"')
        super().tearDown()

    def authenticate(self, role, identity="admin"):
        token = AccessToken()
        token["user_id"] = identity
        token["role"] = role
        self.token = str(token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def request(self, method, path, data=None):
        return getattr(self.client, method)(path, data=data, format="json")

    def create(self, prefix="/api/"):
        response = self.client.post(prefix + "topics/", self.data, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return response

    def test_complete_crud_both_routes(self):
        for prefix in ("/api/", "/api/v1/"):
            with self.subTest(prefix=prefix):
                collection = prefix + "topics/"
                detail = collection + "DT001/"
                created = self.create(prefix)
                self.assertEqual(created.data["updated_by"], "admin")
                self.assertEqual(created.data["major_name"], "Information Technology")
                self.assertEqual(created.data["avisor_name"], "Nguyen An")
                self.assertNotIn("major_id", created.data)
                self.assertNotIn("advisor_id", created.data)
                self.assertTrue(created.data["created_at"].endswith("Z"))
                self.assertFalse(Topic._meta.managed)
                listed = self.client.get(collection).data[0]
                self.assertEqual(listed["topic_id"], "DT001")
                self.assertEqual(listed["major_name"], "Information Technology")
                self.assertEqual(listed["avisor_name"], "Nguyen An")
                detailed = self.client.get(detail).data
                self.assertEqual(detailed["name"], self.data["name"])
                self.assertEqual(detailed["avisor_name"], "Nguyen An")
                patched = self.request("patch", detail, {"description": "new"})
                self.assertEqual(patched.status_code, 200)
                self.assertEqual(patched.data["major_name"], "Information Technology")
                replacement = {**self.data, "name": "Replacement"}
                replacement.pop("advisor_id")
                result = self.request("put", detail, replacement)
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.data["created_at"], created.data["created_at"])
                self.assertIsNone(result.data["description"])
                self.assertIsNone(result.data["avisor_name"])
                self.assertEqual(Topic.objects.get().name, "Replacement")
                deleted = self.client.delete(detail)
                self.assertEqual(deleted.status_code, 204)
                self.assertEqual(deleted.content, b"")
                self.assertFalse(Topic.objects.exists())

    def test_display_failure_after_write_returns_success_with_null_names(self):
        self.names.side_effect = clients.DependencyUnavailable()
        response = self.create()
        self.assertIsNone(response.data["major_name"])
        self.assertIsNone(response.data["avisor_name"])
        self.assertTrue(Topic.objects.exists())
        self.assertEqual(self.client.get("/api/topics/").status_code, 200)
        self.assertEqual(self.request("patch", "/api/topics/DT001/", {"name": "New"}).status_code, 200)
        self.assertEqual(Topic.objects.get().name, "New")

    def test_invalid_input_and_server_fields(self):
        for payload in ({}, {**self.data, "name": " "}, {**self.data, "major_id": None},
                        {**self.data, "status": "bad"}, {**self.data, "updated_by": "attacker"},
                        {**self.data, "major_name": "Fake"}, {**self.data, "avisor_name": "Fake"},
                        {**self.data, "created_at": "2020-01-01"}, {**self.data, "other": True}):
            with self.subTest(payload=payload):
                self.assertEqual(self.request("post", "/api/topics/", payload).status_code, 400)
        self.academic.assert_not_called()
        self.assertFalse(Topic.objects.exists())

    def test_requirement_defaults_updates_validation_and_permissions(self):
        created = self.create()
        self.assertEqual((created.data["req_GPA"], created.data["studentQuota"]), (0, 1))
        url = "/api/v1/topics/DT001/"
        result = self.request("patch", url, {"req_GPA": 3.25, "studentQuota": 4})
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual((result.data["req_GPA"], result.data["studentQuota"]), (3.25, 4))
        self.request("patch", url, {"name": "Retain limits"})
        obj = Topic.objects.get()
        self.assertEqual((obj.req_GPA, obj.studentQuota), (3.25, 4))
        self.assertEqual(Topic._meta.get_field("req_GPA").db_column, "req_GPA")
        self.assertEqual(Topic._meta.get_field("studentQuota").db_column, "studentQuota")
        for field, values in (("req_GPA", [-1, 4.01, None, True, "3"]),
                              ("studentQuota", [0, -1, 1.5, 2147483648, 10**100, None, True, "2"])):
            for value in values:
                with self.subTest(field=field, value=value):
                    self.assertEqual(self.request("patch", url, {field: value}).status_code, 400)
        from .serializers import TopicRequestDTO
        for value in (float("inf"), float("nan")):
            self.assertFalse(TopicRequestDTO(data={"req_GPA": value}, partial=True).is_valid())
        for role in (2, 3):
            self.authenticate(role)
            self.assertEqual(self.request("patch", url, {"studentQuota": 10}).status_code, 403)

    def test_duplicate_and_immutable_id(self):
        self.create()
        self.assertEqual(self.request("post", "/api/topics/", self.data).status_code, 409)
        self.assertEqual(self.request("patch", "/api/topics/DT001/", {"topic_id": "changed"}).status_code, 400)
        self.assertEqual(list(Topic.objects.values_list("topic_id", flat=True)), ["DT001"])

    def test_required_put_fields_and_patch_nullable(self):
        self.create()
        self.assertEqual(self.request("put", "/api/topics/DT001/", {"name": "x"}).status_code, 400)
        response = self.request("patch", "/api/topics/DT001/", {"advisor_id": ""})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(Topic.objects.get().advisor_id)

    def test_status_defaults_permissions_and_updates(self):
        for prefix in ("/api/", "/api/v1/"):
            collection = prefix + "topics/"
            detail = collection + "DT001/"
            for role, initial in ((1, 1),):
                self.authenticate(role)
                self.assertEqual(self.create(prefix).data["status"], initial)
                for method, payload in (("put", self.data), ("patch", {"name": "Revision"})):
                    self.assertEqual(self.request(method, detail, payload).status_code, 200)
                    self.assertEqual(Topic.objects.get().status, initial)
                Topic.objects.all().delete()
            for status in (0, 1, 2, 3):
                self.authenticate(3)
                self.assertEqual(self.request("post", collection, {**self.data, "status": status}).status_code, 403)
                self.assertFalse(Topic.objects.exists())
                self.authenticate(1)
                self.assertEqual(self.request("post", collection, {**self.data, "status": status}).data["status"], status)
                self.authenticate(2)
                for method, payload in (("patch", {"status": status}), ("put", {**self.data, "status": status})):
                    self.assertEqual(self.request(method, detail, payload).status_code, 403)
                    self.assertEqual(Topic.objects.get().status, status)
                self.authenticate(1)
                for next_status in (0, 1, 2, 3):
                    for method, payload in (("patch", {"status": next_status}), ("put", {**self.data, "status": next_status})):
                        self.assertEqual(self.request(method, detail, payload).status_code, 200)
                        self.assertEqual(Topic.objects.get().status, next_status)
                Topic.objects.all().delete()

    def test_status_rejects_invalid_values_without_writes(self):
        for status in (None, -1, 4, True, False, "1", 1.5):
            self.assertEqual(self.request("post", "/api/topics/", {**self.data, "status": status}).status_code, 400)
            self.assertFalse(Topic.objects.exists())
        self.create()
        for status in (None, -1, 4, True, "1", 1.5):
            for method, payload in (("patch", {"status": status}), ("put", {**self.data, "status": status})):
                self.assertEqual(self.request(method, "/api/topics/DT001/", payload).status_code, 400)
                self.assertEqual(Topic.objects.get().status, 1)

    def test_authentication_and_roles(self):
        self.create()
        for role in (3, 0, 4, "1", "2", True, None):
            self.authenticate(role)
            self.assertEqual(self.client.get("/api/topics/").status_code, 200)
            for prefix in ("/api/", "/api/v1/"):
                collection = prefix + "topics/"
                for method, path, payload in [("post", collection, self.data),
                                              ("put", collection + "DT001/", self.data),
                                              ("patch", collection + "DT001/", {}),
                                              ("delete", collection + "DT001/", None)]:
                    self.assertEqual(self.request(method, path, payload).status_code, 403)
                detail = self.client.get(collection + "DT001/").data
                self.assertNotIn("major_id", detail)
                self.assertNotIn("advisor_id", detail)
        self.assertEqual(Topic.objects.get().name, self.data["name"])
        expired = AccessToken()
        expired["user_id"] = "admin"
        expired.set_exp(lifetime=timedelta(seconds=-1))
        for bearer in (None, "invalid", str(expired)):
            self.client.credentials(**({"HTTP_AUTHORIZATION": f"Bearer {bearer}"} if bearer else {}))
            for method, path in [("get", "/api/topics/"), ("post", "/api/topics/"),
                                 ("get", "/api/topics/DT001/"), ("put", "/api/topics/DT001/"),
                                 ("patch", "/api/topics/DT001/"), ("delete", "/api/topics/DT001/")]:
                self.assertEqual(self.request(method, path, self.data).status_code, 401)
        self.assertEqual(self.client.get("/health/").status_code, 200)

    def test_lecturer_reads_only_assigned_topics_and_cannot_mutate_both_aliases(self):
        self.create()
        Topic.objects.create(topic_id="OTHER", name="Other advisor", major_id="1")
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO Lecturers VALUES ('GV002')")
        Topic.objects.create(topic_id="ASSIGNED-OTHER", name="Assigned elsewhere", major_id="1", advisor_id="GV002")
        for prefix in ("/api/", "/api/v1/"):
            collection = prefix + "topics/"
            self.authenticate(2, "GV001")
            self.assertEqual([row["topic_id"] for row in self.client.get(collection).data], ["DT001"])
            detail = self.client.get(collection + "DT001/")
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(detail.data["advisor_id"], "GV001")
            self.assertEqual(detail.data["major_id"], "1")
            self.assertEqual(self.client.get(collection + "OTHER/").status_code, 404)
            self.assertEqual(self.client.get(collection + "ASSIGNED-OTHER/").status_code, 404)
            for method, url, payload in (
                ("put", collection + "DT001/", self.data),
                ("patch", collection + "DT001/", {"name": "Forbidden"}),
                ("delete", collection + "DT001/", None),
                ("delete", collection + "OTHER/", None)):
                self.assertEqual(self.request(method, url, payload).status_code, 403)
            self.authenticate(2, "OTHER-LECTURER")
            self.assertEqual(self.client.get(collection).data, [])
            self.assertEqual(self.client.get(collection + "DT001/").status_code, 404)
            self.assertEqual(self.client.get(collection + "OTHER/").status_code, 404)
            # A caller cannot override authenticated ownership using query parameters.
            self.assertEqual(self.client.get(collection + "?advisor_id=GV001").data, [])
            self.authenticate(1)
            self.assertEqual(len(self.client.get(collection).data), 3)
        self.assertEqual(Topic.objects.get(pk="DT001").name, self.data["name"])
        self.assertEqual(Topic.objects.get(pk="DT001").status, 1)
        self.assertEqual(Topic.objects.count(), 3)
        self.cleanup.assert_not_called()

    def test_service_layer_rejects_lecturer_save_before_reference_calls(self):
        from rest_framework.exceptions import PermissionDenied
        with self.assertRaises(PermissionDenied):
            services.save_topic(self.data, "GV001", "Bearer token", pk="DT001", role=2)
        self.academic.assert_not_called()
        self.assertFalse(Topic.objects.exists())

    def test_lecturer_can_create_topic_with_pending_status_and_self_as_advisor(self):
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO Users VALUES ('GV001')")
        for prefix in ("/api/", "/api/v1/"):
            for status in (None, 0, 1, 2, 3):
                with self.subTest(prefix=prefix, status=status):
                    self.authenticate(2, "GV001")
                    payload = {**self.data, "advisor_id": "OTHER"}
                    if status is None:
                        payload.pop("advisor_id")
                    else:
                        payload["status"] = status
                    response = self.request("post", prefix + "topics/", payload)
                    self.assertEqual(response.status_code, 201, response.data)
                    created = Topic.objects.get(pk="DT001")
                    self.assertEqual((created.status, created.advisor_id, created.updated_by), (0, "GV001", "GV001"))
                    self.assertEqual(response.data["status"], 0)
                    self.academic.assert_called_with([
                        ("major_id", "majors", "major_id", "1"),
                        ("advisor_id", "lecturers", "lecturer_id", "GV001"),
                    ], f"Bearer {self.token}")
                    url = prefix + "topics/DT001/"
                    self.academic.reset_mock()
                    for method, data in (("put", {**self.data, "status": 1}),
                                         ("patch", {"status": 2}), ("delete", None)):
                        self.assertEqual(self.request(method, url, data).status_code, 403)
                    self.academic.assert_not_called()
                    self.cleanup.assert_not_called()
                    created.refresh_from_db()
                    self.assertEqual(created.status, 0)
                    self.authenticate(1)
                    approved = self.request("patch", url, {"status": 1})
                    self.assertEqual(approved.status_code, 200, approved.data)
                    created.refresh_from_db()
                    self.assertEqual(created.status, 1)
                    Topic.objects.all().delete()

    def test_lecturer_creation_reference_failures_do_not_write(self):
        self.authenticate(2, "GV001")
        for error, expected in ((ValidationError({"advisor_id": "Unknown lecturer"}), 400),
                                (clients.DependencyUnavailable(), 503)):
            with self.subTest(status=expected):
                self.academic.side_effect = error
                response = self.request("post", "/api/v1/topics/", self.data)
                self.assertEqual(response.status_code, expected)
                self.assertFalse(Topic.objects.exists())

    def test_management_detail_retains_ids_during_name_outage_and_nullable_advisor(self):
        self.create()
        self.names.side_effect = clients.DependencyUnavailable()
        self.assertEqual(self.request("patch", "/api/topics/DT001/", {"advisor_id": None}).status_code, 200)
        result = self.client.get("/api/topics/DT001/").data
        self.assertEqual(result["major_id"], "1")
        self.assertIsNone(result["advisor_id"])
        self.assertIsNone(result["major_name"])
        self.assertIsNone(result["avisor_name"])

    def test_missing_and_disallowed_methods(self):
        for method in ("get", "put", "patch", "delete"):
            self.assertEqual(self.request(method, "/api/topics/missing/", self.data).status_code, 404)
        self.assertEqual(self.request("post", "/api/topics/missing/", self.data).status_code, 405)
        self.assertEqual(self.request("put", "/api/topics/", self.data).status_code, 405)

    def test_invalid_identity_and_signature(self):
        for identity in (None, "", 123):
            token = AccessToken()
            if identity is not None:
                token["user_id"] = identity
            token["role"] = 1
            self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
            self.assertEqual(self.request("post", "/api/topics/", self.data).status_code, 401)
        header, payload, signature = self.token.split(".")
        signature = ("A" if signature[0] != "A" else "B") + signature[1:]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {header}.{payload}.{signature}")
        self.assertEqual(self.client.get("/api/topics/").status_code, 401)
        self.assertFalse(Topic.objects.exists())

    def test_only_owned_table_is_queried_and_audit_log_is_safe(self):
        with CaptureQueriesContext(connection) as queries, self.assertLogs("topic_manager.views", level="INFO") as logs:
            response = self.client.post("/api/topics/", self.data, format="json", HTTP_X_REQUEST_ID="crud-test-1")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response["X-Request-ID"], "crud-test-1")
        for query in queries:
            for foreign_table in ("Users", "Majors", "Lecturers", "Registrations"):
                self.assertNotIn(f'"{foreign_table}"', query["sql"])
        self.assertIn("crud-test-1", logs.output[0])
        self.assertNotIn(self.token, str(logs.output))
        self.assertNotIn(self.data["name"], str(logs.output))

    def test_reference_failures_do_not_write(self):
        for error, status in [(ValidationError({"major_id": "Missing"}), 400), (clients.DependencyUnavailable(), 503)]:
            self.academic.side_effect = error
            self.assertEqual(self.request("post", "/api/topics/", self.data).status_code, status)
            self.assertFalse(Topic.objects.exists())
        self.academic.side_effect = None
        self.create()
        self.academic.assert_called_with([
            ("major_id", "majors", "major_id", "1"),
            ("advisor_id", "lecturers", "lecturer_id", "GV001")], f"Bearer {self.token}")
        self.academic.side_effect = clients.DependencyUnavailable()
        self.assertEqual(self.request("patch", "/api/topics/DT001/", {"major_id": "2"}).status_code, 503)
        self.assertEqual(Topic.objects.get().major_id, "1")
        # Non-reference updates and reads remain available during dependency outage.
        self.assertEqual(self.request("patch", "/api/topics/DT001/", {"name": "Still available"}).status_code, 200)
        self.assertEqual(self.client.get("/api/topics/").status_code, 200)

    def test_actual_foreign_key_conflicts_rollback(self):
        response = self.request("post", "/api/topics/", {**self.data, "major_id": "999"})
        self.assertEqual(response.status_code, 409)
        self.assertFalse(Topic.objects.exists())
        self.create()
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO Registrations VALUES ('R1', 'DT001')")
        self.assertEqual(self.client.delete("/api/topics/DT001/").status_code, 503)
        self.assertEqual(Topic.objects.get().status, 0)
        self.assertTrue(Topic.objects.exists())

    def test_cascade_orchestration_closes_before_http_and_deletes_topic(self):
        for role in (1,):
            self.authenticate(role)
            self.create()
            with connection.cursor() as cursor:
                cursor.execute("INSERT INTO Topics (TopicId, TopicName, MajorId) VALUES ('OTHER', 'Other', '1')")
                cursor.execute("INSERT INTO Registrations VALUES ('R1', 'DT001')")
                cursor.execute("INSERT INTO Registrations VALUES ('R2', 'OTHER')")
            def emulate_registration_owner(topic_id, authorization, request_id):
                self.assertEqual(topic_id, "DT001")
                self.assertEqual(authorization, "Bearer " + self.token)
                self.assertEqual(request_id, "delete-cascade-1")
                self.assertFalse(connection.in_atomic_block)
                topic = Topic.objects.get(pk=topic_id)
                self.assertEqual(topic.status, 0)
                self.assertEqual(topic.updated_by, "admin")
                # Disposable fixture only: emulates the separate registration service.
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM Registrations WHERE TopicId = %s", [topic_id])
                return 1
            self.cleanup.side_effect = emulate_registration_owner
            response = self.client.delete("/api/v1/topics/DT001/", HTTP_X_REQUEST_ID="delete-cascade-1")
            self.assertEqual(response.status_code, 204)
            self.assertFalse(Topic.objects.filter(pk="DT001").exists())
            self.assertTrue(Topic.objects.filter(pk="OTHER").exists())
            with connection.cursor() as cursor:
                self.assertEqual(cursor.execute("SELECT RegistrationId FROM Registrations").fetchall(), [("R2",)])
                cursor.execute("DELETE FROM Registrations")
            Topic.objects.all().delete()

    def test_cleanup_failure_leaves_closed_topic_and_reports_partial_outcome(self):
        self.create()
        self.cleanup.side_effect = clients.DependencyUnavailable("private host")
        result = self.client.delete("/api/topics/DT001/")
        self.assertEqual(result.status_code, 503)
        self.assertEqual(result.data["code"], "deletion_incomplete")
        self.assertNotIn("private host", str(result.data))
        self.assertEqual(Topic.objects.get().status, 0)
        self.assertEqual(self.cleanup.call_count, 1)
        self.cleanup.side_effect = None
        self.assertEqual(self.client.delete("/api/topics/DT001/").status_code, 204)

    def test_missing_and_unauthorized_delete_never_calls_cleanup(self):
        self.assertEqual(self.client.delete("/api/topics/missing/").status_code, 404)
        self.create()
        for role in (3, "1", True, None):
            self.authenticate(role)
            self.assertEqual(self.client.delete("/api/topics/DT001/").status_code, 403)
        self.cleanup.assert_not_called()
        self.assertEqual(Topic.objects.get().status, 1)

    def test_storage_failure_after_cleanup_reports_partial_outcome(self):
        self.create()
        with patch("django.db.models.query.QuerySet.delete", side_effect=OperationalError("private SQL")):
            result = self.client.delete("/api/topics/DT001/")
        self.assertEqual(result.status_code, 503)
        self.assertEqual(result.data["code"], "deletion_incomplete")
        self.assertNotIn("private SQL", str(result.data))
        self.cleanup.assert_called_once()
        self.assertTrue(Topic.objects.exists())

    def test_storage_errors_are_safe(self):
        for method, path in [("get", "/api/topics/DT001/"), ("delete", "/api/topics/DT001/")]:
            with patch("django.db.models.query.QuerySet.get", side_effect=OperationalError("secret SQL")):
                response = self.request(method, path)
                self.assertEqual(response.status_code, 503)
                self.assertNotIn("secret", str(response.data))
        with patch.object(Topic.objects, "create", side_effect=OperationalError("database locked")):
            self.assertEqual(self.request("post", "/api/topics/", self.data).status_code, 503)

    def test_concurrent_delete_does_not_insert(self):
        self.create()
        with patch("topic_manager.services.Topic.objects.filter") as filtered:
            filtered.return_value.update.return_value = 0
            self.assertEqual(self.request("patch", "/api/topics/DT001/", {"name": "x"}).status_code, 404)
        self.assertEqual(Topic.objects.get().name, self.data["name"])


@override_settings(ACADEMIC_CLIENT=CLIENT_CONFIG)
class AcademicClientTests(SimpleTestCase):
    def setUp(self):
        self.client = clients.AcademicClient()

    @patch.object(clients, "fetch_json", return_value={"major_id": "1"})
    def test_static_development_contract(self, fetch):
        self.client.validate(REFERENCE, "Bearer test")
        fetch.assert_called_once_with("http://academic.test:8002/api/majors/1/", {"Authorization": "Bearer test"}, 2)

    @override_settings(ACADEMIC_CLIENT={**CLIENT_CONFIG, "BASE_URL": "http://127.0.0.1:8002"},
                       CONSUL={"URL": "http://unreachable-registry.invalid:8500", "TOKEN": "registry-only"})
    @patch.object(clients, "fetch_json")
    def test_explicit_loopback_validates_both_references_without_registry(self, fetch):
        fetch.side_effect = [{"major_id": "1"}, {"lecturer_id": "GV001"}]
        self.client.validate(REFERENCE + [("advisor_id", "lecturers", "lecturer_id", "GV001")], "Bearer test")
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual([call.args for call in fetch.call_args_list], [
            ("http://127.0.0.1:8002/api/majors/1/", {"Authorization": "Bearer test"}, 2),
            ("http://127.0.0.1:8002/api/lecturers/GV001/", {"Authorization": "Bearer test"}, 2),
        ])

    @override_settings(ACADEMIC_CLIENT={**CLIENT_CONFIG, "BASE_URL": "http://127.0.0.1:8002"})
    @patch.object(clients, "fetch_json", side_effect=URLError("private transport detail"))
    def test_explicit_loopback_failure_remains_safe_and_does_not_retry(self, fetch):
        with self.assertRaises(clients.DependencyUnavailable) as caught:
            self.client.validate(REFERENCE, "Bearer test")
        self.assertNotIn("private", str(caught.exception))
        self.assertEqual(fetch.call_count, 1)

    @override_settings(ACADEMIC_CLIENT={**CLIENT_CONFIG, "DISCOVERY_ENABLED": True},
                       CONSUL={"URL": "http://registry:8500", "TOKEN": "acl"})
    @patch.object(clients, "fetch_json")
    def test_discovery_and_bearer_separation(self, fetch):
        fetch.side_effect = [[{"Service": {"Service": "academic-service", "Address": "::1", "Port": 8002},
                               "Checks": [{"Status": "passing"}]}], {"major_id": "1"}]
        self.client.validate(REFERENCE, "Bearer test")
        self.assertEqual(fetch.call_args_list[0].args, (
            "http://registry:8500/v1/health/service/academic-service?passing=true", {"X-Consul-Token": "acl"}, 2))
        self.assertEqual(fetch.call_args_list[1].args[0], "http://[::1]:8002/api/majors/1/")
        self.assertEqual(fetch.call_args_list[1].args[1], {"Authorization": "Bearer test"})

    @override_settings(ACADEMIC_CLIENT={**CLIENT_CONFIG, "DISCOVERY_ENABLED": True})
    @patch.object(clients, "fetch_json")
    def test_invalid_registry_never_falls_back(self, fetch):
        for payload in ([], {}, [{"Service": {}}],
                        [{"Service": {"Service": "academic-service", "Address": "bad/host", "Port": 8002},
                          "Checks": [{"Status": "passing"}]}],
                        [{"Service": {"Service": "academic-service"}, "Checks": [{"Status": "critical"}]}]):
            fetch.reset_mock()
            fetch.return_value = payload
            with self.assertRaises(clients.DependencyUnavailable):
                clients.AcademicClient().validate(REFERENCE, "Bearer test")
            self.assertEqual(fetch.call_count, 1)

    @patch.object(clients, "fetch_json")
    def test_missing_reference_and_upstream_errors(self, fetch):
        for code in (404, 401, 403, 500, 302):
            fetch.side_effect = HTTPError("http://academic.test", code, "private response", {}, None)
            expected = ValidationError if code == 404 else clients.DependencyUnavailable
            with self.assertRaises(expected) as caught:
                clients.AcademicClient().validate(REFERENCE, "Bearer test")
            self.assertNotIn("private", str(caught.exception))

    @patch.object(clients, "fetch_json")
    def test_malformed_payload_and_timeout(self, fetch):
        for value in (None, [], {}, {"major_id": "wrong"}):
            fetch.return_value = value
            with self.assertRaises(clients.DependencyUnavailable):
                clients.AcademicClient().validate(REFERENCE, "Bearer test")
        fetch.side_effect = TimeoutError()
        with self.assertRaises(clients.DependencyUnavailable):
            clients.AcademicClient().validate(REFERENCE, "Bearer test")

    @patch.object(clients.time, "monotonic", return_value=100)
    @patch.object(clients, "fetch_json", side_effect=TimeoutError())
    def test_circuit_opens_and_recovers(self, fetch, clock):
        for _ in range(4):
            with self.assertRaises(clients.DependencyUnavailable):
                self.client.validate(REFERENCE, "Bearer test")
        self.assertEqual(fetch.call_count, 3)
        clock.return_value = 111
        fetch.side_effect = None
        fetch.return_value = {"major_id": "1"}
        self.client.validate(REFERENCE, "Bearer test")
        self.assertEqual(self.client.failures, 0)
        self.assertEqual(self.client.open_until, 0)

    @patch.object(clients, "fetch_json", return_value={"lecturer_id": "GV 1"})
    def test_string_advisor_id_is_encoded(self, fetch):
        self.client.validate([("advisor_id", "lecturers", "lecturer_id", "GV 1")], "Bearer test")
        self.assertIn("GV%201/", fetch.call_args.args[0])

    @patch.object(clients, "fetch_json")
    def test_non_numeric_major_is_explicit_validation_error(self, fetch):
        self.client.open_until = float("inf")
        with self.assertRaises(ValidationError):
            self.client.validate([("major_id", "majors", "major_id", "CNTT")], "Bearer test")
        fetch.assert_not_called()

    def test_discovery_address_validation(self):
        self.assertEqual(clients.instance_url("academic.local", 8002), "http://academic.local:8002")
        for address, port in [("bad/host", 8002), ("host", 0), ("host", True), ("", 8002)]:
            with self.assertRaises(ValueError):
                clients.instance_url(address, port)

    @patch.object(clients, "build_opener")
    def test_transport_limits_and_no_redirect(self, opener):
        response = opener.return_value.open.return_value.__enter__.return_value
        response.read.return_value = b'{"major_id":"1"}'
        self.assertEqual(clients.fetch_json("http://academic.test", {"Authorization": "Bearer test"}, 2), {"major_id": "1"})
        self.assertIsInstance(opener.call_args.args[0], clients.NoRedirect)
        self.assertEqual(opener.return_value.open.call_args.kwargs["timeout"], 2)
        response.read.assert_called_with(262145)
        response.read.return_value = b"x" * 262145
        with self.assertRaises(ValueError):
            clients.fetch_json("http://academic.test", {}, 2)
        self.assertIsNone(clients.NoRedirect().redirect_request(None, None, 302, "", {}, "http://other"))


@override_settings(ACADEMIC_CLIENT=CLIENT_CONFIG)
class TopicNameClientTests(SimpleTestCase):
    @patch.object(clients, "fetch_json")
    def test_batches_deduplicate_and_resolve_once(self, fetch):
        def response(url, headers, timeout, data=None):
            return {"major_names": {i: "Major " + i for i in data["major_ids"]},
                    "advisor_names": {i: "Lecturer " + i for i in data["advisor_ids"]}}
        fetch.side_effect = response
        client = clients.AcademicClient()
        with patch.object(client, "base_url", return_value="http://academic.test") as discover:
            result = client.display_names([str(i) for i in range(205)] + ["1"] * 50, ["GV1"] * 500, "Bearer t")
        discover.assert_called_once()
        self.assertEqual(fetch.call_count, 3)
        self.assertEqual(result["major_names"]["204"], "Major 204")
        self.assertEqual(result["advisor_names"], {"GV1": "Lecturer GV1"})
        for call in fetch.call_args_list:
            self.assertLessEqual(len(call.args[3]["major_ids"]), 100)
            self.assertLessEqual(len(call.args[3]["advisor_ids"]), 100)
            self.assertEqual(call.args[1], {"Authorization": "Bearer t"})
            self.assertEqual(call.args[2], 2)

    @patch.object(clients, "fetch_json")
    def test_empty_and_nullable_names(self, fetch):
        client = clients.AcademicClient()
        self.assertEqual(client.display_names([], [], "Bearer t"), {"major_names": {}, "advisor_names": {}})
        fetch.assert_not_called()
        fetch.return_value = {"major_names": {"1": None}, "advisor_names": {}}
        self.assertIsNone(client.display_names(["1"], [], "Bearer t")["major_names"]["1"])

    @patch.object(clients, "fetch_json")
    def test_malformed_name_contract(self, fetch):
        for payload in ({}, {"major_names": {}, "advisor_names": {}},
                        {"major_names": {"1": 5}, "advisor_names": {}},
                        {"major_names": {"1": "IT", "extra": "private"}, "advisor_names": {}}):
            fetch.return_value = payload
            with self.assertRaises(clients.DependencyUnavailable):
                clients.AcademicClient().display_names(["1"], [], "Bearer t")

    @patch.object(clients.time, "monotonic", return_value=10)
    @patch.object(clients, "fetch_json", side_effect=TimeoutError())
    def test_display_circuit_and_recovery(self, fetch, clock):
        client = clients.AcademicClient()
        for _ in range(4):
            with self.assertRaises(clients.DependencyUnavailable):
                client.display_names(["1"], [], "Bearer t")
        self.assertEqual(fetch.call_count, 3)
        clock.return_value = 21
        fetch.side_effect = None
        fetch.return_value = {"major_names": {"1": "IT"}, "advisor_names": {}}
        self.assertEqual(client.display_names(["1"], [], "Bearer t")["major_names"]["1"], "IT")
        self.assertEqual(client.failures, 0)
        self.assertIsNot(clients.academic_client, clients.academic_names_client)

    @patch.object(clients.academic_names_client, "display_names", return_value={
        "major_names": {"1": "IT"}, "advisor_names": {"GV1": "Nguyen An"}})
    def test_enrichment_deduplication_and_response_shape(self, names):
        obj = SimpleNamespace(req_GPA=0, studentQuota=1, topic_id="T", name="SOA", description=None, file_url=None,
                              major_id="1", advisor_id="GV1", status=1,
                              created_at=None, updated_at=None, updated_by=None)
        response = topic_response([obj] * 200, "Bearer t", many=True)
        names.assert_called_once_with(["1"], ["GV1"], "Bearer t")
        self.assertEqual(set(response[0]), {"req_GPA", "studentQuota", "topic_id", "name", "description", "file_url", "major_name", "status",
                                            "avisor_name", "created_at", "updated_at", "updated_by"})
        self.assertEqual(response[0]["avisor_name"], "Nguyen An")
        self.assertEqual(len(response), 200)

    @patch.object(clients.academic_names_client, "display_names", return_value={
        "major_names": {"1": "IT"}, "advisor_names": {"GV1": None}})
    def test_identity_fallback_retains_real_major_without_fabricating_advisor(self, names):
        obj = SimpleNamespace(req_GPA=0, studentQuota=1, topic_id="T", name="SOA", description=None, file_url=None,
                              major_id="1", advisor_id="GV1", status=1,
                              created_at=None, updated_at=None, updated_by=None)
        response = topic_response(obj, "Bearer t")
        self.assertEqual(response["major_name"], "IT")
        self.assertIsNone(response["avisor_name"])
        self.assertNotIn("advisor_id", response)

    @patch.object(clients.academic_names_client, "display_names", side_effect=[
        clients.DependencyUnavailable(), {"major_names": {"1": "IT"}, "advisor_names": {"GV1": "Nguyen An"}}])
    def test_enrichment_recovers_on_next_lookup_after_dependency_recovers(self, names):
        obj = SimpleNamespace(req_GPA=0, studentQuota=1, topic_id="T", name="SOA", description=None, file_url=None,
                              major_id="1", advisor_id="GV1", status=1,
                              created_at=None, updated_at=None, updated_by=None)
        failed = topic_response(obj, "Bearer t")
        self.assertIsNone(failed["major_name"])
        self.assertIsNone(failed["avisor_name"])
        recovered = topic_response(obj, "Bearer t")
        self.assertEqual(recovered["major_name"], "IT")
        self.assertEqual(recovered["avisor_name"], "Nguyen An")
