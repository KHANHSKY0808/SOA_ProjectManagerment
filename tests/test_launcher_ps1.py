"""Automated tests for start_all.ps1 and api-gateway/dev_gateway.py."""
import http.client
import os
from pathlib import Path
import py_compile
import subprocess
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER_PS1 = ROOT / "start_all.ps1"
GATEWAY_SCRIPT = ROOT / "api-gateway" / "dev_gateway.py"


class LauncherPs1Tests(unittest.TestCase):
    def test_launcher_ps1_exists(self):
        self.assertTrue(LAUNCHER_PS1.is_file(), "start_all.ps1 must exist at root")

    @unittest.skipUnless(os.name == "nt", "Windows PowerShell test")
    def test_launcher_ps1_dry_run_outputs_all_services(self):
        cmd = ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", str(LAUNCHER_PS1), "-DryRun"]
        proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, encoding="utf-8", errors="replace", timeout=15)
        self.assertEqual(proc.returncode, 0, f"DryRun failed: {proc.stderr}\n{proc.stdout}")

        output = proc.stdout
        self.assertIn("SOA API Gateway :8000", output)
        self.assertIn("SOA Auth Service :8001", output)
        self.assertIn("SOA Academic Service :8002", output)
        self.assertIn("SOA Regist Service :8003", output)
        self.assertIn("SOA Topic Service :8004", output)
        self.assertIn("SOA Frontend :5173", output)
        self.assertIn("ACADEMIC_DISCOVERY_ENABLED=false", output)
        self.assertIn("REGISTRATION_DISCOVERY_ENABLED=false", output)
        self.assertIn("AUTH_NAMES_DISCOVERY_ENABLED=false", output)
        self.assertIn("DRY RUN HOA", output)

    def test_service_env_files_exist_and_disable_discovery(self):
        for svc in ("auth-service", "academic-services", "regist-service", "topic-service"):
            env_file = ROOT / "services" / svc / ".env"
            self.assertTrue(env_file.is_file(), f"{svc} must have .env file")
            content = env_file.read_text(encoding="utf-8")
            self.assertIn("CONSUL_AUTO_REGISTER=false", content)
            if svc in ("academic-services", "regist-service", "topic-service"):
                self.assertIn("DISCOVERY_ENABLED=false", content)


class DevGatewayTests(unittest.TestCase):
    def test_gateway_compilation(self):
        self.assertTrue(GATEWAY_SCRIPT.is_file(), "dev_gateway.py must exist")
        py_compile.compile(str(GATEWAY_SCRIPT), doraise=True)

    def test_dev_gateway_health_docs_and_503(self):
        # Import and spin up dev gateway on a test port
        import sys
        sys.path.insert(0, str(ROOT / "api-gateway"))
        from dev_gateway import ThreadingHTTPServer, DevGatewayHandler

        test_port = 18000
        server = ThreadingHTTPServer(("127.0.0.1", test_port), DevGatewayHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.2)

        try:
            conn = http.client.HTTPConnection("127.0.0.1", test_port, timeout=3)

            # 1. Test /health/ -> 200 OK
            conn.request("GET", "/health/")
            resp = conn.getresponse()
            self.assertEqual(resp.status, 200)
            data = resp.read().decode("utf-8")
            self.assertIn("api-gateway-dev", data)

            # 2. Test /docs/ -> 200 OK (Swagger UI)
            conn.request("GET", "/docs/")
            resp = conn.getresponse()
            self.assertEqual(resp.status, 200)
            html = resp.read().decode("utf-8")
            self.assertIn("swagger-ui", html)

            # 3. Test /openapi.yaml -> 200 OK
            conn.request("GET", "/openapi.yaml")
            resp = conn.getresponse()
            self.assertEqual(resp.status, 200)
            yaml_content = resp.read().decode("utf-8")
            self.assertIn("openapi: 3.0.3", yaml_content)

            # 4. Test blocked internal auth -> 404
            conn.request("GET", "/auth/internal/v1/identities/")
            resp = conn.getresponse()
            self.assertEqual(resp.status, 404)
            resp.read()

            # 5. Test upstream route (when service is down returns 503, or 401 when running without auth)
            conn.request("GET", "/registrations/api/v1/available-topics/")
            resp = conn.getresponse()
            self.assertIn(resp.status, (503, 401))
            resp.read()

            conn.close()
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
