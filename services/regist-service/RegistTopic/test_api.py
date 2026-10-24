from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from datetime import timedelta
import threading
from unittest.mock import patch

from django.db import IntegrityError, OperationalError, connection, connections
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from . import clients, services
from .models import Registration

URL = "/api/v1/registrations/"


class RegistrationAPITests(TransactionTestCase):
    def test_database_first_point_mapping(self):
        field = Registration._meta.get_field("point")
        self.assertEqual(field.db_column, "Point")
        self.assertEqual((field.max_digits, field.decimal_places), (4, 2))
        self.assertFalse(Registration._meta.managed)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with connection.schema_editor() as editor:
            editor.create_model(Registration)

    @classmethod
    def tearDownClass(cls):
        with connection.schema_editor() as editor:
            editor.delete_model(Registration)
        super().tearDownClass()

    def setUp(self):
        Registration.objects.all().delete()
        self.client = APIClient()
        self.authenticate()
        self.context = self.mock(clients.academic_client, "context", {"student_id": "SV1", "department_id": "F1", "gpa": 3.2})
        self.departments = self.mock(clients.academic_client, "departments", {"M2": "F1"})
        self.topic = self.mock(clients.topic_client, "topic", {"topic_id": "T1", "name": "SOA", "req_GPA": 0, "studentQuota": 1, "major_id": "M2", "status": 2})
        self.page = self.mock(clients.topic_client, "page", {"results": [], "next_after": None})
        self.mock(clients, "fetch_json", side_effect=AssertionError("Live network forbidden"))

    def tearDown(self):
        Registration.objects.all().delete()
        super().tearDown()

    def mock(self, obj, name, value=None, **kwargs):
        patcher = patch.object(obj, name, return_value=value, **kwargs)
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    def authenticate(self, role=3, identity="SV1", expired=False):
        token = AccessToken()
        token["user_id"], token["role"] = identity, role
        if expired:
            token.set_exp(lifetime=timedelta(seconds=-1))
        self.token = str(token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def create(self, **kwargs):
        return self.client.post(URL, {"topic_id": "T1", **kwargs}, format="json")

    def test_register_list_cancel_and_register_again(self):
        result = self.create()
        self.assertEqual(result.status_code, 201, result.data)
        pk = result.data["registration_id"]
        record = Registration.objects.get(pk=pk)
        self.assertEqual((record.student_id, record.updated_by, record.status), ("SV1", "SV1", 1))
        self.assertEqual(self.client.get(URL).data, [result.data])
        self.assertEqual(self.create().status_code, 200)
        self.assertEqual(self.create(semester="different").status_code, 409)
        self.topic.return_value = {**self.topic.return_value, "topic_id": "T2"}
        self.assertEqual(self.create(topic_id="T2").status_code, 409)
        for _ in range(2):
            self.assertEqual(self.client.delete(URL + pk + "/").status_code, 204)
        self.assertEqual(len(self.client.get(URL + "?status=cancelled").data), 1)
        self.assertEqual(self.client.get(URL + "?status=active").data, [])
        self.assertEqual(self.create(topic_id="T2").status_code, 201)
        self.assertEqual(Registration.objects.count(), 2)

    def test_gpa_boundary_and_idempotent_retry_after_requirement_change(self):
        self.topic.return_value["req_GPA"] = 3.21
        denied = self.create()
        self.assertEqual((denied.status_code, denied.data["code"]), (400, "gpa_requirement_not_met"))
        self.assertFalse(Registration.objects.exists())
        self.topic.return_value["req_GPA"] = 3.2
        self.assertEqual(self.create().status_code, 201)
        self.context.return_value["gpa"] = 0
        self.assertEqual(self.create().status_code, 200)
        self.assertEqual(Registration.objects.count(), 1)

    def test_quota_counts_distinct_active_students_and_cancel_releases_seat(self):
        for index, status in enumerate((1, None, -1)):
            Registration.objects.create(registration_id=str(index), student_id="SV2", topic_id="T1", status=status)
        # Three legacy records for one student occupy one seat.
        result = self.create()
        self.assertEqual((result.status_code, result.data["code"]), (409, "topic_quota_full"))
        Registration.objects.filter(student_id="SV2").update(status=0)
        self.assertEqual(self.create().status_code, 201)
        self.assertEqual(self.client.delete(URL + Registration.objects.get(student_id="SV1").pk + "/").status_code, 204)
        self.assertEqual(self.create().status_code, 201)

    def test_available_eligibility_and_capacity_are_computed_on_server(self):
        self.page.return_value = {"results": [self.topic.return_value], "next_after": None}
        def available():
            return self.client.get("/api/v1/available-topics/").data["results"][0]
        row = available()
        self.assertEqual((row["eligible"], row["registered_count"], row["ineligibility_reason"]), (True, 0, None))
        self.topic.return_value["req_GPA"] = 4
        self.assertEqual(available()["ineligibility_reason"], "gpa_requirement_not_met")
        self.topic.return_value["req_GPA"] = 0
        Registration.objects.create(registration_id="other", student_id="SV2", topic_id="T1", status=None)
        row = available()
        self.assertEqual((row["eligible"], row["registered_count"], row["ineligibility_reason"]), (False, 1, "topic_quota_full"))

    def test_concurrent_students_cannot_take_same_last_seat(self):
        barrier = threading.Barrier(2)
        def attempt(identity):
            connections.close_all()
            try:
                barrier.wait(timeout=5)
                return 201 if services.register(identity, {"topic_id": "T1"}, "Bearer test", "quota-race")[1] else 200
            except services.TopicQuotaFull:
                return 409
            except OperationalError:
                return 503
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, ["SV1", "SV2"]))
        self.assertEqual(results.count(201), 1, results)
        self.assertTrue(all(value in (201, 409, 503) for value in results), results)
        self.assertEqual(services.topic_student_counts(["T1"]), {"T1": 1})

    def test_semester_and_repeated_cancel_preserve_history(self):
        result = self.create(semester="2026-1")
        self.assertEqual(result.data["semester"], "2026-1")
        self.assertEqual(self.create(semester="2026-1").status_code, 200)
        pk = result.data["registration_id"]
        self.client.delete(URL + pk + "/")
        obj = Registration.objects.get(pk=pk)
        self.assertEqual(obj.created_at.isoformat().replace("+00:00", "Z"), result.data["created_at"])
        updated = obj.updated_at
        self.client.delete(URL + pk + "/")
        obj.refresh_from_db()
        self.assertEqual(obj.updated_at, updated)

    def test_owner_filter_and_cancel(self):
        Registration.objects.create(registration_id="other", student_id="SV2", topic_id="T1", status=1, point=Decimal("9.00"))
        Registration.objects.create(registration_id="mine", student_id="SV1", topic_id="T1", status=1, point=Decimal("8.25"))
        self.assertEqual([row["registration_id"] for row in self.client.get(URL + "?student_id=SV2").data], ["mine"])
        self.assertEqual([(row["registration_id"], row["point"]) for row in self.client.get(URL).data], [("mine", "8.25")])
        self.assertEqual(self.client.delete(URL + "other/").status_code, 404)
        self.assertEqual(self.client.delete(URL + "missing/").status_code, 404)
        self.assertEqual(Registration.objects.get(pk="other").status, 1)

    def test_student_cannot_cancel_when_topic_registration_is_closed(self):
        obj = Registration.objects.create(registration_id="R1", student_id="SV1", topic_id="T1",
                                          status=1, point=Decimal("8.50"), updated_by="previous")
        self.topic.return_value = {**self.topic.return_value, "status": 3}
        result = self.client.delete(URL + "R1/", HTTP_X_REQUEST_ID="cancel-closed")
        self.assertEqual(result.status_code, 409, result.data)
        self.assertEqual(result.data["code"], "topic_registration_closed")
        self.assertEqual(result["X-Request-ID"], "cancel-closed")
        self.topic.assert_called_once_with("T1", f"Bearer {self.token}", "cancel-closed")
        obj.refresh_from_db()
        self.assertEqual((obj.status, obj.point, obj.updated_by, obj.updated_at),
                         (1, Decimal("8.50"), "previous", None))
        self.assertEqual(self.client.get(URL).data[0]["point"], "8.50")
        obj.status = 0
        obj.save(update_fields=["status"])
        self.topic.reset_mock()
        self.assertEqual(self.client.delete(URL + "R1/").status_code, 204)
        self.topic.assert_not_called()

    def test_student_cancel_fails_closed_when_topic_lookup_fails(self):
        Registration.objects.create(registration_id="R1", student_id="SV1", topic_id="T1", status=1)
        self.topic.side_effect = clients.DependencyUnavailable()
        self.assertEqual(self.client.delete(URL + "R1/").status_code, 503)
        self.assertEqual(Registration.objects.get(pk="R1").status, 1)
        self.topic.side_effect = NotFound()
        self.assertEqual(self.client.delete(URL + "R1/").status_code, 404)
        self.assertEqual(Registration.objects.get(pk="R1").status, 1)
        self.topic.assert_called()

    def test_same_faculty_different_major_and_open_topic_only(self):
        # Context supplies faculty F1; topic major M2 is independently resolved.
        self.assertEqual(self.create().status_code, 201)
        Registration.objects.all().delete()
        for status in (0, 1, 3, None):
            self.topic.return_value["status"] = status
            response = self.create()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.data["code"], "topic_closed")
        self.topic.return_value["status"] = 2
        for department in (None, "F2"):
            self.departments.return_value = {"M2": department}
            response = self.create()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.data["code"], "faculty_mismatch")
        self.assertFalse(Registration.objects.exists())

    def test_available_topics_are_filtered_and_keep_cursor(self):
        rows = [{"topic_id": f"T{i}", "name": "SOA", "req_GPA": 0, "studentQuota": 1, "major_id": f"M{i}", "status": 2} for i in range(3)]
        self.page.return_value = {"results": rows, "next_after": "T2"}
        self.departments.return_value = {"M0": "F1", "M1": "F2", "M2": None}
        result = self.client.get("/api/v1/available-topics/?after=T0")
        self.assertEqual(result.data, {"results": [{**rows[0], "registered_count": 0, "eligible": True, "ineligibility_reason": None}], "next_after": "T2"})
        self.page.assert_called_once_with("T0", f"Bearer {self.token}", result["X-Request-ID"])
        self.page.return_value = {"results": [], "next_after": None}
        self.departments.reset_mock()
        self.assertEqual(self.client.get("/api/v1/available-topics/").data["results"], [])
        self.departments.assert_not_called()

    def test_role_identity_token_and_input_denials(self):
        for role in (1, 2, "3", True, None):
            self.authenticate(role)
            for method, path in (("get", URL), ("post", URL), ("delete", URL + "id/"), ("get", "/api/v1/available-topics/")):
                self.assertEqual(getattr(self.client, method)(path).status_code, 403)
        for identity in (None, "", 12):
            self.authenticate(identity=identity)
            self.assertEqual(self.create().status_code, 401)
        self.authenticate(expired=True)
        self.assertEqual(self.create().status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid")
        self.assertEqual(self.create().status_code, 401)
        self.client.credentials()
        self.assertEqual(self.create().status_code, 401)
        self.authenticate()
        for field in ("student_id", "status", "updated_by", "registration_id"):
            self.assertEqual(self.create(**{field: "override"}).status_code, 400)
        self.assertEqual(self.create(topic_id="").status_code, 400)
        self.assertEqual(self.client.get(URL + "?status=unknown").status_code, 400)
        self.assertEqual(self.client.get("/api/v1/available-topics/?after=" + "x" * 256).status_code, 400)
        self.assertFalse(Registration.objects.exists())

    def test_dependency_failures_never_write_and_cancellation_is_independent(self):
        created = self.create()
        pk = created.data["registration_id"]
        self.context.side_effect = clients.DependencyUnavailable()
        self.assertEqual(self.client.delete(URL + pk + "/").status_code, 204)
        for error, status in ((clients.DependencyUnavailable(), 503), (PermissionDenied(), 403)):
            self.context.side_effect = error
            self.assertEqual(self.create().status_code, status)
        self.context.side_effect = None
        self.topic.side_effect = NotFound()
        self.assertEqual(self.create().status_code, 404)
        self.topic.side_effect = clients.DependencyUnavailable()
        self.assertEqual(self.create().status_code, 503)
        self.topic.side_effect = None
        self.departments.side_effect = clients.DependencyUnavailable()
        self.assertEqual(self.create().status_code, 503)
        self.assertFalse(services.current_registrations("SV1").exists())

    def test_legacy_statuses_and_duplicate_records_fail_closed(self):
        for status in (None, 2, -1):
            Registration.objects.all().delete()
            Registration.objects.create(registration_id="legacy", student_id="SV1", topic_id="old", status=status)
            self.assertEqual(self.create().status_code, 409)
            self.assertEqual(len(self.client.get(URL + "?status=active").data), 1)
        Registration.objects.create(registration_id="second", student_id="SV1", topic_id="T1", status=1)
        self.assertEqual(self.create().status_code, 409)

    def test_owned_queries_audit_and_storage_errors(self):
        with CaptureQueriesContext(connection) as queries, self.assertLogs("RegistTopic.views", level="INFO") as logs:
            result = self.client.post(URL, {"topic_id": "T1"}, format="json", HTTP_X_REQUEST_ID="registration-1")
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result["X-Request-ID"], "registration-1")
        self.assertNotIn(self.token, str(logs.output))
        for query in queries:
            for table in ("Users", "Students", "Topics", "Majors", "Faculties"):
                self.assertNotIn('"' + table + '"', query["sql"])
        with patch.object(services, "acquire_write_lock", side_effect=OperationalError("private SQL")):
            result = self.create()
            self.assertEqual(result.status_code, 503)
            self.assertNotIn("private", str(result.data))
        Registration.objects.all().delete()
        with patch.object(Registration.objects, "create", side_effect=IntegrityError("private schema")):
            self.assertEqual(self.create().status_code, 409)
        self.assertFalse(Registration.objects.exists())

    def test_concurrent_registration_has_at_most_one_current_record(self):
        barrier = threading.Barrier(2)
        def attempt(topic_id):
            connections.close_all()
            try:
                barrier.wait(timeout=5)
                obj, created = services.register("SV1", {"topic_id": topic_id}, "Bearer test", "race")
                return 201 if created else 200
            except services.RegistrationConflict:
                return 409
            except OperationalError:
                return 503  # Shared-cache test SQLite may immediately reject lock contention.
            finally:
                connections.close_all()
        self.topic.side_effect = lambda topic_id, *args: {"topic_id": topic_id, "major_id": "M2", "name": "SOA", "req_GPA": 0, "studentQuota": 1, "status": 2}
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, ["T1", "T2"]))
        self.assertEqual(results.count(201), 1, results)
        self.assertTrue(all(status in (201, 409, 503) for status in results))
        self.assertEqual(services.current_registrations("SV1").count(), 1)
