import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from .consul import ConsulClient, ConsulServiceSettings


class ConsulClientTests(SimpleTestCase):
    def setUp(self):
        self.config = ConsulServiceSettings(
            base_url="http://localhost:8500",
            service_name="auth-service",
            instance_id="auth-service-8001",
            address="host.docker.internal",
            port=8001,
            health_check_url="http://host.docker.internal:8001/health/",
            token="test-token",
            timeout_seconds=3,
        )

    @patch("authentication.consul.urlopen")
    def test_register_sends_consul_service_definition(self, mocked_urlopen):
        response = MagicMock(status=200)
        mocked_urlopen.return_value.__enter__.return_value = response

        ConsulClient(self.config).register()

        request = mocked_urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(request.full_url, "http://localhost:8500/v1/agent/service/register")
        self.assertEqual(request.get_method(), "PUT")
        self.assertEqual(request.get_header("X-consul-token"), "test-token")
        self.assertEqual(payload["Name"], "auth-service")
        self.assertEqual(payload["Port"], 8001)
        self.assertEqual(payload["Check"]["HTTP"], "http://host.docker.internal:8001/health/")

    @patch("authentication.consul.urlopen")
    def test_deregister_uses_service_instance_id(self, mocked_urlopen):
        response = MagicMock(status=200)
        mocked_urlopen.return_value.__enter__.return_value = response

        ConsulClient(self.config).deregister()

        request = mocked_urlopen.call_args.args[0]
        self.assertEqual(
            request.full_url,
            "http://localhost:8500/v1/agent/service/deregister/auth-service-8001",
        )
        self.assertEqual(request.get_method(), "PUT")

class PlaintextLoginTests(SimpleTestCase):
    def setUp(self):
        from rest_framework.test import APIClient
        from .models import Users

        self.client = APIClient()
        self.user = Users(
            userid="test-student", email="student@example.com", password="test-password",
            firstname="An", lastname="Nguyen", gender=1, dateofbirth=None,
            phone="0900000000", role=1, status=1, createdat=None, updatedat=None,
        )
        self.lookup = patch("authentication.views.Users.objects.get").start()
        self.addCleanup(patch.stopall)
        self.lookup.side_effect = self.find_user

    def find_user(self, **criteria):
        from .models import Users

        if criteria in ({"email": self.user.email}, {"userid": self.user.userid}):
            return self.user
        raise Users.DoesNotExist

    def login(self, **payload):
        return self.client.post("/login/", payload, format="json")

    def test_login_with_each_identifier_issues_signed_tokens(self):
        from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

        for field, value in [("identifier", self.user.userid),
                             ("identifier", self.user.email),
                             ("email", self.user.email),
                             ("userid", self.user.userid)]:
            with self.subTest(field=field, value=value):
                response = self.login(**{field: value, "password": self.user.password})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["token_type"], "Bearer")
                self.assertEqual(response.data["user"]["user_id"], self.user.userid)
                self.assertNotIn("password", response.data["user"])
                self.assertNotIn(self.user.password, response.content.decode())
                access = AccessToken(response.data["access"])
                self.assertEqual(access["exp"] - access["iat"], 1800)
                for token in [AccessToken(response.data["access"]),
                              RefreshToken(response.data["refresh"])]:
                    self.assertEqual(token["user_id"], self.user.userid)
                    self.assertEqual(token["email"], self.user.email)
                    self.assertEqual(token["role"], self.user.role)
                    self.assertNotIn("password", token.payload)

    def test_id_lookup_falls_back_after_email_lookup(self):
        response = self.login(userid=self.user.userid, password=self.user.password)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.lookup.call_args_list[0].kwargs, {"email": self.user.userid})
        self.assertEqual(self.lookup.call_args_list[1].kwargs, {"userid": self.user.userid})

    def test_wrong_password_and_unknown_user_return_same_error(self):
        for userid, password in [(self.user.userid, "incorrect"),
                                 ("missing-user", self.user.password)]:
            with self.subTest(userid=userid):
                response = self.login(userid=userid, password=password)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.data, {"detail": "Invalid email or password."})

    def test_password_comparison_is_exact_and_supports_unicode(self):
        self.user.password = "  m\u1eadt-kh\u1ea9u  "
        response = self.login(userid=self.user.userid, password=self.user.password)
        self.assertEqual(response.status_code, 200)
        for value in [self.user.password.strip(), self.user.password.upper()]:
            with self.subTest(value=value):
                self.assertEqual(self.login(userid=self.user.userid, password=value).status_code, 401)

    def test_stored_hash_is_not_verified(self):
        from django.contrib.auth.hashers import make_password

        self.user.password = make_password("original-password")
        response = self.login(userid=self.user.userid, password="original-password")
        self.assertEqual(response.status_code, 401)

    def test_missing_and_invalid_fields_rejected_before_lookup(self):
        for payload in [{}, {"userid": self.user.userid}, {"password": "test"},
                        {"userid": self.user.userid, "password": ""},
                        {"email": "invalid-email", "password": "test"}]:
            with self.subTest(payload=payload):
                self.lookup.reset_mock()
                self.assertEqual(self.login(**payload).status_code, 400)
                self.lookup.assert_not_called()

    def test_login_tokens_work_for_refresh_and_profile(self):
        from rest_framework_simplejwt.tokens import AccessToken

        login = self.login(userid=self.user.userid, password=self.user.password)
        refresh = self.client.post("/token/refresh/", {"refresh": login.data["refresh"]}, format="json")
        self.assertEqual(refresh.status_code, 200)
        access = AccessToken(refresh.data["access"])
        self.assertEqual(access["exp"] - access["iat"], 1800)
        self.assertEqual(access["user_id"], self.user.userid)
        self.assertEqual(access["role"], 1)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.data['access']}")
        profile = self.client.get("/me/")
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.data["user_id"], self.user.userid)
        self.assertNotIn("password", profile.data)

    def test_profile_requires_valid_access_token(self):
        self.assertEqual(self.client.get("/me/").status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid-token")
        self.assertEqual(self.client.get("/me/").status_code, 401)

    def test_access_token_is_accepted_before_expiry_and_rejected_at_expiry(self):
        from datetime import datetime, timezone

        from rest_framework_simplejwt.tokens import AccessToken

        login = self.login(userid=self.user.userid, password=self.user.password)
        access = AccessToken(login.data["access"])
        issued_at = datetime.fromtimestamp(access["iat"], tz=timezone.utc)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        with patch("jwt.api_jwt.datetime") as clock:
            clock.now.return_value = issued_at + timedelta(minutes=29, seconds=59)
            self.assertEqual(self.client.get("/me/").status_code, 200)
            clock.now.return_value = issued_at + timedelta(minutes=30)
            self.assertEqual(self.client.get("/me/").status_code, 401)

    def test_refresh_rejects_invalid_token_and_missing_user(self):
        response = self.client.post("/token/refresh/", {"refresh": "invalid-token"}, format="json")
        self.assertEqual(response.status_code, 401)
        login = self.login(userid=self.user.userid, password=self.user.password)
        from .models import Users
        self.lookup.side_effect = Users.DoesNotExist
        response = self.client.post("/token/refresh/", {"refresh": login.data["refresh"]}, format="json")
        self.assertEqual(response.status_code, 401)
