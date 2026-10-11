from unittest.mock import patch
from django.db import connection, OperationalError
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken
from .models import Registration
from . import clients


class TopicRosterTests(TransactionTestCase):
    url = "/api/v1/topics/T1/registrations/"

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
        self.authenticate(1)
        self.names_patch = patch.object(clients.academic_client, "student_names", return_value={
            "student_names": {"S1": "Nguyen An"}, "names_unavailable": False})
        self.names = self.names_patch.start()
        self.addCleanup(self.names_patch.stop)
        self.network_patch = patch.object(clients, "fetch_json", side_effect=AssertionError("Live network forbidden"))
        self.network_patch.start()
        self.addCleanup(self.network_patch.stop)

    def authenticate(self, role):
        token = AccessToken()
        token["user_id"], token["role"] = "manager", role
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_topic_isolation_current_status_and_minimal_dto(self):
        for key, topic, status in (("R1", "T1", 1), ("R2", "T1", None), ("R3", "T1", 2),
                                   ("R4", "T1", 0), ("R5", "T2", 1)):
            Registration.objects.create(registration_id=key, student_id="S1", topic_id=topic,
                                        status=status, notes="private", reason="private")
        for role in (1, 2):
            self.authenticate(role)
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get(self.url, HTTP_X_REQUEST_ID="roster-1")
            self.assertEqual(response.status_code, 200)
            self.assertEqual([row["registration_id"] for row in response.data["results"]], ["R1", "R2", "R3"])
            self.assertEqual(set(response.data["results"][0]), {
                "registration_id", "student_id", "student_name", "semester", "status", "created_at"})
            self.assertEqual(response.data["results"][0]["student_name"], "Nguyen An")
            self.assertEqual(response["X-Request-ID"], "roster-1")
            for query in queries:
                for table in ("Users", "Students", "Topics", "Majors"):
                    self.assertNotIn('"' + table + '"', query["sql"])
        self.assertEqual(self.names.call_args.args[0], ["S1"])
        self.assertTrue(self.names.call_args.args[1].startswith("Bearer "))

    def test_empty_pagination_and_partial_names(self):
        self.assertEqual(self.client.get(self.url).data, {"results": [], "next_after": None, "names_unavailable": False})
        self.names.assert_not_called()
        Registration.objects.bulk_create([Registration(registration_id=f"R{i:03}", topic_id="T1", student_id="S1", status=1) for i in range(101)])
        page = self.client.get(self.url).data
        self.assertEqual(len(page["results"]), 100)
        self.assertEqual(page["next_after"], "R099")
        self.assertEqual(len(self.client.get(self.url + "?after=R099").data["results"]), 1)
        self.names.side_effect = clients.DependencyUnavailable()
        result = self.client.get(self.url).data
        self.assertEqual(len(result["results"]), 100)
        self.assertTrue(result["names_unavailable"])
        self.assertIsNone(result["results"][0]["student_name"])

    def test_roles_queries_and_safe_storage_failure(self):
        for role in (3, "1", True, None, 0):
            self.authenticate(role)
            self.assertEqual(self.client.get(self.url).status_code, 403)
        self.client.credentials()
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.authenticate(1)
        for suffix in ("?after=" + "x" * 256, "?student_id=other"):
            self.assertEqual(self.client.get(self.url + suffix).status_code, 400)
        self.assertEqual(self.client.post(self.url, {}, format="json").status_code, 405)
        with patch.object(Registration.objects, "filter", side_effect=OperationalError("secret SQL")):
            result = self.client.get(self.url)
            self.assertEqual(result.status_code, 503)
            self.assertNotIn("secret", str(result.data))


    def test_management_cancellation_audit_history_and_idempotence(self):
        for role in (1, 2):
            for initial in (1, None, 2):
                self.authenticate(role)
                Registration.objects.all().delete()
                Registration.objects.create(registration_id="R1", student_id="S1", topic_id="T1",
                    status=initial, semester="2026-1", notes="keep", updated_by="student")
                Registration.objects.create(registration_id="R2", student_id="S2", topic_id="T1", status=1)
                url = self.url + "R1/"
                self.assertEqual(self.client.get(url).data, {"registration_id": "R1", "topic_id": "T1", "status": initial})
                response = self.client.delete(url, HTTP_X_REQUEST_ID="cancel-1")
                self.assertEqual(response.status_code, 204)
                self.assertEqual(response["X-Request-ID"], "cancel-1")
                obj = Registration.objects.get(pk="R1")
                self.assertEqual((obj.status, obj.updated_by, obj.student_id, obj.topic_id, obj.semester, obj.notes),
                                 (0, "manager", "S1", "T1", "2026-1", "keep"))
                timestamp = obj.updated_at
                self.assertIsNotNone(timestamp)
                self.assertEqual(self.client.delete(url).status_code, 204)
                obj.refresh_from_db()
                self.assertEqual(obj.updated_at, timestamp)
                self.assertEqual(Registration.objects.get(pk="R2").status, 1)
                self.assertEqual(self.client.get(url).data["status"], 0)
                self.assertEqual(Registration.objects.count(), 2)
        self.names.assert_not_called()

    def test_management_cancel_permissions_and_topic_isolation(self):
        Registration.objects.create(registration_id="R1", topic_id="T2", student_id="S1", status=1)
        for role in (3, "1", True, None, 0):
            self.authenticate(role)
            for method in ("get", "delete"):
                self.assertEqual(getattr(self.client, method)(self.url + "R1/").status_code, 403)
        self.client.credentials()
        self.assertEqual(self.client.delete(self.url + "R1/").status_code, 401)
        self.authenticate(1)
        for method in ("get", "delete"):
            self.assertEqual(getattr(self.client, method)(self.url + "R1/").status_code, 404)
            self.assertEqual(getattr(self.client, method)(self.url + "missing/").status_code, 404)
        self.assertEqual(Registration.objects.get().status, 1)

    def test_cancel_storage_failure_is_safe_and_rolls_back(self):
        Registration.objects.create(registration_id="R1", topic_id="T1", student_id="S1", status=1)
        from django.db.models.query import QuerySet
        original_update = QuerySet.update
        def failing_update(query, **values):
            original_update(query, **values)
            raise OperationalError("private SQL")
        with patch.object(QuerySet, "update", failing_update):
            result = self.client.delete(self.url + "R1/")
        self.assertEqual(result.status_code, 503)
        self.assertNotIn("private", str(result.data))
        self.assertEqual(Registration.objects.get().status, 1)


    def test_permanent_topic_cleanup_all_statuses_isolated_and_idempotent(self):
        for role in (1, 2):
            self.authenticate(role)
            for i, status in enumerate((None, 0, 1, 2)):
                Registration.objects.create(registration_id=f"R{i}", topic_id="T1", student_id="S1", status=status)
            Registration.objects.update_or_create(registration_id="OTHER", defaults={"topic_id": "T2"})
            with CaptureQueriesContext(connection) as queries:
                result = self.client.delete(self.url, HTTP_X_REQUEST_ID="purge-1")
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.data, {"topic_id": "T1", "deleted_count": 4})
            self.assertEqual(result["X-Request-ID"], "purge-1")
            self.assertEqual(list(Registration.objects.values_list("registration_id", flat=True)), ["OTHER"])
            self.assertEqual(self.client.delete(self.url).data["deleted_count"], 0)
            for query in queries:
                for table in ("Topics", "Students", "Users"):
                    self.assertNotIn('"' + table + '"', query["sql"])
        self.names.assert_not_called()

    def test_permanent_cleanup_permissions_and_transaction_rollback(self):
        Registration.objects.create(registration_id="R1", topic_id="T1", status=1)
        for role in (3, "1", True, None, 0):
            self.authenticate(role)
            self.assertEqual(self.client.delete(self.url).status_code, 403)
        self.client.credentials()
        self.assertEqual(self.client.delete(self.url).status_code, 401)
        self.authenticate(1)
        from django.db.models.query import QuerySet
        original = QuerySet.delete
        def fail_after_delete(query):
            original(query)
            raise OperationalError("private SQL")
        with patch.object(QuerySet, "delete", fail_after_delete):
            result = self.client.delete(self.url)
        self.assertEqual(result.status_code, 503)
        self.assertNotIn("private SQL", str(result.data))
        self.assertTrue(Registration.objects.filter(pk="R1").exists())
        self.assertEqual(self.client.delete("/api/v1/topics/unknown/registrations/").data["deleted_count"], 0)
        self.assertTrue(Registration.objects.filter(pk="R1").exists())
