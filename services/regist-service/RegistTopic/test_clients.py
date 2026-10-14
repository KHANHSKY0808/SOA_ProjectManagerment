from unittest.mock import patch
from urllib.error import HTTPError
from django.test import SimpleTestCase, override_settings
from rest_framework.exceptions import NotFound, PermissionDenied
from . import clients

CONFIG = {"DISCOVERY_ENABLED": False, "BASE_URL": "http://academic.test:8002", "TIMEOUT_SECONDS": 3}
TOPIC = {"topic_id": "T1", "major_id": "M1", "name": "SOA", "status": 2}


@override_settings(ACADEMIC_CLIENT=CONFIG, TOPIC_CLIENT={**CONFIG, "BASE_URL": "http://topic.test:8004"})
class ReferenceClientTests(SimpleTestCase):
    def setUp(self):
        self.academic = clients.AcademicClient("academic-service", "ACADEMIC_CLIENT")
        self.topic = clients.TopicClient("topic-service", "TOPIC_CLIENT")

    @patch.object(clients, "fetch_json")
    def test_failure_logs_identify_stage_without_credentials_or_private_values(self, fetch):
        for error in (TimeoutError("secret-token private-student"),
                      HTTPError("http://private-host", 401, "secret-token", {}, None)):
            fetch.side_effect = error
            client = clients.TopicClient("topic-service", "TOPIC_CLIENT")
            with self.assertLogs("RegistTopic.clients", level="WARNING") as logs:
                with self.assertRaises(clients.DependencyUnavailable):
                    client.topic("private-student", "Bearer secret-token", "lookup-123")
            output = str(logs.output)
            for value in ("service=topic-service", "operation=topic_detail", "stage=request", "request_id=lookup-123"):
                self.assertIn(value, output)
            self.assertIn("upstream_status=401" if isinstance(error, HTTPError) else "error=TimeoutError", output)
            for value in ("secret-token", "private-student", "private-host"):
                self.assertNotIn(value, output)
        fetch.side_effect = None
        fetch.return_value = {"private-student": "secret-token"}
        with self.assertLogs("RegistTopic.clients", level="WARNING") as logs:
            with self.assertRaises(clients.DependencyUnavailable):
                self.academic.context("private-student", "Bearer secret-token", "lookup-123")
        self.assertIn("operation=context stage=validation", str(logs.output))
        self.assertNotIn("secret-token", str(logs.output))
        self.assertNotIn("private-student", str(logs.output))
        self.academic.open_until = float("inf")
        with self.assertLogs("RegistTopic.clients", level="WARNING") as logs:
            with self.assertRaises(clients.DependencyUnavailable):
                self.academic.context("private-student", "Bearer secret-token", "unsafe\nvalue")
        self.assertIn("stage=circuit request_id=invalid", str(logs.output))
        self.assertNotIn("unsafe", str(logs.output))

    @patch.object(clients, "fetch_json")
    def test_student_names_contract_and_invalid_responses(self, fetch):
        fetch.return_value = {"student_names": {"S1": "An"}, "names_unavailable": False}
        self.assertEqual(self.academic.student_names(["S1", "S1"], "Bearer t", "id"), fetch.return_value)
        fetch.assert_called_once_with("http://academic.test:8002/api/v1/student-display-names/",
            {"Authorization": "Bearer t", "X-Request-ID": "id"}, 3, {"student_ids": ["S1"]})
        for payload in ({}, {"student_names": {}, "names_unavailable": False},
                        {"student_names": {"S1": 123}, "names_unavailable": False},
                        {"student_names": {"S1": None}, "names_unavailable": "false"}):
            fetch.return_value = payload
            with self.assertRaises(clients.DependencyUnavailable):
                clients.AcademicClient("academic-service", "ACADEMIC_CLIENT").student_names(["S1"], "Bearer t", "id")

    @patch.object(clients, "fetch_json")
    def test_static_contracts_and_deduplicated_batches(self, fetch):
        fetch.return_value = {"student_id": "SV1", "department_id": "F1"}
        self.academic.context("SV1", "Bearer test", "request-1")
        fetch.assert_called_once_with("http://academic.test:8002/api/v1/registration-context/",
                                      {"Authorization": "Bearer test", "X-Request-ID": "request-1"}, 3, None)
        fetch.return_value = {"departments": {"M1": "F1", "M2": None}}
        self.assertEqual(self.academic.departments(["M1", "M1", "M2"], "Bearer t", "id"), {"M1": "F1", "M2": None})
        self.assertEqual(fetch.call_args.args[3], {"major_ids": ["M1", "M2"]})
        fetch.return_value = TOPIC
        self.assertEqual(self.topic.topic("T1", "Bearer t", "id"), TOPIC)
        fetch.return_value = {"results": [TOPIC], "next_after": None}
        self.assertEqual(self.topic.page("", "Bearer t", "id")["results"], [TOPIC])

    @patch.object(clients, "fetch_json")
    def test_management_topic_ownership_contract(self, fetch):
        fetch.return_value = {"topic_id": "T #", "advisor_id": "GV1"}
        self.assertEqual(self.topic.management_topic("T #", "Bearer t", "rid"), fetch.return_value)
        fetch.assert_called_once_with("http://topic.test:8004/api/v1/topics/T%20%23/",
                                      {"Authorization": "Bearer t", "X-Request-ID": "rid"}, 3, None)
        for payload in ({}, {"topic_id": "T #"}, {"topic_id": "other", "advisor_id": "GV1"},
                        {"topic_id": "T #", "advisor_id": 1}):
            fetch.return_value = payload
            with self.assertRaises(clients.DependencyUnavailable):
                clients.TopicClient("topic-service", "TOPIC_CLIENT").management_topic("T #", "Bearer t", "rid")

    @override_settings(ACADEMIC_CLIENT={**CONFIG, "DISCOVERY_ENABLED": True},
                       CONSUL={"URL": "http://registry:8500", "TOKEN": "acl"})
    @patch.object(clients, "fetch_json")
    def test_discovery_healthy_instance_and_separate_credentials(self, fetch):
        fetch.side_effect = [[{"Service": {"Service": "academic-service", "Address": "::1", "Port": 8002},
                               "Checks": [{"Status": "passing"}]}], {"student_id": "SV1", "department_id": "F1"}]
        self.academic.context("SV1", "Bearer user", "id")
        self.assertEqual(fetch.call_args_list[0].args, ("http://registry:8500/v1/health/service/academic-service?passing=true",
                                                      {"X-Consul-Token": "acl"}, 3))
        self.assertEqual(fetch.call_args_list[1].args[0], "http://[::1]:8002/api/v1/registration-context/")
        self.assertEqual(fetch.call_args_list[1].args[1], {"Authorization": "Bearer user", "X-Request-ID": "id"})

    @override_settings(ACADEMIC_CLIENT={**CONFIG, "DISCOVERY_ENABLED": True})
    @patch.object(clients, "fetch_json")
    def test_registry_failures_never_fall_back(self, fetch):
        for payload in ([], {}, [{"Service": {}}], [{"Service": {"Service": "academic-service", "Address": "bad/path", "Port": 8002},
                                                     "Checks": [{"Status": "passing"}]}]):
            fetch.reset_mock()
            fetch.return_value = payload
            with self.assertRaises(clients.DependencyUnavailable):
                clients.AcademicClient("academic-service", "ACADEMIC_CLIENT").context("SV1", "Bearer t", "id")
            self.assertEqual(fetch.call_count, 1)

    @patch.object(clients, "fetch_json")
    def test_expected_errors_and_upstream_failures(self, fetch):
        for code in (401, 403, 404, 500, 302):
            fetch.side_effect = HTTPError("http://service", code, "private details", {}, None)
            expected = NotFound if code == 404 else clients.DependencyUnavailable
            with self.assertRaises(expected):
                clients.TopicClient("topic-service", "TOPIC_CLIENT").topic("T1", "Bearer t", "id")
        fetch.side_effect = HTTPError("http://academic", 403, "private", {}, None)
        with self.assertRaises(PermissionDenied):
            self.academic.context("SV1", "Bearer t", "id")

    @patch.object(clients, "fetch_json")
    def test_invalid_dtos_fail_closed(self, fetch):
        for payload in (None, [], {}, {"student_id": "other", "department_id": "F1"}, {"student_id": "SV1", "department_id": None}):
            fetch.return_value = payload
            with self.assertRaises(clients.DependencyUnavailable):
                clients.AcademicClient("academic-service", "ACADEMIC_CLIENT").context("SV1", "t", "id")
        for payload in ({}, {key: value for key, value in TOPIC.items() if key != "status"},
                        {**TOPIC, "topic_id": "wrong"}, {**TOPIC, "status": True}, {**TOPIC, "major_id": None}):
            fetch.return_value = payload
            with self.assertRaises(clients.DependencyUnavailable):
                clients.TopicClient("topic-service", "TOPIC_CLIENT").topic("T1", "t", "id")
        for values in ({}, {"M1": 123}, {"M1": "F1", "extra": "F1"}):
            fetch.return_value = {"departments": values}
            with self.assertRaises(clients.DependencyUnavailable):
                clients.AcademicClient("academic-service", "ACADEMIC_CLIENT").departments(["M1"], "t", "id")

    @patch.object(clients, "fetch_json")
    def test_page_order_closed_status_and_cursor_validation(self, fetch):
        for payload in ({}, {"results": [TOPIC, TOPIC], "next_after": None},
                        {"results": [{**TOPIC, "status": 0}], "next_after": None},
                        {"results": [{**TOPIC, "status": 1}], "next_after": None},
                        {"results": [], "next_after": "T1"}, {"results": [TOPIC], "next_after": "T1"}):
            fetch.return_value = payload
            with self.assertRaises(clients.DependencyUnavailable):
                clients.TopicClient("topic-service", "TOPIC_CLIENT").page("", "t", "id")

    @patch.object(clients.time, "monotonic", return_value=100)
    @patch.object(clients, "fetch_json", side_effect=TimeoutError("private transport"))
    def test_timeout_circuit_and_recovery(self, fetch, clock):
        for _ in range(4):
            with self.assertRaises(clients.DependencyUnavailable) as caught:
                self.topic.topic("T1", "t", "id")
            self.assertNotIn("private", str(caught.exception))
        self.assertEqual(fetch.call_count, 3)
        clock.return_value = 111
        fetch.side_effect = None
        fetch.return_value = TOPIC
        self.topic.topic("T1", "t", "id")
        self.assertEqual((self.topic.failures, self.topic.open_until), (0, 0))

    @patch.object(clients, "build_opener")
    def test_transport_bounds_encoding_timeout_and_redirect_denial(self, opener):
        response = opener.return_value.open.return_value.__enter__.return_value
        response.read.return_value = b'{"ok":true}'
        self.assertEqual(clients.fetch_json("http://service", {}, 3, {"major_ids": ["M1"]}), {"ok": True})
        self.assertEqual(opener.return_value.open.call_args.kwargs["timeout"], 3)
        sent = opener.return_value.open.call_args.args[0]
        self.assertEqual(sent.get_method(), "POST")
        self.assertIsInstance(opener.call_args.args[0], clients.NoRedirect)
        self.assertIsNone(clients.NoRedirect().redirect_request(None, None, 302, "", {}, "http://other"))
        response.read.assert_called_with(262145)
        response.read.return_value = b"x" * 262145
        with self.assertRaises(ValueError):
            clients.fetch_json("http://service", {}, 3)

    def test_address_validation(self):
        self.assertEqual(clients.instance_url("service.local", 8002), "http://service.local:8002")
        for address, port in (("bad/path", 8002), ("service", True), ("service", 0), ("", 8002)):
            with self.assertRaises(ValueError):
                clients.instance_url(address, port)
