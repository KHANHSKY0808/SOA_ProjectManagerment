"""Automated tests for Swagger testing files and scenario documentation."""
import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SWAGGER_DIR = ROOT / "swagger"


class SwaggerFilesTests(unittest.TestCase):
    def setUp(self):
        self.yaml_path = SWAGGER_DIR / "openapi.yaml"
        self.html_path = SWAGGER_DIR / "index.html"
        self.doc_path = SWAGGER_DIR / "KICH_BAN_KIEM_THU.md"

    def test_all_three_files_exist_and_non_empty(self):
        self.assertTrue(self.yaml_path.is_file(), "swagger/openapi.yaml must exist")
        self.assertTrue(self.html_path.is_file(), "swagger/index.html must exist")
        self.assertTrue(self.doc_path.is_file(), "swagger/KICH_BAN_KIEM_THU.md must exist")

        self.assertGreater(self.yaml_path.stat().st_size, 5000, "openapi.yaml should contain full spec")
        self.assertGreater(self.html_path.stat().st_size, 1000, "index.html should contain Swagger UI")
        self.assertGreater(self.doc_path.stat().st_size, 2000, "KICH_BAN_KIEM_THU.md should contain full scenario")

    def test_openapi_yaml_structure_and_routes(self):
        content = self.yaml_path.read_text(encoding="utf-8")
        self.assertTrue(content.startswith("openapi: 3.0.3"))
        self.assertIn("title: Hệ Thống Quản Lý Đồ Án Tốt Nghiệp", content)
        self.assertIn("http://localhost:8000", content)

        # Core services tags
        self.assertIn("1. Auth Service (:8001)", content)
        self.assertIn("2. Academic Service (:8002)", content)
        self.assertIn("3. Topic Service (:8004)", content)
        self.assertIn("4. Registration Service (:8003)", content)

        # Essential scenario endpoints
        self.assertIn("/auth/login/:", content)
        self.assertIn("/auth/token/refresh/:", content)
        self.assertIn("/auth/me/:", content)
        self.assertIn("/academic/api/departments/:", content)
        self.assertIn("/academic/api/majors/:", content)
        self.assertIn("/academic/api/students/:", content)
        self.assertIn("/topics/api/v1/topics/:", content)
        self.assertIn("/registrations/api/v1/available-topics/:", content)
        self.assertIn("/registrations/api/v1/registrations/:", content)

        # Topic new schema columns
        self.assertIn("req_GPA", content)
        self.assertIn("studentQuota", content)
        self.assertIn("patch:", content)
        self.assertIn("/registrations/api/v1/topics/{topic_id}/registrations/{registration_id}/point/:", content)

        # Bearer Auth security scheme
        self.assertIn("bearerAuth:", content)
        self.assertIn("scheme: bearer", content)
        self.assertIn("bearerFormat: JWT", content)

    def test_swagger_ui_html_configuration(self):
        content = self.html_path.read_text(encoding="utf-8")
        self.assertIn("<!DOCTYPE html>", content)
        self.assertIn("SwaggerUIBundle", content)
        self.assertIn("swagger-ui", content)
        self.assertIn("openapi.yaml", content)
        self.assertIn("persistAuthorization: true", content)
        self.assertIn("tryItOutEnabled: true", content)

    def test_kich_ban_kiem_thu_contains_six_steps_and_no_duplicates(self):
        content = self.doc_path.read_text(encoding="utf-8")

        # Must contain all 6 scenario steps
        self.assertIn("BƯỚC 1: Admin đăng nhập", content)
        self.assertIn("BƯỚC 2: Giảng viên tạo đề tài", content)
        self.assertIn("BƯỚC 3: Admin duyệt", content)
        self.assertIn("BƯỚC 4: Sinh viên xem đề tài mở và đăng ký", content)
        self.assertIn("BƯỚC 5: Giảng viên xem danh sách đăng ký", content)
        self.assertIn("BƯỚC 6: Consul UI", content)
        self.assertIn("503 Service Unavailable", content)

        # Must contain the new columns in scenario payloads
        self.assertIn('"req_GPA": 2.5', content)
        self.assertIn('"studentQuota": 2', content)

        # Must not contain duplicate block headers
        step1_count = content.count("BƯỚC 1: Admin đăng nhập")
        self.assertEqual(step1_count, 1, "Scenario steps must not be duplicated")

    def test_swagger_md_contains_spec_and_scenario(self):
        swagger_md = ROOT / "swagger.md"
        self.assertTrue(swagger_md.is_file(), "swagger.md must exist in root")
        content = swagger_md.read_text(encoding="utf-8")
        self.assertIn("openapi: 3.0.3", content)
        self.assertIn("req_GPA", content)
        self.assertIn("studentQuota", content)
        self.assertIn("KỊCH BẢN DEMO 1: LUỒNG NGHIỆP VỤ CHÍNH", content)


if __name__ == "__main__":
    unittest.main()

