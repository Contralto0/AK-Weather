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
class BootstrapExtractionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.folder = self.root / "Bootstrap mit [Klammern] & Leerzeichen"
        self.folder.mkdir()
        self.script = self.folder / "Expand-PythonArchive.ps1"
        shutil.copy2(REPOSITORY / "bootstrap/Expand-PythonArchive.ps1", self.script)
        self.archive = self.root / "Python Archiv.zip"
        self.destination = self.root / "temporaere Laufzeit"
        self.powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        self.environment = dict(os.environ, PATH="", PYTHONHOME="not-installed", PYTHONPATH="not-installed")
        self.environment.pop("AK_WEATHER_PYTHON", None)

    def write_zip(self, entries):
        with zipfile.ZipFile(self.archive, "w") as archive:
            for name, content in entries:
                archive.writestr(name, content)

    def launch(self, destination=None):
        return subprocess.run(
            [str(self.powershell), "-NoLogo", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "RemoteSigned", "-File", str(self.script),
             "-ArchivePath", str(self.archive), "-DestinationPath", str(destination or self.destination)],
            cwd=self.root, env=self.environment, capture_output=True, text=True,
            errors="replace", timeout=20, creationflags=subprocess.CREATE_NO_WINDOW,
        )

    def assert_rejected_without_output(self, result):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("Fehler beim Entpacken", result.stderr)
        self.assertFalse(self.destination.exists())

    def test_extracts_regular_files_without_python_or_path(self):
        self.write_zip([("python.exe", b"exe"), ("Lib/module.py", b"pass\n"), ("empty/", b"")])
        result = self.launch()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.destination / "python.exe").read_bytes(), b"exe")
        self.assertEqual((self.destination / "Lib/module.py").read_bytes(), b"pass\n")
        self.assertTrue((self.destination / "empty").is_dir())

    def test_rejects_parent_absolute_drive_and_unc_paths_before_writing(self):
        for unsafe in ("../outside.txt", "/absolute.txt", "C:/drive.txt", "//server/share.txt",
                       "folder/../../outside.txt", r"\\server\share.txt", "CON.txt",
                       "folder/name.", "folder/name "):
            with self.subTest(unsafe=unsafe):
                self.write_zip([("safe.txt", b"safe"), (unsafe, b"unsafe")])
                self.assert_rejected_without_output(self.launch())
                self.assertFalse((self.root / "outside.txt").exists())

    def test_rejects_symlinks_and_case_insensitive_duplicate_targets(self):
        link = zipfile.ZipInfo("link")
        link.create_system = 3
        link.external_attr = 0o120777 << 16
        with zipfile.ZipFile(self.archive, "w") as archive:
            archive.writestr(link, "target")
        self.assert_rejected_without_output(self.launch())

        self.write_zip([("Lib/module.py", b"one"), ("lib/MODULE.py", b"two")])
        self.assert_rejected_without_output(self.launch())

    def test_existing_or_missing_parent_destination_is_not_modified(self):
        self.write_zip([("python.exe", b"exe")])
        self.destination.mkdir()
        marker = self.destination / "keep.txt"
        marker.write_text("keep", encoding="utf-8")
        result = self.launch()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

        missing = self.root / "missing" / "runtime"
        result = self.launch(missing)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(missing.exists())

    def test_corrupt_zip_removes_no_unrelated_files(self):
        self.archive.write_bytes(b"not a zip")
        unrelated = self.root / "keep.txt"
        unrelated.write_text("keep", encoding="utf-8")
        self.assert_rejected_without_output(self.launch())
        self.assertEqual(unrelated.read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()
