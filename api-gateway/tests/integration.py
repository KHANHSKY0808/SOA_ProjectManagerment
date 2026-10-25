"""Run inside the gateway image; isolated mock registry/backends, no real Consul."""
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import socket
from pathlib import Path
import subprocess
import sys
import threading
import time
import unittest

STATE = {"healthy": True, "registry_error": False, "port": None, "writes": [], "address": "127.0.0.1"}


class Backend(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def handle_request(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode()
        if self.command == "POST":
            STATE["writes"].append(self.server.server_port)
        payload = json.dumps({"path": self.path, "body": body,
                              "authorization": self.headers.get("Authorization"),
                              "request_id": self.headers.get("X-Request-ID"),
                              "port": self.server.server_port}).encode()
        self.send_response(502 if self.path == "/fail-write" else 200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    do_GET = handle_request
    do_POST = handle_request


class Registry(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(503 if STATE["registry_error"] else 200)
        self.end_headers()
        name = self.path.split("/")[-1].split("?")[0]
        ports = STATE["port"] if isinstance(STATE["port"], list) else [STATE["port"]]
        result = [{"Service": {"Service": name, "Address": STATE["address"], "Port": port},
                   "Node": {"Address": "127.0.0.1"}, "Checks": [{"Status": "passing"}]}
                  for port in ports] if STATE["healthy"] else []
        self.wfile.write(json.dumps(result).encode())


def server(handler):
    result = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=result.serve_forever, daemon=True).start()
    return result


def request_raw(path, method="GET", body=None, headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", 80, timeout=2)
    try:
        connection.request(method, path, body, headers or {})
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


def request(path, method="GET", body=None, headers=None):
    status, _, payload = request_raw(path, method, body, headers)
    return status, json.loads(payload)


def eventually(check, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if check():
                return
        except (OSError, ValueError):
            pass
        time.sleep(0.1)
    raise AssertionError("Expected routing state did not arrive")


class GatewayIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Disposable container only: reproduce a host with A and unreachable AAAA.
        with Path("/etc/hosts").open("a") as hosts:
            hosts.write("\n127.0.0.1 dualstack.gateway.test\nfd00::123 dualstack.gateway.test\n")
        cls.a = server(Backend)
        cls.b = server(Backend)
        cls.registry = server(Registry)
        STATE["port"] = cls.a.server_port
        STATE["registry_error"] = True
        environment = dict(os.environ, CONSUL_URL=f"http://127.0.0.1:{cls.registry.server_port}",
                           CONSUL_REFRESH_SECONDS="0.2", CONSUL_TIMEOUT_SECONDS="0.2",
                           CONSUL_STALE_TTL_SECONDS="1", GATEWAY_UPSTREAM_IP_FAMILY="ipv4",
                           GATEWAY_DNS_TIMEOUT_SECONDS="1")
        cls.worker = subprocess.Popen(["/opt/gateway/entrypoint.sh"], env=environment,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        eventually(lambda: request("/health/")[0] == 200)
        if request("/auth/health/")[0] != 503:
            raise AssertionError("Bootstrap must fail closed when registry is unavailable")
        cls.verify_documentation()
        STATE["registry_error"] = False
        eventually(lambda: request("/auth/health/")[0] == 200)

    @classmethod
    def tearDownClass(cls):
        cls.worker.terminate()
        cls.worker.wait(timeout=15)
        for item in [cls.a, cls.b, cls.registry]:
            item.shutdown()
            item.server_close()

    def setUp(self):
        STATE.update(healthy=True, registry_error=False, port=self.a.server_port, writes=[], address="127.0.0.1")
        eventually(lambda: request("/auth/probe")[1].get("port") == self.a.server_port)

    @classmethod
    def verify_documentation(cls):
        for path, content_type, marker in [
            ("/swagger/", "text/html", b"Swagger"),
            ("/swagger/swagger-config.js", "application/javascript", b"persistAuthorization: false"),
            ("/swagger/vendor/swagger-ui-bundle.js", "application/javascript", b"SwaggerUIBundle"),
            ("/swagger/vendor/swagger-ui.css", "text/css", b"swagger-ui"),
            ("/openapi.json", "application/json", b'"openapi": "3.0.3"'),
        ]:
            status, headers, body = request_raw(path)
            if status != 200 or not headers.get("Content-Type", "").startswith(content_type) or marker not in body:
                raise AssertionError(f"Invalid documentation response at {path}: {status}, {headers}")
            if headers.get("X-Content-Type-Options") != "nosniff":
                raise AssertionError(f"Missing content type protection at {path}")

    def test_documentation_after_discovery_reload_and_without_backends(self):
        self.verify_documentation()
        STATE["healthy"] = False
        eventually(lambda: request("/auth/login/")[0] == 503)
        self.verify_documentation()
        self.assertEqual(STATE["writes"], [])

    def test_documentation_redirect_head_methods_and_unknown_assets(self):
        status, headers, _ = request_raw("/swagger")
        self.assertEqual(status, 308)
        self.assertTrue(headers["Location"].endswith("/swagger/"))
        self.assertEqual(request_raw("/openapi.json", "HEAD")[0], 200)
        self.assertEqual(request_raw("/swagger/", "HEAD")[2], b"")
        for path in ["/swagger/", "/openapi.json", "/swagger/vendor/swagger-ui.css"]:
            self.assertEqual(request_raw(path, "POST", "ignored")[0], 403)
        self.assertEqual(request_raw("/swagger/vendor/missing.js")[0], 404)
        self.assertEqual(request_raw("/swagger/missing")[0], 404)
        self.assertEqual(STATE["writes"], [])

    def test_all_prefixes_preserve_query_and_authorization(self):
        for prefix in ["auth", "academic", "registrations", "topics"]:
            status, payload = request(f"/{prefix}/api/items/?page=2", headers={"Authorization": "Bearer fake-test-token"})
            self.assertEqual(status, 200)
            self.assertEqual(payload["path"], "/api/items/?page=2")
            self.assertEqual(payload["authorization"], "Bearer fake-test-token")
            self.assertTrue(payload["request_id"])

    def test_instance_port_changes_without_restart(self):
        STATE["port"] = self.b.server_port
        eventually(lambda: request("/academic/api/items/")[1].get("port") == self.b.server_port)

    def test_multiple_instances_and_no_write_replay(self):
        STATE["port"] = [self.a.server_port, self.b.server_port]
        seen = set()
        def both():
            seen.add(request("/auth/probe")[1].get("port"))
            return seen == {self.a.server_port, self.b.server_port}
        eventually(both)
        status, _ = request("/auth/fail-write", "POST", "payload")
        self.assertEqual(status, 503)
        self.assertEqual(len(STATE["writes"]), 1)

    def test_no_healthy_instance_returns_json_503(self):
        STATE["healthy"] = False
        eventually(lambda: request("/auth/login/")[0] == 503)
        self.assertEqual(request("/health/")[0], 200)

    def test_registry_outage_expires_cache_then_recovers(self):
        STATE["registry_error"] = True
        eventually(lambda: request("/academic/api/items/")[0] == 503)
        STATE["registry_error"] = False
        eventually(lambda: request("/academic/api/items/")[0] == 200)

    def test_unknown_route_is_safe_404(self):
        self.assertEqual(request("/not-a-service/"), (404, {"detail": "Not found."}))

    def test_internal_identity_routes_never_reach_auth(self):
        for path in ["/auth/internal", "/auth/internal/v1/identities/students/",
                     "/auth/internal/v1/identity-profiles/lecturers/", "/auth/%69nternal/v1/identities/students/"]:
            for method in ["GET", "POST", "DELETE"]:
                self.assertEqual(request(path, method)[0], 404)

    def test_dual_stack_hostname_never_routes_to_unreachable_ipv6(self):
        families = {entry[0] for entry in socket.getaddrinfo("dualstack.gateway.test", None, type=socket.SOCK_STREAM)}
        self.assertEqual(families, {socket.AF_INET, socket.AF_INET6})
        STATE.update(address="dualstack.gateway.test", port=self.b.server_port)
        eventually(lambda: request("/academic/probe")[1].get("port") == self.b.server_port)
        config = Path("/etc/nginx/nginx.conf").read_text()
        self.assertIn(f"server 127.0.0.1:{self.b.server_port};", config)
        self.assertNotIn("dualstack.gateway.test", config)
        self.assertNotIn("fd00::123", config)
        for _ in range(40):
            status, payload = request("/academic/probe")
            self.assertEqual(status, 200)
            self.assertEqual(payload["port"], self.b.server_port)

    def test_ipv6_only_registry_instance_is_unavailable_in_ipv4_mode(self):
        STATE["address"] = "fd00::123"
        eventually(lambda: request("/academic/probe")[0] == 503)
        STATE["address"] = "127.0.0.1"
        eventually(lambda: request("/academic/probe")[0] == 200)


if __name__ == "__main__":
    unittest.main()
