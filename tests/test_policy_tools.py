from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pithon.policy import PolicyError, WorkspacePolicy
from pithon.redaction import redact_text
from pithon.tools import ToolRegistry


class PolicyAndToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.decisions: list[str] = []
        self.approve = True
        self.policy = WorkspacePolicy(self.root, self._confirm)
        self.tools = ToolRegistry(self.policy)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _confirm(self, prompt: str) -> bool:
        self.decisions.append(prompt)
        return self.approve

    def test_blocks_secret_paths_and_parent_traversal(self) -> None:
        (self.root / ".env").write_text("TOKEN=secret-value", encoding="utf-8")
        with self.assertRaises(PolicyError):
            self.policy.resolve(".env")
        with self.assertRaises(PolicyError):
            self.policy.resolve("../outside")
        with self.assertRaises(PolicyError):
            self.policy.resolve("private.pem", must_exist=False)

    def test_rejects_symlinks(self) -> None:
        target = self.root / "target.txt"
        target.write_text("safe", encoding="utf-8")
        link = self.root / "link.txt"
        link.symlink_to(target)
        with self.assertRaises(PolicyError):
            self.policy.resolve("link.txt")

    def test_read_redacts_provider_bound_content(self) -> None:
        (self.root / "config.txt").write_text(
            "API_TOKEN=abcdefghijklmnop\nvalue=ok\n", encoding="utf-8"
        )
        payload = json.loads(self.tools.execute("read_file", {"path": "config.txt"}))
        self.assertTrue(payload["ok"])
        content = payload["result"]["content"]
        self.assertIn("API_TOKEN=<redacted>", content)
        self.assertNotIn("abcdefghijklmnop", content)

    def test_edit_requires_confirmation_and_is_atomic(self) -> None:
        path = self.root / "sample.py"
        path.write_text("before\n", encoding="utf-8")
        self.approve = False
        declined = json.loads(self.tools.execute(
            "edit_file", {"path": "sample.py", "old_text": "before", "new_text": "after"}
        ))
        self.assertFalse(declined["result"]["applied"])
        self.assertEqual(path.read_text(encoding="utf-8"), "before\n")

        self.approve = True
        applied = json.loads(self.tools.execute(
            "edit_file", {"path": "sample.py", "old_text": "before", "new_text": "after"}
        ))
        self.assertTrue(applied["result"]["applied"])
        self.assertEqual(path.read_text(encoding="utf-8"), "after\n")
        self.assertIn("-before", self.decisions[-1])
        self.assertIn("+after", self.decisions[-1])

    def test_rejects_ambiguous_and_oversized_edits(self) -> None:
        path = self.root / "sample.txt"
        path.write_text("same same", encoding="utf-8")
        ambiguous = json.loads(self.tools.execute(
            "edit_file", {"path": "sample.txt", "old_text": "same", "new_text": "new"}
        ))
        self.assertFalse(ambiguous["ok"])
        oversized = json.loads(self.tools.execute(
            "write_file", {"path": "large.txt", "content": "x" * 70_000}
        ))
        self.assertFalse(oversized["ok"])
        self.assertFalse((self.root / "large.txt").exists())

    def test_redacts_common_token_and_private_key_forms(self) -> None:
        raw = "ghp_abcdefghijklmnopqrstuvwxyz123456\n-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----"
        redacted = redact_text(raw)
        self.assertNotIn("ghp_", redacted)
        self.assertNotIn("abc", redacted)
        self.assertIn("<redacted-private-key>", redacted)


if __name__ == "__main__":
    unittest.main()
