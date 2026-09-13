import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ak_weather.changelog import entries_since
from ak_weather.read_state import ReadStateError, default_state_path, load_last_seen, save_after_display
from ak_weather.versioning import Version


class ReadStateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.path = self.root / "user-data" / "read-state.json"

    def test_first_start_and_failed_display_create_nothing(self):
        self.assertIsNone(load_last_seen(self.path))
        self.assertIsNone(save_after_display("1.0.0.0", displayed=False, path=self.path))
        self.assertFalse(self.path.parent.exists())

    def test_successful_display_survives_reopening(self):
        self.assertEqual(save_after_display("1.2.3.4", displayed=True, path=self.path), Version(1, 2, 3, 4))
        self.assertEqual(load_last_seen(self.path), Version(1, 2, 3, 4))
        self.assertEqual(json.loads(self.path.read_text()), {"last_seen_version": "1.2.3.4"})

    def test_failed_display_preserves_existing_state(self):
        save_after_display("1.0.0.0", displayed=True, path=self.path)
        content = self.path.read_bytes()
        save_after_display("2.0.0.0", displayed=False, path=self.path)
        self.assertEqual(self.path.read_bytes(), content)

    def test_equal_or_older_display_does_not_regress_or_rewrite_state(self):
        save_after_display("1.10.0.0", displayed=True, path=self.path)
        modified = self.path.stat().st_mtime_ns
        for version in ("1.9.0.0", "1.10.0.0"):
            self.assertEqual(save_after_display(version, displayed=True, path=self.path), Version(1, 10, 0, 0))
        self.assertEqual(self.path.stat().st_mtime_ns, modified)

    def test_corrupt_state_is_preserved_and_reported(self):
        self.path.parent.mkdir()
        for content in (b"invalid", b"[]", b"{}", b'{"last_seen_version": 123}', b'{"last_seen_version": "1.2.3"}', b"\xff"):
            with self.subTest(content=content):
                self.path.write_bytes(content)
                with self.assertRaises(ReadStateError):
                    load_last_seen(self.path)
                with self.assertRaises(ReadStateError):
                    save_after_display("2.0.0.0", displayed=True, path=self.path)
                self.assertEqual(self.path.read_bytes(), content)

    def test_failed_replace_preserves_previous_file_and_cleans_temporary(self):
        save_after_display("1.0.0.0", displayed=True, path=self.path)
        with patch("ak_weather.read_state.os.replace", side_effect=PermissionError):
            with self.assertRaises(PermissionError):
                save_after_display("2.0.0.0", displayed=True, path=self.path)
        self.assertEqual(load_last_seen(self.path), Version(1, 0, 0, 0))
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_invalid_arguments_create_nothing(self):
        for version in ("1.2.3", 123):
            with self.assertRaises((ValueError, TypeError)):
                save_after_display(version, displayed=True, path=self.path)
        with self.assertRaises(TypeError):
            save_after_display("1.0.0.0", displayed="yes", path=self.path)
        self.assertFalse(self.path.parent.exists())

    def test_default_paths_use_user_data_and_ignore_relative_environment_paths(self):
        for platform, variable in (("win32", "LOCALAPPDATA"), ("linux", "XDG_STATE_HOME")):
            with self.subTest(platform=platform):
                with patch("ak_weather.read_state.sys.platform", platform), patch.dict("os.environ", {variable: str(self.root)}, clear=True):
                    self.assertEqual(default_state_path(), self.root / "AK-Weather" / "read-state.json")
                with patch("ak_weather.read_state.sys.platform", platform), patch.dict("os.environ", {variable: "relative"}, clear=True), patch("ak_weather.read_state.Path.home", return_value=self.root):
                    folder = self.root / "AppData" / "Local" if platform == "win32" else self.root / ".local" / "state"
                    self.assertEqual(default_state_path(), folder / "AK-Weather" / "read-state.json")

    def test_read_state_filters_news_only_after_successful_display(self):
        before = entries_since(load_last_seen(self.path))
        self.assertTrue(before)
        save_after_display(before[0].version, displayed=False, path=self.path)
        self.assertEqual(entries_since(load_last_seen(self.path)), before)
        save_after_display(before[0].version, displayed=True, path=self.path)
        self.assertEqual(entries_since(load_last_seen(self.path)), ())


if __name__ == "__main__":
    unittest.main()
