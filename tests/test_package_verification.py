import hashlib
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ak_weather.package_verification import PackageVerificationError, verify_package_file

ABC_SHA256 = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


class PackageVerificationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.path = self.root / "package.whl"

    def test_known_hash_accepts_matching_file_without_changes(self):
        self.path.write_bytes(b"abc")
        modified = self.path.stat().st_mtime_ns
        self.assertIsNone(verify_package_file(self.path, size_bytes=3, sha256=ABC_SHA256))
        self.assertEqual(self.path.read_bytes(), b"abc")
        self.assertEqual(self.path.stat().st_mtime_ns, modified)
        self.assertEqual(list(self.root.iterdir()), [self.path])

    def test_empty_file_requires_matching_size_and_hash(self):
        self.path.write_bytes(b"")
        verify_package_file(self.path, size_bytes=0,
                            sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
        with self.assertRaises(PackageVerificationError):
            verify_package_file(self.path, size_bytes=0, sha256=ABC_SHA256)

    def test_truncated_and_oversized_files_are_rejected(self):
        for content in (b"ab", b"abcd"):
            with self.subTest(content=content):
                self.path.write_bytes(content)
                with self.assertRaises(PackageVerificationError):
                    verify_package_file(self.path, size_bytes=3, sha256=ABC_SHA256)
                self.assertEqual(self.path.read_bytes(), content)

    def test_same_size_tampering_is_rejected(self):
        self.path.write_bytes(b"abd")
        with self.assertRaises(PackageVerificationError):
            verify_package_file(self.path, size_bytes=3, sha256=ABC_SHA256)

    def test_missing_file_and_directory_are_not_accepted(self):
        with self.assertRaises(FileNotFoundError):
            verify_package_file(self.path, size_bytes=3, sha256=ABC_SHA256)
        with self.assertRaises((OSError, PackageVerificationError)):
            verify_package_file(self.root, size_bytes=3, sha256=ABC_SHA256)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_invalid_expectations_are_rejected_before_file_access(self):
        for size in (-1, True, 3.0, "3", None):
            with self.subTest(size=size), self.assertRaises(ValueError):
                verify_package_file(self.path, size_bytes=size, sha256=ABC_SHA256)
        for digest in (None, 123, "", "a" * 63, "a" * 65, "g" * 64,
                       ABC_SHA256.upper(), ABC_SHA256 + "\n"):
            with self.subTest(digest=digest), self.assertRaises(ValueError):
                verify_package_file(self.path, size_bytes=3, sha256=digest)

    def test_access_errors_remain_visible(self):
        with patch("ak_weather.package_verification.Path.open", side_effect=PermissionError):
            with self.assertRaises(PermissionError):
                verify_package_file(self.path, size_bytes=3, sha256=ABC_SHA256)

    def test_size_change_after_initial_metadata_check_is_rejected(self):
        initial = SimpleNamespace(st_mode=stat.S_IFREG, st_size=3)
        for content in (b"ab", b"abcd"):
            with self.subTest(content=content):
                self.path.write_bytes(content)
                with patch("ak_weather.package_verification.os.fstat", return_value=initial):
                    with self.assertRaises(PackageVerificationError):
                        verify_package_file(self.path, size_bytes=3, sha256=ABC_SHA256)

    def test_content_across_multiple_read_blocks_is_checked(self):
        content = b"a" * (2 * 1024 * 1024) + b"tail"
        self.path.write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()
        verify_package_file(self.path, size_bytes=len(content), sha256=digest)
        with self.path.open("r+b") as stream:
            stream.seek(-1, 2)
            stream.write(b"!")
        with self.assertRaises(PackageVerificationError):
            verify_package_file(self.path, size_bytes=len(content), sha256=digest)


if __name__ == "__main__":
    unittest.main()
