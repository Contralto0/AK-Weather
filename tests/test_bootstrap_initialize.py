import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

REPOSITORY = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == "win32", "Windows PowerShell 5.1")
class BootstrapInitializeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.bootstrap = self.root / "Bootstrap mit Leerzeichen"
        shutil.copytree(REPOSITORY / "bootstrap", self.bootstrap)
        self.runtime_root = self.root / "Globale Software"
        self.runtime_root.mkdir()
        self.source = self.root / "simulierter Download.zip"
        with zipfile.ZipFile(self.source, "w") as archive:
            archive.writestr("python.exe", b"portable")
            archive.writestr("python314._pth", b"python314.zip\n")
        content = self.source.read_bytes()
        self.metadata = self.bootstrap / "test-python.lock.json"
        self.spec = {
            "format_version": 1,
            "runtime": {"version": "3.14.7", "directory_name": "python-3.14.7",
                        "executable": "python.exe"},
            "archive": {"filename": "python.zip", "url": "https://www.python.org/python.zip",
                        "size_bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()},
        }
        self.metadata.write_text(json.dumps(self.spec), encoding="utf-8")
        self.script = self.bootstrap / "Initialize-PythonRuntime.ps1"
        self.target = self.runtime_root / "python-3.14.7"
        self.archive = self.runtime_root / "python.zip"
        self.powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        self.environment = dict(os.environ, PATH="", PYTHONHOME="not-installed", PYTHONPATH="not-installed")

    @staticmethod
    def quote(value):
        return "'" + str(value).replace("'", "''") + "'"

    def launch(self, action=None):
        if action is None:
            action = f"{{ param($uri,$path) [System.IO.File]::Copy({self.quote(self.source)}, $path) }}"
        command = (f"$download={action}; & {self.quote(self.script)} -RuntimeRootPath "
                   f"{self.quote(self.runtime_root)} -MetadataPath {self.quote(self.metadata)} "
                   "-DownloadAction $download; exit $LASTEXITCODE")
        return subprocess.run(
            [str(self.powershell), "-NoLogo", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "RemoteSigned", "-Command", command],
            cwd=self.root, env=self.environment, capture_output=True, text=True,
            errors="replace", timeout=30, creationflags=subprocess.CREATE_NO_WINDOW,
        )

    def staging_paths(self):
        return list(self.runtime_root.glob(".*.staging"))

    def test_missing_runtime_runs_all_steps_with_simulated_download(self):
        result = self.launch()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.target / "python.exe").read_bytes(), b"portable")
        self.assertTrue(self.archive.is_file())
        self.assertEqual(self.staging_paths(), [])
        self.assertIn("vollstaendig bereitgestellt", result.stdout)

    def test_matching_runtime_skips_download_and_remains_unchanged(self):
        self.target.mkdir()
        (self.target / "python.exe").write_bytes(b"existing")
        marker = {"format_version": 1, "runtime_version": "3.14.7",
                  "directory_name": "python-3.14.7", "executable": "python.exe"}
        (self.target / ".ak-weather-runtime.json").write_text(json.dumps(marker), encoding="utf-8")
        before = {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in self.target.iterdir()}
        result = self.launch("{ throw 'Download darf nicht laufen' }")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ohne Download wiederverwendet", result.stdout)
        self.assertEqual(before, {path.name: (path.read_bytes(), path.stat().st_mtime_ns)
                                  for path in self.target.iterdir()})
        self.assertFalse(self.archive.exists())

    def test_conflicting_runtime_is_rejected_before_download(self):
        self.target.mkdir()
        (self.target / "python.exe").write_bytes(b"unknown")
        result = self.launch("{ throw 'Download darf nicht laufen' }")
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.archive.exists())
        self.assertEqual((self.target / "python.exe").read_bytes(), b"unknown")

    def test_corrupt_simulated_download_stops_before_extraction(self):
        corrupt = self.root / "corrupt.zip"
        corrupt.write_bytes(b"corrupt")
        action = f"{{ param($uri,$path) [System.IO.File]::Copy({self.quote(corrupt)}, $path) }}"
        result = self.launch(action)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.target.exists())
        self.assertEqual(self.staging_paths(), [])

    def test_unsafe_archive_is_rejected_and_staging_is_cleaned(self):
        with zipfile.ZipFile(self.source, "w") as archive:
            archive.writestr("../outside.txt", b"unsafe")
        content = self.source.read_bytes()
        self.spec["archive"]["size_bytes"] = len(content)
        self.spec["archive"]["sha256"] = hashlib.sha256(content).hexdigest()
        self.metadata.write_text(json.dumps(self.spec), encoding="utf-8")
        result = self.launch()
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.target.exists())
        self.assertFalse((self.root / "outside.txt").exists())
        self.assertEqual(self.staging_paths(), [])


if __name__ == "__main__":
    unittest.main()
