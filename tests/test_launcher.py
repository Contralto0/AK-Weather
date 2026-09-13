import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPOSITORY = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == "win32", "Windows-Startdatei")
class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.app = self.root / "Projekte" / "App mit Leerzeichen & !"
        (self.app / "ak_weather").mkdir(parents=True)
        for name in ("Start-AK-Weather.cmd", "launch.py", "VERSION",
                     "ak_weather/__init__.py", "ak_weather/versioning.py"):
            shutil.copy2(REPOSITORY / name, self.app / name)
        self.environment = dict(os.environ)
        self.environment["PATH"] = ""
        self.environment["PYTHONHOME"] = str(self.root / "invalid-python-home")
        self.environment["PYTHONPATH"] = str(self.root)
        self.environment["AK_WEATHER_PYTHON"] = sys.executable
        self.cmd = Path(os.environ["SystemRoot"]) / "System32" / "cmd.exe"

    def launch(self, app=None, pause=False):
        launcher = (app or self.app) / "Start-AK-Weather.cmd"
        argument = "" if pause else " --no-pause"
        command = f'"{self.cmd}" /d /s /c ""{launcher}"{argument}"'
        return subprocess.run(command, cwd=self.root, env=self.environment,
                              input="\n", text=True, encoding="oem", capture_output=True,
                              timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)

    def test_relocated_app_uses_portable_python_without_path_or_current_directory(self):
        (self.app / "VERSION").write_text("1.2.3.4\n", encoding="utf-8")
        (self.root / "ak_weather.py").write_text("raise RuntimeError('wrong import')")
        result = self.launch()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("AK-Weather 1.2.3.4", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_repository_default_reuses_shared_portable_runtime(self):
        self.environment.pop("AK_WEATHER_PYTHON")
        result = self.launch(REPOSITORY)
        self.assertEqual(result.returncode, 0, result.stderr)
        version = (REPOSITORY / "VERSION").read_text().strip()
        self.assertIn(f"AK-Weather {version}", result.stdout)

    def test_missing_runtime_is_reported_without_falling_back_to_system_python(self):
        for override in (None, str(self.root / "fehlend & !" / "python.exe")):
            with self.subTest(override=override):
                if override is None:
                    self.environment.pop("AK_WEATHER_PYTHON", None)
                else:
                    self.environment["AK_WEATHER_PYTHON"] = override
                result = self.launch(pause=True)
                self.assertEqual(result.returncode, 1)
                self.assertIn("portable Python-Laufzeit wurde nicht gefunden", result.stderr)
                self.assertNotIn("AK-Weather ", result.stdout)

    def test_missing_or_invalid_version_is_reported_and_exit_code_preserved(self):
        version = self.app / "VERSION"
        for content in (None, "1.2.3"):
            with self.subTest(content=content):
                if content is None:
                    version.unlink()
                else:
                    version.write_text(content)
                result = self.launch()
                self.assertEqual(result.returncode, 1)
                self.assertIn("Programmversion kann nicht gelesen werden", result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_default_interactive_start_preserves_result_after_pause(self):
        result = self.launch(pause=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("AK-Weather ", result.stdout)


if __name__ == "__main__":
    unittest.main()
