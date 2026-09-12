from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ak_weather.versioning import Change, Version, advance_version_file, read_version


class VersionTests(unittest.TestCase):
    def test_each_change_resets_only_following_parts(self):
        before = Version.parse("1.2.3.4")
        expected = {
            Change.MAJOR: "2.0.0.0", Change.FEATURE: "1.3.0.0",
            Change.IMPROVEMENT: "1.2.4.0", Change.FIX: "1.2.3.5",
        }
        for category, value in expected.items():
            with self.subTest(category=category):
                after = before.advance([category])
                self.assertEqual(str(after), value)
                self.assertGreater(after, before)

    def test_highest_category_wins_once(self):
        before = Version.parse("1.2.3.4")
        self.assertEqual(str(before.advance([Change.FIX, Change.FEATURE, Change.FEATURE])), "1.3.0.0")
        self.assertEqual(str(before.advance([Change.FIX, Change.MAJOR])), "2.0.0.0")

    def test_no_change_means_no_new_version(self):
        before = Version.parse("1.2.3.4")
        self.assertIs(before.advance([]), before)

    def test_versions_are_compared_numerically(self):
        self.assertGreater(Version.parse("1.10.0.0"), Version.parse("1.9.9.9"))

    def test_rejects_malformed_versions(self):
        for value in ("1.2.3", "1.2.3.4.5", "1.02.3.4", "-1.2.3.4", "1.2.3.x", "1.2.3.4\n", "１.2.3.4"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    Version.parse(value)
        for parts in ((-1, 0, 0, 0), (True, 0, 0, 0), (1.5, 0, 0, 0)):
            with self.subTest(parts=parts):
                with self.assertRaises(ValueError):
                    Version(*parts)

    def test_invalid_category_does_not_change_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "VERSION"
            path.write_text("1.2.3.4\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                advance_version_file(["fix"], path)
            self.assertEqual(path.read_text(encoding="utf-8"), "1.2.3.4\n")

    def test_file_update_and_read_only_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "VERSION"
            path.write_text("1.2.3.4\n", encoding="utf-8")
            self.assertEqual(str(advance_version_file([Change.IMPROVEMENT], path)), "1.2.4.0")
            before = path.stat().st_mtime_ns
            self.assertEqual(str(advance_version_file([], path)), "1.2.4.0")
            self.assertEqual(path.stat().st_mtime_ns, before)
            self.assertEqual(read_version(path), Version(1, 2, 4, 0))

    def test_failed_replace_preserves_original_and_cleans_temporary(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "VERSION"
            path.write_text("1.2.3.4\n", encoding="utf-8")
            with patch("ak_weather.versioning.os.replace", side_effect=PermissionError):
                with self.assertRaises(PermissionError):
                    advance_version_file([Change.FIX], path)
            self.assertEqual(path.read_text(encoding="utf-8"), "1.2.3.4\n")
            self.assertEqual(list(Path(directory).iterdir()), [path])


if __name__ == "__main__":
    unittest.main()
