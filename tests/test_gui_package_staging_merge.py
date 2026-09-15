import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPOSITORY = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == "win32", "Windows PowerShell 5.1")
class GuiPackageStagingMergeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.script = self.root / "Merge-GuiPackageStaging.ps1"
        shutil.copy2(REPOSITORY / "dependencies/Merge-GuiPackageStaging.ps1", self.script)
        self.shiboken = self.root / "shiboken staging"
        self.essentials = self.root / "essentials staging"
        self.destination = self.root / "application staging"
        self.shiboken.mkdir()
        self.essentials.mkdir()
        self.powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        self.environment = dict(os.environ, PATH="", PYTHONHOME="not-installed", PYTHONPATH="not-installed")

    def launch(self, shiboken=None, essentials=None, destination=None):
        return subprocess.run(
            [str(self.powershell), "-NoLogo", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "RemoteSigned", "-File", str(self.script),
             "-ShibokenStagingPath", str(shiboken or self.shiboken),
             "-EssentialsStagingPath", str(essentials or self.essentials),
             "-DestinationPath", str(destination or self.destination)],
            cwd=self.root, env=self.environment, capture_output=True, text=True,
            errors="replace", timeout=20, creationflags=subprocess.CREATE_NO_WINDOW,
        )

    def test_distinct_package_files_are_combined_without_python_or_path(self):
        (self.shiboken / "shiboken6").mkdir()
        (self.shiboken / "shiboken6/__init__.py").write_bytes(b"binding")
        (self.essentials / "PySide6").mkdir()
        (self.essentials / "PySide6/QtCore.pyd").write_bytes(b"qt core")
        result = self.launch()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.destination / "shiboken6/__init__.py").read_bytes(), b"binding")
        self.assertEqual((self.destination / "PySide6/QtCore.pyd").read_bytes(), b"qt core")

    def test_case_insensitive_collision_is_rejected_before_destination_creation(self):
        (self.shiboken / "Shared.txt").write_text("one")
        (self.essentials / "shared.TXT").write_text("two")
        result = self.launch()
        self.assertEqual(result.returncode, 1)
        self.assertIn("Mehrdeutiger Paket-Zielpfad", result.stderr)
        self.assertFalse(self.destination.exists())

    def test_missing_source_and_existing_destination_are_left_unchanged(self):
        missing = self.root / "missing"
        self.assertEqual(self.launch(shiboken=missing).returncode, 1)
        self.assertFalse(self.destination.exists())
        self.destination.mkdir()
        marker = self.destination / "keep"
        marker.write_text("keep")
        self.assertEqual(self.launch().returncode, 1)
        self.assertEqual(marker.read_text(), "keep")

    def test_destination_inside_source_is_rejected(self):
        nested = self.shiboken / "combined"
        self.assertEqual(self.launch(destination=nested).returncode, 1)
        self.assertFalse(nested.exists())


if __name__ == "__main__":
    unittest.main()
