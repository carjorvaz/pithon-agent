from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from pithon.cli import _consume_api_key_file


@unittest.skipUnless(hasattr(os, "O_NOFOLLOW"), "platform lacks O_NOFOLLOW")
class ApiKeyFileTests(unittest.TestCase):
    def test_consumes_mode_0600_regular_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "key"
            path.write_text("secret-value\n", encoding="utf-8")
            path.chmod(0o600)
            self.assertEqual(_consume_api_key_file(path), "secret-value")
            self.assertFalse(path.exists())

    def test_rejects_group_readable_file_without_deleting_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "key"
            path.write_text("secret-value\n", encoding="utf-8")
            path.chmod(0o640)
            with self.assertRaisesRegex(ValueError, "group/others"):
                _consume_api_key_file(path)
            self.assertTrue(path.exists())

    def test_rejects_symlink_without_consuming_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "target"
            target.write_text("secret-value\n", encoding="utf-8")
            target.chmod(0o600)
            link = Path(directory) / "link"
            link.symlink_to(target)
            with self.assertRaises(OSError):
                _consume_api_key_file(link)
            self.assertEqual(target.read_text(encoding="utf-8"), "secret-value\n")


if __name__ == "__main__":
    unittest.main()
