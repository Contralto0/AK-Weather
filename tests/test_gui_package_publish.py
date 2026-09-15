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
class GuiPackagePublishTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.library_root = self.root / "Portable Libraries"
        self.library_root.mkdir()
        self.staging = self.library_root / ".gui-temp"
        (self.staging / "shiboken6").mkdir(parents=True)
        (self.staging / "PySide6").mkdir()
        (self.staging / "PySide6/QtCore.pyd").write_bytes(b"fixture")
        self.script = self.root / "Publish-GuiPackage.ps1"
        shutil.copy2(REPOSITORY / "dependencies/Publish-GuiPackage.ps1", self.script)
        self.metadata = self.root / "windows-gui.lock.json"
        self.write_metadata()
        self.target = self.library_root / "ak-weather-gui-6.11.2-py3.14-win_amd64"
        self.powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        self.environment = dict(os.environ, PATH="", PYTHONHOME="not-installed", PYTHONPATH="not-installed")

    def write_metadata(self, **deployment_changes):
        deployment = {"directory_name": "ak-weather-gui-6.11.2-py3.14-win_amd64",
                      "marker_name": ".ak-weather-gui.json",
                      "required_directories": ["shiboken6", "PySide6"]}
        deployment.update(deployment_changes)
        data = {"format_version": 1, "target": {"python_version": "3.14.7"},
                "deployment": deployment,
                "packages": [{"version": "6.11.2"}, {"version": "6.11.2"}]}
        self.metadata.write_text(json.dumps(data), encoding="utf-8")

    def launch(self, staging=None):
        return subprocess.run(
            [str(self.powershell), "-NoLogo", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "RemoteSigned", "-File", str(self.script),
             "-StagingPath", str(staging or self.staging),
             "-LibraryRootPath", str(self.library_root), "-MetadataPath", str(self.metadata)],
            cwd=self.root, env=self.environment, capture_output=True, text=True,
            errors="replace", timeout=20, creationflags=subprocess.CREATE_NO_WINDOW,
        )

    def marker(self):
        return {"format_version": 1, "gui_version": "6.11.2", "python_version": "3.14.7",
                "directory_name": "ak-weather-gui-6.11.2-py3.14-win_amd64"}

    def test_atomically_publishes_marked_versioned_package(self):
        result = self.launch()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.staging.exists())
        self.assertEqual((self.target / "PySide6/QtCore.pyd").read_bytes(), b"fixture")
        marker = json.loads((self.target / ".ak-weather-gui.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(marker, self.marker())

    def test_matching_existing_package_is_reused_without_changes(self):
        shutil.copytree(self.staging, self.target)
        (self.target / ".ak-weather-gui.json").write_text(json.dumps(self.marker()), encoding="utf-8")
        before = {path.relative_to(self.target): (path.read_bytes(), path.stat().st_mtime_ns)
                  for path in self.target.rglob("*") if path.is_file()}
        result = self.launch()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("wiederverwendet", result.stdout)
        self.assertEqual(before, {path.relative_to(self.target): (path.read_bytes(), path.stat().st_mtime_ns)
                                  for path in self.target.rglob("*") if path.is_file()})
        self.assertTrue(self.staging.exists())

    def test_unmarked_or_mismatched_existing_package_is_rejected(self):
        for marker in (None, dict(self.marker(), gui_version="6.10.0")):
            with self.subTest(marker=marker):
                shutil.copytree(self.staging, self.target)
                if marker:
                    (self.target / ".ak-weather-gui.json").write_text(json.dumps(marker), encoding="utf-8")
                self.assertEqual(self.launch().returncode, 1)
                self.assertTrue(self.staging.exists())
                shutil.rmtree(self.target)

    def test_missing_required_directory_or_existing_marker_preserves_staging(self):
        shutil.rmtree(self.staging / "PySide6")
        self.assertEqual(self.launch().returncode, 1)
        self.assertTrue(self.staging.exists())
        (self.staging / "PySide6").mkdir()
        (self.staging / ".ak-weather-gui.json").write_text("reserved")
        self.assertEqual(self.launch().returncode, 1)
        self.assertTrue(self.staging.exists())

    def test_staging_must_be_direct_child_and_names_must_be_safe(self):
        nested = self.library_root / "nested" / "staging"
        shutil.copytree(self.staging, nested)
        self.assertEqual(self.launch(nested).returncode, 1)
        self.assertTrue(nested.exists())
        self.write_metadata(directory_name="../outside")
        self.assertEqual(self.launch().returncode, 1)
        self.assertTrue(self.staging.exists())


if __name__ == "__main__":
    unittest.main()
