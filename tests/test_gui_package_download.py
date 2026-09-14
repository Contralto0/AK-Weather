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
class GuiPackageDownloadTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.folder = self.root / "GUI-Pakete mit [Klammern] & Leerzeichen"
        self.folder.mkdir()
        self.script = self.folder / "Get-GuiPackage.ps1"
        shutil.copy2(REPOSITORY / "dependencies/Get-GuiPackage.ps1", self.script)
        self.metadata = self.folder / "windows-gui.lock.json"
        self.source = self.root / "simuliertes Paket.whl"
        self.source.write_bytes(b"wheel")
        self.destination = self.root / "Paket-Cache"
        self.destination.mkdir()
        self.filename = "shiboken6-test-win_amd64.whl"
        self.write_spec(b"wheel")
        self.powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        self.environment = dict(os.environ, PATH="", PYTHONHOME="not-installed", PYTHONPATH="not-installed")

    def write_spec(self, expected, url="https://files.pythonhosted.org/shiboken6.whl", filename=None):
        package = {"name": "shiboken6", "filename": filename or self.filename, "url": url,
                   "size_bytes": len(expected), "sha256": hashlib.sha256(expected).hexdigest()}
        self.metadata.write_text(json.dumps({"format_version": 1, "packages": [package]}), encoding="utf-8")

    @staticmethod
    def quote(value):
        return "'" + str(value).replace("'", "''") + "'"

    def launch(self, action=None, destination=None):
        if action is None:
            action = f"{{ param($uri,$path) [System.IO.File]::Copy({self.quote(self.source)}, $path) }}"
        command = (f"$download={action}; & {self.quote(self.script)} -DestinationDirectory "
                   f"{self.quote(destination or self.destination)} -MetadataPath {self.quote(self.metadata)} "
                   "-DownloadAction $download; exit $LASTEXITCODE")
        return subprocess.run(
            [str(self.powershell), "-NoLogo", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "RemoteSigned", "-Command", command],
            cwd=self.root, env=self.environment, capture_output=True, text=True,
            errors="replace", timeout=20, creationflags=subprocess.CREATE_NO_WINDOW,
        )

    @property
    def target(self):
        return self.destination / self.filename

    def assert_clean_failure(self, result):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("Fehler beim Bereitstellen", result.stderr)
        self.assertFalse(self.target.exists())
        self.assertEqual(list(self.destination.glob(".*.partial")), [])

    def test_missing_shiboken_wheel_is_downloaded_then_verified(self):
        result = self.launch()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.read_bytes(), b"wheel")
        self.assertIn("heruntergeladen und erfolgreich geprueft", result.stdout)

    def test_valid_existing_wheel_skips_download(self):
        self.target.write_bytes(b"wheel")
        before = self.target.stat().st_mtime_ns
        result = self.launch("{ throw 'Download darf nicht laufen' }")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.stat().st_mtime_ns, before)
        self.assertIn("Vorhandenes", result.stdout)

    def test_corrupt_or_missing_download_is_rejected_and_cleaned(self):
        self.source.write_bytes(b"wrong")
        self.assert_clean_failure(self.launch())
        self.source.write_bytes(b"wheel")
        self.assert_clean_failure(self.launch("{ param($uri,$path) }"))

    def test_download_error_leaves_no_package(self):
        self.assert_clean_failure(self.launch("{ throw 'simulierter Netzfehler' }"))

    def test_invalid_source_filename_or_destination_is_rejected_before_download(self):
        for url, filename in (("http://example.invalid/package.whl", None),
                              ("https://example.invalid/package.whl", "../outside.whl"),
                              ("https://example.invalid/package.whl", "CON.whl")):
            with self.subTest(url=url, filename=filename):
                self.write_spec(b"wheel", url=url, filename=filename)
                self.assert_clean_failure(self.launch("{ throw 'Download darf nicht laufen' }"))
        self.write_spec(b"wheel")
        missing = self.root / "fehlt"
        result = self.launch("{ throw 'Download darf nicht laufen' }", missing)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
