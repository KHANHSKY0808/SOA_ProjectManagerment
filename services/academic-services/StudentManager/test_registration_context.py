from types import SimpleNamespace
from unittest.mock import patch
from django.db import OperationalError
from django.test import SimpleTestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken
from registration_context import Student, Major


class RegistrationReferenceTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.authenticate()

    def authenticate(self, role=3, identity="SV001"):
        token = AccessToken()
        token["user_id"], token["role"] = identity, role
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    @patch.object(Major.objects, "filter")
    @patch.object(Student.objects, "filter")
    def test_self_text_identity_and_faculty(self, students, majors):
        students.return_value.first.return_value = SimpleNamespace(pk="SV001", major_id="M1")
        majors.return_value.values_list.return_value.first.return_value = "F1"
        result = self.client.get("/api/v1/registration-context/?student_id=other")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data, {"student_id": "SV001", "department_id": "F1"})
        students.assert_called_once_with(pk="SV001")
        majors.assert_called_once_with(pk="M1")

    @patch.object(Student.objects, "filter")
    def test_missing_student_and_storage_failure(self, students):
        students.return_value.first.return_value = None
        self.assertEqual(self.client.get("/api/v1/registration-context/").status_code, 403)
        students.side_effect = OperationalError("private SQL")
        result = self.client.get("/api/v1/registration-context/")
        self.assertEqual(result.status_code, 503)
        self.assertNotIn("private", str(result.data))

    @patch.object(Major.objects, "filter")
    def test_batch_missing_nullable_and_limit(self, majors):
        majors.return_value.values_list.return_value = [("M1", "F1"), ("M2", None)]
        result = self.client.post("/api/v1/major-departments/", {"major_ids": ["M1", "M2", "missing"]}, format="json")
        self.assertEqual(result.data, {"departments": {"M1": "F1", "M2": None, "missing": None}})
        majors.assert_called_once_with(pk__in=["M1", "M2", "missing"])
        self.assertEqual(self.client.post("/api/v1/major-departments/", {"major_ids": ["M"] * 101}, format="json").status_code, 400)

    def test_role_and_auth_denials(self):
        for role in (1, 2, "3", True, None):
            self.authenticate(role)
            self.assertEqual(self.client.get("/api/v1/registration-context/").status_code, 403)
            self.assertEqual(self.client.post("/api/v1/major-departments/", {}, format="json").status_code, 403)
        self.client.credentials()
        self.assertEqual(self.client.get("/api/v1/registration-context/").status_code, 401)
