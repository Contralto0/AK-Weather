import hashlib
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
class BootstrapDownloadTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.folder = self.root / "Bootstrap mit [Klammern] & Leerzeichen"
        self.folder.mkdir()
        self.script = self.folder / "Get-PythonArchive.ps1"
        shutil.copy2(REPOSITORY / "bootstrap/Get-PythonArchive.ps1", self.script)
        self.metadata = self.folder / "windows-python.lock.json"
        self.source = self.root / "simulierter Download.zip"
        self.source.write_bytes(b"abc")
        self.destination = self.root / "Python Archiv.zip"
        self.write_spec(b"abc")
        self.powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        self.environment = dict(os.environ, PATH="", PYTHONHOME="not-installed", PYTHONPATH="not-installed")
        self.environment.pop("AK_WEATHER_PYTHON", None)

    def write_spec(self, expected, url="https://www.python.org/example.zip"):
        spec = {"format_version": 1, "archive": {"url": url, "size_bytes": len(expected),
                "sha256": hashlib.sha256(expected).hexdigest()}}
        self.metadata.write_text(json.dumps(spec), encoding="utf-8")

    @staticmethod
    def quote(value):
        return "'" + str(value).replace("'", "''") + "'"

    def launch(self, action=None, destination=None):
        if action is None:
            action = f"{{ param($uri,$path) [System.IO.File]::Copy({self.quote(self.source)}, $path) }}"
        command = (f"$download={action}; & {self.quote(self.script)} -DestinationPath "
                   f"{self.quote(destination or self.destination)} -MetadataPath {self.quote(self.metadata)} "
                   "-DownloadAction $download; exit $LASTEXITCODE")
        return subprocess.run([str(self.powershell), "-NoLogo", "-NoProfile", "-NonInteractive",
                               "-ExecutionPolicy", "RemoteSigned", "-Command", command],
                              cwd=self.root, env=self.environment, capture_output=True, text=True,
                              errors="replace", timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)

    def assert_clean_failure(self, result):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("Fehler beim Bereitstellen", result.stderr)
        self.assertFalse(self.destination.exists())
        self.assertEqual(list(self.root.glob(".*.partial")), [])

    def test_missing_archive_is_downloaded_to_temporary_file_then_published(self):
        result = self.launch()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.destination.read_bytes(), b"abc")
        self.assertEqual(self.source.read_bytes(), b"abc")
        self.assertIn("heruntergeladen und erfolgreich geprueft", result.stdout)
        self.assertEqual(list(self.root.glob(".*.partial")), [])

    def test_valid_existing_archive_skips_download(self):
        self.destination.write_bytes(b"abc")
        before = self.destination.stat().st_mtime_ns
        result = self.launch(action="{ throw 'Download darf nicht laufen' }")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Vorhandenes", result.stdout)
        self.assertEqual(self.destination.stat().st_mtime_ns, before)

    def test_corrupt_download_is_rejected_and_temporary_file_removed(self):
        self.source.write_bytes(b"abd")
        self.assert_clean_failure(self.launch())

    def test_download_error_or_missing_output_leaves_no_archive(self):
        for action in ("{ throw 'simulierter Netzfehler' }", "{ param($uri,$path) }"):
            with self.subTest(action=action):
                self.assert_clean_failure(self.launch(action=action))

    def test_invalid_source_or_missing_destination_folder_is_rejected_before_download(self):
        self.write_spec(b"abc", url="http://www.python.org/example.zip")
        self.assert_clean_failure(self.launch(action="{ throw 'Download darf nicht laufen' }"))
        self.write_spec(b"abc")
        missing = self.root / "fehlt" / "archive.zip"
        result = self.launch(action="{ throw 'Download darf nicht laufen' }", destination=missing)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
