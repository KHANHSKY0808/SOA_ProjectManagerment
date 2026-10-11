from unittest.mock import patch
from django.db import OperationalError
from django.test import SimpleTestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken
from .models import Topic


class RegistrationLookupTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.authenticate(3)

    def authenticate(self, role):
        token = AccessToken()
        token["user_id"], token["role"] = "SV001", role
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    @patch.object(Topic.objects, "filter")
    def test_open_topics_cursor_and_minimal_dto(self, topics):
        rows = [Topic(topic_id=f"T{i:03}", name="SOA", major_id="M1", status=2) for i in range(101)]
        topics.return_value.order_by.return_value.__getitem__.return_value = rows
        result = self.client.get("/api/v1/registration-topics/?after=T000")
        topics.assert_called_once_with(status=2, topic_id__gt="T000")
        self.assertEqual(len(result.data["results"]), 100)
        self.assertEqual(result.data["next_after"], "T099")
        self.assertEqual(set(result.data["results"][0]), {"topic_id", "name", "major_id", "status"})

    @patch.object(Topic.objects, "filter")
    def test_detail_closed_missing_and_failure(self, topics):
        topics.return_value.first.return_value = Topic(topic_id="DT001", name="SOA", major_id="M1", status=0)
        result = self.client.get("/api/v1/registration-topics/DT001/")
        self.assertEqual(result.data["status"], 0)
        topics.assert_called_once_with(pk="DT001")
        topics.return_value.first.return_value = None
        self.assertEqual(self.client.get("/api/v1/registration-topics/missing/").status_code, 404)
        topics.side_effect = OperationalError("private")
        self.assertEqual(self.client.get("/api/v1/registration-topics/").status_code, 503)

    def test_auth_roles_and_query_validation(self):
        self.assertEqual(self.client.get("/api/v1/registration-topics/?after=" + "x" * 256).status_code, 400)
        for role in (1, 2, "3", True, None):
            self.authenticate(role)
            self.assertEqual(self.client.get("/api/v1/registration-topics/").status_code, 403)
        self.client.credentials()
        self.assertEqual(self.client.get("/api/v1/registration-topics/").status_code, 401)
