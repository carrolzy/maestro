from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from path_safety import require_descendant, resolve_relative_child


class PathSafetyTests(unittest.TestCase):
    def test_resolve_relative_child_accepts_nested_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "vault"
            self.assertEqual(
                resolve_relative_child(root, "notes/entry.md"),
                (root / "notes" / "entry.md").resolve(),
            )

    def test_resolve_relative_child_rejects_parent_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "vault"
            with self.assertRaisesRegex(ValueError, "escapes root"):
                resolve_relative_child(root, "../outside.md")

    def test_resolve_relative_child_rejects_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "vault"
            with self.assertRaisesRegex(ValueError, "relative"):
                resolve_relative_child(root, str(Path(tmp_dir) / "outside.md"))

    def test_require_descendant_rejects_prefix_sibling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "repo"
            sibling = Path(tmp_dir) / "repo-other" / "file.md"
            with self.assertRaisesRegex(ValueError, "escapes root"):
                require_descendant(root, sibling)


if __name__ == "__main__":
    unittest.main()
