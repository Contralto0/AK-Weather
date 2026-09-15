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
class GuiPackageExtractionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.script = self.root / "Expand-GuiPackage.ps1"
        shutil.copy2(REPOSITORY / "dependencies/Expand-GuiPackage.ps1", self.script)
        self.wheel = self.root / "shiboken6-test.whl"
        self.metadata = self.root / "windows-gui.lock.json"
        self.destination = self.root / "Paket Staging"
        self.powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        self.environment = dict(os.environ, PATH="", PYTHONHOME="not-installed", PYTHONPATH="not-installed")

    def write_wheel(self, entries, package_name="shiboken6", filename=None):
        if filename is not None:
            self.wheel = self.root / filename
        with zipfile.ZipFile(self.wheel, "w") as archive:
            for entry in entries:
                if isinstance(entry[0], zipfile.ZipInfo):
                    archive.writestr(entry[0], entry[1])
                else:
                    archive.writestr(entry[0], entry[1])
        content = self.wheel.read_bytes()
        package = {"name": package_name, "filename": self.wheel.name,
                   "size_bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
        self.metadata.write_text(json.dumps({"format_version": 1, "packages": [package]}), encoding="utf-8")

    def launch(self, destination=None, package_name=None):
        arguments = [str(self.powershell), "-NoLogo", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "RemoteSigned", "-File", str(self.script),
             "-WheelPath", str(self.wheel), "-DestinationPath", str(destination or self.destination),
             "-MetadataPath", str(self.metadata)]
        if package_name is not None:
            arguments.extend(["-PackageName", package_name])
        return subprocess.run(
            arguments,
            cwd=self.root, env=self.environment, capture_output=True, text=True,
            errors="replace", timeout=20, creationflags=subprocess.CREATE_NO_WINDOW,
        )

    def assert_rejected(self, result):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("Fehler beim Entpacken", result.stderr)
        self.assertFalse(self.destination.exists())

    def test_verified_wheel_extracts_regular_files_without_python_or_path(self):
        self.write_wheel([("shiboken6/__init__.py", b"version = 1\n"),
                          ("shiboken6-1.dist-info/METADATA", b"Name: shiboken6\n")])
        result = self.launch()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.destination / "shiboken6/__init__.py").read_bytes(), b"version = 1\n")

    def test_verified_pyside6_essentials_wheel_uses_its_own_staging_folder(self):
        self.write_wheel(
            [("PySide6/QtCore.pyd", b"small fixture")],
            package_name="PySide6-Essentials",
            filename="pyside6_essentials-test.whl",
        )
        result = self.launch(package_name="PySide6-Essentials")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            (self.destination / "PySide6/QtCore.pyd").read_bytes(),
            b"small fixture",
        )

    def test_parent_absolute_drive_unc_and_device_paths_are_rejected_before_writing(self):
        for unsafe in ("../outside", "/absolute", "C:/drive", r"\\server\share", "CON"):
            with self.subTest(unsafe=unsafe):
                self.write_wheel([("safe/file", b"safe"), (unsafe, b"unsafe")])
                self.assert_rejected(self.launch())
                self.assertFalse((self.root / "outside").exists())

    def test_symlink_and_case_insensitive_duplicate_targets_are_rejected(self):
        link = zipfile.ZipInfo("link")
        link.create_system = 3
        link.external_attr = 0o120777 << 16
        self.write_wheel([(link, b"target")])
        self.assert_rejected(self.launch())
        self.write_wheel([("Package/file", b"one"), ("package/FILE", b"two")])
        self.assert_rejected(self.launch())

    def test_tampered_wheel_is_rejected_before_extraction(self):
        self.write_wheel([("shiboken6/file", b"original")])
        self.wheel.write_bytes(self.wheel.read_bytes() + b"tampered")
        self.assert_rejected(self.launch())

    def test_existing_destination_or_missing_parent_is_unchanged(self):
        self.write_wheel([("shiboken6/file", b"content")])
        self.destination.mkdir()
        marker = self.destination / "keep"
        marker.write_text("keep")
        result = self.launch()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(marker.read_text(), "keep")
        missing = self.root / "missing" / "staging"
        self.assertEqual(self.launch(missing).returncode, 1)
        self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
