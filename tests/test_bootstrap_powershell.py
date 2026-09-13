import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPOSITORY = Path(__file__).resolve().parents[1]
ABC_SHA256 = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


@unittest.skipUnless(sys.platform == "win32", "Windows PowerShell 5.1")
class BootstrapPowerShellTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.folder = self.root / "Bootstrap mit [Klammern] & Leerzeichen"
        self.folder.mkdir()
        self.script = self.folder / "Test-PythonArchive.ps1"
        shutil.copy2(REPOSITORY / "bootstrap/Test-PythonArchive.ps1", self.script)
        self.metadata = self.folder / "windows-python.lock.json"
        self.archive = self.root / "Archiv [1] & Test.zip"
        self.archive.write_bytes(b"abc")
        self.spec = {"format_version": 1, "archive": {"size_bytes": 3, "sha256": ABC_SHA256}}
        self.write_spec(self.spec)
        self.powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        self.environment = dict(os.environ, PATH="", PYTHONHOME="not-installed", PYTHONPATH="not-installed")
        self.environment.pop("AK_WEATHER_PYTHON", None)
        self.environment["PSModulePath"] = str(self.powershell.parent / "Modules")

    def write_spec(self, spec):
        self.metadata.write_text(json.dumps(spec), encoding="utf-8")

    def launch(self, archive=None, explicit_metadata=False):
        args = [str(self.powershell), "-NoLogo", "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "RemoteSigned",
                "-File", str(self.script), "-ArchivePath", str(archive or self.archive)]
        if explicit_metadata:
            args += ["-MetadataPath", str(self.metadata)]
        return subprocess.run(args, cwd=self.root, env=self.environment, capture_output=True,
                              text=True, errors="replace", timeout=15,
                              creationflags=subprocess.CREATE_NO_WINDOW)

    def assert_rejected(self, result):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("Fehler bei der Python-Archivpruefung:", result.stderr)
        self.assertNotIn("erfolgreich", result.stdout)

    def test_native_powershell_accepts_archive_without_python_or_path(self):
        before = self.archive.stat().st_mtime_ns
        result = self.launch()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("erfolgreich geprueft", result.stdout)
        self.assertEqual(result.stderr, "")
        self.assertEqual(self.archive.read_bytes(), b"abc")
        self.assertEqual(self.archive.stat().st_mtime_ns, before)
        self.assertEqual(set(self.root.iterdir()), {self.folder, self.archive})

    def test_explicit_metadata_path_and_empty_archive(self):
        self.archive.write_bytes(b"")
        self.write_spec({"format_version": 1, "archive": {"size_bytes": 0,
            "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}})
        self.assertEqual(self.launch(explicit_metadata=True).returncode, 0)

    def test_truncated_oversized_and_same_size_tampering_are_rejected(self):
        for content in (b"ab", b"abcd", b"abd"):
            with self.subTest(content=content):
                self.archive.write_bytes(content)
                self.assert_rejected(self.launch())
                self.assertEqual(self.archive.read_bytes(), content)

    def test_missing_files_and_directories_are_rejected(self):
        for archive in (self.root / "missing.zip", self.folder):
            with self.subTest(archive=archive):
                self.assert_rejected(self.launch(archive))
        self.metadata.unlink()
        self.assert_rejected(self.launch())

    def test_malformed_metadata_is_rejected(self):
        for content in ("{invalid", "[]", "null", "{}",
                        '{"format_version":"1","archive":{}}',
                        '{"format_version":2,"archive":{}}'):
            with self.subTest(content=content):
                self.metadata.write_text(content)
                self.assert_rejected(self.launch())

    def test_invalid_size_and_hash_types_are_rejected(self):
        for size in (-1, True, "3", 3.0):
            with self.subTest(size=size):
                self.write_spec({"format_version": 1, "archive": {"size_bytes": size, "sha256": ABC_SHA256}})
                self.assert_rejected(self.launch())
        for digest in (None, 123, "a" * 63, "g" * 64, ABC_SHA256 + "\n"):
            with self.subTest(digest=digest):
                self.write_spec({"format_version": 1, "archive": {"size_bytes": 3, "sha256": digest}})
                self.assert_rejected(self.launch())

    def test_open_writer_prevents_acceptance(self):
        with self.archive.open("r+b"):
            self.assert_rejected(self.launch())


if __name__ == "__main__":
    unittest.main()
