from unittest.mock import patch
from django.core.cache import cache
from django.db import OperationalError
from django.test import SimpleTestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken
from .display_names import Student, identity_client, ReaderLookupThrottle


class StudentDisplayNamesTests(SimpleTestCase):
    url = "/api/v1/student-display-names/"

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.authenticate(1)
        self.students_patch = patch.object(Student.objects, "filter")
        self.students = self.students_patch.start()
        self.students.return_value.values_list.return_value = ["S1"]
        self.addCleanup(self.students_patch.stop)
        self.names_patch = patch.object(identity_client, "names", return_value={"S1": "Nguyen An"})
        self.names = self.names_patch.start()
        self.addCleanup(self.names_patch.stop)

    def authenticate(self, role):
        token = AccessToken()
        token["user_id"], token["role"] = "manager", role
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def post(self, data=None):
        return self.client.post(self.url, {"student_ids": ["S1", "missing", "S1"]} if data is None else data, format="json")

    def test_manager_roles_and_no_arbitrary_identity_lookup(self):
        for role in (1, 2):
            self.authenticate(role)
            response = self.post()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, {"student_names": {"S1": "Nguyen An", "missing": None}, "names_unavailable": True})
        self.students.assert_called_with(pk__in=["S1", "missing"])
        self.names.assert_called_with(["S1"])
        self.students.return_value.values_list.assert_called_with("student_id", flat=True)

    def test_names_outage_preserves_student_ids_and_empty_batch(self):
        self.names.return_value = {"S1": None}
        self.assertTrue(self.post().data["names_unavailable"])
        self.students.return_value.values_list.return_value = []
        self.names.reset_mock()
        self.assertEqual(self.post({"student_ids": []}).data, {"student_names": {}, "names_unavailable": False})
        self.names.assert_not_called()

    def test_permissions_and_validation(self):
        for role in (3, True, "1", None):
            self.authenticate(role)
            self.assertEqual(self.post().status_code, 403)
        self.client.credentials()
        self.assertEqual(self.post().status_code, 401)
        self.authenticate(1)
        for data in ({}, {"student_ids": ["x"] * 101}, {"student_ids": [""]},
                     {"student_ids": [], "private": True}, {"student_ids": ["x" * 65537]}):
            self.assertEqual(self.post(data).status_code, 400)
        self.students.assert_not_called()
        self.names.assert_not_called()

    def test_safe_storage_error_and_rate_limit(self):
        self.students.side_effect = OperationalError("private SQL")
        response = self.post()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private", str(response.data))
        self.students.side_effect = None
        with patch.object(ReaderLookupThrottle, "rate", "1/min"):
            cache.clear()
            self.assertEqual(self.post().status_code, 200)
            self.assertEqual(self.post().status_code, 429)
