import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ak_weather.changelog import ChangelogError, entries_since, read_changelog
from ak_weather.versioning import Change, Version, read_version


def entry(version: str) -> dict:
    return {
        "version": version, "date": "2026-09-12", "category": "feature",
        "title": "Größe und Böen", "changes": ["Änderung mit Umlauten."],
    }


class ChangelogTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "changelog.json"

    def write_history(self, records):
        self.path.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")

    def test_first_open_returns_all_entries_in_numeric_descending_order(self):
        self.write_history([entry("1.2.0.0"), entry("1.10.0.0"), entry("1.9.0.0")])
        records = entries_since(None, self.path)
        self.assertEqual([str(item.version) for item in records], ["1.10.0.0", "1.9.0.0", "1.2.0.0"])
        self.assertEqual(records[0].title, "Größe und Böen")
        self.assertEqual(records[0].changes, ("Änderung mit Umlauten.",))
        self.assertEqual(records[0].category, Change.FEATURE)

    def test_skipped_versions_are_all_included(self):
        self.write_history([entry("1.2.0.0"), entry("1.3.0.0"), entry("1.10.0.0")])
        records = entries_since("1.2.0.0", self.path)
        self.assertEqual([str(item.version) for item in records], ["1.10.0.0", "1.3.0.0"])

    def test_equal_or_newer_last_seen_returns_nothing(self):
        self.write_history([entry("1.2.0.0"), entry("1.10.0.0")])
        for last_seen in (Version(1, 10, 0, 0), "2.0.0.0"):
            with self.subTest(last_seen=last_seen):
                self.assertEqual(entries_since(last_seen, self.path), ())

    def test_last_seen_need_not_exist_in_history(self):
        self.write_history([entry("1.2.0.0"), entry("1.10.0.0")])
        self.assertEqual([str(item.version) for item in entries_since("1.5.0.0", self.path)], ["1.10.0.0"])

    def test_empty_history_is_valid(self):
        self.write_history([])
        self.assertEqual(entries_since(None, self.path), ())

    def test_reading_preserves_source_and_does_not_store_read_state(self):
        record = entry("1.2.0.0")
        record["additional_metadata"] = "reserved for future versions"
        self.write_history([record])
        content = self.path.read_bytes()
        first = entries_since(None, self.path)
        self.assertEqual(entries_since(None, self.path), first)
        self.assertEqual(self.path.read_bytes(), content)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_invalid_history_is_not_treated_as_no_news(self):
        bad_records = (
            {}, [None], [{}], [dict(entry("1.0.0.0"), version="1.0.0")],
            [dict(entry("1.0.0.0"), date="2026-02-31")],
            [dict(entry("1.0.0.0"), category="unknown")],
            [dict(entry("1.0.0.0"), changes="not a list")],
            [dict(entry("1.0.0.0"), changes=[""])],
        )
        for records in bad_records:
            with self.subTest(records=records):
                self.write_history(records)
                with self.assertRaises(ChangelogError):
                    entries_since("9.0.0.0", self.path)
        for content in (b"[invalid", b"\xff"):
            self.path.write_bytes(content)
            with self.assertRaises(ChangelogError):
                read_changelog(self.path)

    def test_duplicate_version_is_rejected(self):
        self.write_history([entry("1.0.0.0"), entry("1.0.0.0")])
        with self.assertRaises(ChangelogError):
            read_changelog(self.path)

    def test_missing_file_and_invalid_last_seen_are_explicit_errors(self):
        with self.assertRaises(FileNotFoundError):
            entries_since(None, self.path)
        self.write_history([])
        with self.assertRaises(ValueError):
            entries_since("not-a-version", self.path)
        with self.assertRaises(TypeError):
            entries_since(123, self.path)

    def test_repository_history_matches_current_version(self):
        self.assertEqual(read_changelog()[0].version, read_version())


if __name__ == "__main__":
    unittest.main()
