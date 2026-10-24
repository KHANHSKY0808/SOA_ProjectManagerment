"""Exercise the Windows launcher without starting any application servers."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SERVICES = {"auth-service": 8001, "academic-services": 8002,
            "regist-service": 8003, "topic-service": 8004}


@unittest.skipUnless(os.name == "nt", "Windows cmd launcher")
class StartServicesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="SOA launcher test ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project with spaces & symbols!"
        self.root.mkdir()
        shutil.copyfile(ROOT / "start-services.bat", self.root / "start-services.bat")
        for service in SERVICES:
            for filename in ("venv/Scripts/python.exe", "manage.py"):
                path = self.root / "services" / service / filename
                path.parent.mkdir(parents=True, exist_ok=True)
                # Not executable: dry-run must never attempt to invoke these fixtures.
                path.write_text("not an executable", encoding="ascii")
        for filename in ("package.json", "node_modules/.bin/vite.cmd"):
            path = self.root / "fe" / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("invalid fixture", encoding="ascii")
        self.bin = Path(self.temp.name) / "tools"
        self.bin.mkdir()
        for filename in ("node.exe", "npm.cmd"):
            (self.bin / filename).write_text("invalid fixture", encoding="ascii")
        self.env = {**os.environ, "PATH": str(self.bin)}

    def run_launcher(self, arguments="--dry-run", **kwargs):
        return subprocess.run(
            f'"{os.environ["COMSPEC"]}" /d /s /c ""{self.root / "start-services.bat"}" {arguments}"',
            cwd=self.temp.name, env=self.env, text=True,
            capture_output=True, timeout=10, **kwargs)

    def test_dry_run_from_unrelated_directory_prints_all_five_commands(self):
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("DRY RUN", result.stdout)
        for service, port in SERVICES.items():
            self.assertIn(f'"{self.root / "services" / service / "venv/Scripts/python.exe"}"', result.stdout)
            self.assertIn(f'"{self.root / "services" / service / "manage.py"}" runserver 0.0.0.0:{port}', result.stdout)
        self.assertIn(f'cd /d "{self.root / "fe"}" && npm.cmd run dev', result.stdout)
        self.assertNotIn("Launch requested", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_missing_any_prerequisite_fails_before_any_launch_command(self):
        paths = [self.root / "services" / name / filename for name in SERVICES
                 for filename in ("venv/Scripts/python.exe", "manage.py")]
        paths += [self.root / "fe" / "package.json", self.root / "fe/node_modules/.bin/vite.cmd",
                  self.bin / "node.exe", self.bin / "npm.cmd"]
        for path in paths:
            with self.subTest(path=path):
                content = path.read_bytes()
                path.unlink()
                try:
                    result = self.run_launcher()
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn("ERROR:", result.stdout)
                    self.assertNotIn("runserver", result.stdout)
                    self.assertNotIn("npm.cmd run dev", result.stdout)
                finally:
                    path.write_bytes(content)

    def test_help_does_not_require_prepared_services(self):
        shutil.rmtree(self.root / "services")
        result = self.run_launcher("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Usage:", result.stdout)
        self.assertNotIn("runserver", result.stdout)

    def test_unknown_or_extra_arguments_are_rejected(self):
        for arguments in ("--unknown", "--dry-run extra"):
            with self.subTest(arguments=arguments):
                result = self.run_launcher(arguments)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertNotIn("runserver", result.stdout)


if __name__ == "__main__":
    unittest.main()
