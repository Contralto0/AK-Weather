import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPOSITORY = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == "win32", "Windows PowerShell 5.1")
class BootstrapPublishTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.runtime_root = self.root / "Globale Software"
        self.runtime_root.mkdir()
        self.staging = self.runtime_root / ".python-temp"
        self.staging.mkdir()
        (self.staging / "python.exe").write_bytes(b"portable python")
        self.script = self.root / "Publish-PythonRuntime.ps1"
        shutil.copy2(REPOSITORY / "bootstrap/Publish-PythonRuntime.ps1", self.script)
        self.metadata = self.root / "windows-python.lock.json"
        self.write_metadata()
        self.target = self.runtime_root / "python-3.14.7"
        self.powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        self.environment = dict(os.environ, PATH="", PYTHONHOME="not-installed", PYTHONPATH="not-installed")

    def write_metadata(self, **runtime_changes):
        runtime = {"version": "3.14.7", "directory_name": "python-3.14.7", "executable": "python.exe"}
        runtime.update(runtime_changes)
        self.metadata.write_text(json.dumps({"format_version": 1, "runtime": runtime}), encoding="utf-8")

    def launch(self, staging=None):
        return subprocess.run(
            [str(self.powershell), "-NoLogo", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "RemoteSigned", "-File", str(self.script),
             "-StagingPath", str(staging or self.staging),
             "-RuntimeRootPath", str(self.runtime_root), "-MetadataPath", str(self.metadata)],
            cwd=self.root, env=self.environment, capture_output=True, text=True,
            errors="replace", timeout=20, creationflags=subprocess.CREATE_NO_WINDOW,
        )

    def test_atomically_publishes_versioned_runtime_without_python_or_path(self):
        result = self.launch()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.staging.exists())
        self.assertEqual((self.target / "python.exe").read_bytes(), b"portable python")
        marker = json.loads((self.target / ".ak-weather-runtime.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(marker, {"format_version": 1, "runtime_version": "3.14.7",
                                  "directory_name": "python-3.14.7", "executable": "python.exe"})

    def test_matching_existing_runtime_is_reused_without_changes(self):
        self.target.mkdir()
        (self.target / "python.exe").write_bytes(b"existing")
        marker = {"format_version": 1, "runtime_version": "3.14.7",
                  "directory_name": "python-3.14.7", "executable": "python.exe"}
        (self.target / ".ak-weather-runtime.json").write_text(json.dumps(marker), encoding="utf-8")
        before = {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in self.target.iterdir()}
        result = self.launch()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("wiederverwendet", result.stdout)
        self.assertEqual(before, {path.name: (path.read_bytes(), path.stat().st_mtime_ns)
                                  for path in self.target.iterdir()})
        self.assertTrue(self.staging.exists())

    def test_unmarked_or_mismatched_existing_runtime_is_rejected(self):
        for marker in (None, {"format_version": 1, "runtime_version": "3.13.0",
                              "directory_name": "python-3.14.7", "executable": "python.exe"}):
            with self.subTest(marker=marker):
                self.target.mkdir()
                (self.target / "python.exe").write_bytes(b"existing")
                if marker:
                    (self.target / ".ak-weather-runtime.json").write_text(json.dumps(marker), encoding="utf-8")
                result = self.launch()
                self.assertEqual(result.returncode, 1)
                self.assertTrue(self.staging.exists())
                shutil.rmtree(self.target)

    def test_invalid_names_or_missing_executable_leave_staging_unchanged(self):
        original = (self.staging / "python.exe").read_bytes()
        for changes in ({"directory_name": "../outside"}, {"executable": "C:/python.exe"},
                        {"directory_name": "CON"}, {"version": "3.14"}):
            with self.subTest(changes=changes):
                self.write_metadata(**changes)
                result = self.launch()
                self.assertEqual(result.returncode, 1)
                self.assertEqual((self.staging / "python.exe").read_bytes(), original)
                self.assertFalse(self.target.exists())

        self.write_metadata()
        (self.staging / "python.exe").unlink()
        self.assertEqual(self.launch().returncode, 1)
        self.assertTrue(self.staging.exists())

    def test_staging_must_be_direct_child_of_runtime_root(self):
        nested = self.runtime_root / "nested" / "staging"
        nested.mkdir(parents=True)
        (nested / "python.exe").write_bytes(b"portable")
        result = self.launch(nested)
        self.assertEqual(result.returncode, 1)
        self.assertTrue(nested.exists())
        self.assertFalse(self.target.exists())


if __name__ == "__main__":
    unittest.main()
