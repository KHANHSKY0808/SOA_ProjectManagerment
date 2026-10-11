import json
from io import BytesIO
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError
from django.test import SimpleTestCase, override_settings
from .clients import RegistrationCleanupClient, DependencyUnavailable

CONFIG = {"DISCOVERY_ENABLED": False, "BASE_URL": "http://regist.test:8003", "TIMEOUT_SECONDS": 2}


@override_settings(REGISTRATION_CLIENT=CONFIG)
class RegistrationCleanupClientTests(SimpleTestCase):
    def response(self, payload, status=200):
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = status
        response.read.return_value = json.dumps(payload).encode()
        return response

    @patch("topic_manager.clients.build_opener")
    def test_encoded_delete_forwarded_headers_timeout_and_no_retry(self, opener):
        opener.return_value.open.return_value = self.response({"topic_id": "T #?", "deleted_count": 3})
        self.assertEqual(RegistrationCleanupClient().purge("T #?", "Bearer manager", "request-1"), 3)
        args, kwargs = opener.return_value.open.call_args
        request = args[0]
        self.assertEqual(request.full_url, "http://regist.test:8003/api/v1/topics/T%20%23%3F/registrations/")
        self.assertEqual(request.method, "DELETE")
        self.assertIsNone(request.data)
        self.assertEqual(request.get_header("Authorization"), "Bearer manager")
        self.assertEqual(request.get_header("X-request-id"), "request-1")
        self.assertEqual(kwargs["timeout"], 2)
        opener.return_value.open.assert_called_once()

    @patch("topic_manager.clients.build_opener")
    def test_failure_invalid_dto_and_http_errors_are_safe_without_retries(self, opener):
        for payload in ({"topic_id": "other", "deleted_count": 1}, {"topic_id": "T", "deleted_count": True},
                        {"topic_id": "T", "deleted_count": -1}, []):
            opener.return_value.open.return_value = self.response(payload)
            with self.assertRaises(DependencyUnavailable):
                RegistrationCleanupClient().purge("T", "Bearer manager", "r")
        for error in (TimeoutError("private"), URLError("private"),
                      HTTPError("http://private", 403, "private", {}, BytesIO(b"private")),
                      HTTPError("http://private", 302, "private", {}, BytesIO(b"private"))):
            opener.return_value.open.reset_mock()
            opener.return_value.open.side_effect = error
            with self.assertRaises(DependencyUnavailable) as caught:
                RegistrationCleanupClient().purge("T", "Bearer manager", "r")
            self.assertNotIn("private", str(caught.exception))
            opener.return_value.open.assert_called_once()

    @override_settings(REGISTRATION_CLIENT={**CONFIG, "DISCOVERY_ENABLED": True},
                       CONSUL={"URL": "http://registry:8500", "TOKEN": "acl"})
    @patch("topic_manager.clients.fetch_json")
    @patch("topic_manager.clients.build_opener")
    def test_discovers_only_healthy_regist_service_no_static_fallback(self, opener, fetch):
        fetch.return_value = [{"Service": {"Service": "regist-service", "Address": "127.0.0.1", "Port": 8003},
                               "Checks": [{"Status": "passing"}]}]
        opener.return_value.open.return_value = self.response({"topic_id": "T", "deleted_count": 0})
        RegistrationCleanupClient().purge("T", "Bearer manager", "r")
        self.assertEqual(fetch.call_args.args, ("http://registry:8500/v1/health/service/regist-service?passing=true",
                                              {"X-Consul-Token": "acl"}, 2))
        self.assertEqual(opener.return_value.open.call_args.args[0].full_url,
                         "http://127.0.0.1:8003/api/v1/topics/T/registrations/")
        for payload in ([], [{"Service": {"Service": "regist-service", "Address": "127.0.0.1", "Port": 8003},
                              "Checks": [{"Status": "critical"}]}]):
            fetch.return_value = payload
            opener.return_value.open.reset_mock()
            with self.assertRaises(DependencyUnavailable):
                RegistrationCleanupClient().purge("T", "Bearer manager", "r")
            opener.return_value.open.assert_not_called()


    @patch("topic_manager.clients.build_opener")
    def test_non200_oversized_and_non_json_responses_are_unconfirmed(self, opener):
        for body, status in ((b"{}", 204), (b"x" * 4097, 200), (b"not-json", 200)):
            response = self.response({}, status)
            response.read.return_value = body
            opener.return_value.open.return_value = response
            with self.assertRaises(DependencyUnavailable):
                RegistrationCleanupClient().purge("T", "Bearer manager", "r")

    def test_registration_configuration_defaults_overrides_and_invalid_timeouts(self):
        import os
        import subprocess
        import sys
        from pathlib import Path
        settings_path = Path(__file__).resolve().parents[1] / "config" / "settings.py"
        code = ("import json, runpy; " + f"config=runpy.run_path({str(settings_path)!r}); "
                + "print(json.dumps(config['REGISTRATION_CLIENT']))")
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith("REGISTRATION_")}
        environment["PYTHON_DOTENV_DISABLED"] = "1"
        result = subprocess.run([sys.executable, "-B", "-c", code], env=environment,
                                capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout), {"DISCOVERY_ENABLED": True,
                         "BASE_URL": "http://localhost:8003", "TIMEOUT_SECONDS": 2})
        environment.update(REGISTRATION_DISCOVERY_ENABLED="false",
                           REGISTRATION_BASE_URL="http://regist.test:8003", REGISTRATION_TIMEOUT_SECONDS="1.5")
        result = subprocess.run([sys.executable, "-B", "-c", code], env=environment,
                                capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout), {"DISCOVERY_ENABLED": False,
                         "BASE_URL": "http://regist.test:8003", "TIMEOUT_SECONDS": 1.5})
        for value in ("nan", "inf", "0", "-1", "11"):
            environment["REGISTRATION_TIMEOUT_SECONDS"] = value
            result = subprocess.run([sys.executable, "-B", "-c", code], env=environment,
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("REGISTRATION_TIMEOUT_SECONDS", result.stderr)
