#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import code_search
from code_search import glob_files, grep_code, read_file_slice, repo_outline


def _seed_repo(root: Path) -> None:
    (root / "src").mkdir()
    (root / "src" / "cart.js").write_text(
        "export function addToCart(item) {\n"
        "  // 加入购物车\n"
        "  return cartStore.push(item)\n"
        "}\n"
        "\n"
        "export const checkout = async (order) => {\n"
        "  await submitOrder(order)\n"
        "}\n",
        encoding="utf-8",
    )
    (root / "src" / "user.py").write_text(
        "class UserService:\n"
        "    def login(self, name):\n"
        "        return token_for(name)\n",
        encoding="utf-8",
    )
    (root / "node_modules").mkdir()
    (root / "node_modules" / "lib.js").write_text("function addToCart() {}\n", encoding="utf-8")
    (root / "README.md").write_text("# Demo\naddToCart usage docs\n", encoding="utf-8")


class GrepCodeTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _seed_repo(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def _grep(self, **kwargs):
        return grep_code(repo_root=self.root, **kwargs)

    def test_finds_matches_with_line_numbers(self):
        result = self._grep(pattern="addToCart")
        paths = {m["path"] for m in result["matches"]}
        self.assertIn("src/cart.js", paths)
        self.assertIn("README.md", paths)
        cart_match = next(m for m in result["matches"] if m["path"] == "src/cart.js")
        self.assertEqual(cart_match["line"], 1)

    def test_glob_filter(self):
        result = self._grep(pattern="addToCart", glob="*.js")
        paths = {m["path"] for m in result["matches"]}
        self.assertEqual(paths, {"src/cart.js"})

    def test_case_insensitive(self):
        result = self._grep(pattern="ADDTOCART", case_insensitive=True)
        self.assertGreater(result["match_count"], 0)

    def test_fixed_string_escapes_regex(self):
        result = self._grep(pattern="push(item)", fixed_string=True)
        self.assertEqual(result["match_count"], 1)

    def test_cjk_content(self):
        result = self._grep(pattern="购物车")
        self.assertEqual(result["matches"][0]["path"], "src/cart.js")

    def test_max_matches_truncates(self):
        for i in range(10):
            (self.root / f"file{i}.txt").write_text("needle\n" * 5, encoding="utf-8")
        result = self._grep(pattern="needle", max_matches=3)
        self.assertEqual(result["match_count"], 3)
        self.assertTrue(result["truncated"])

    def test_empty_pattern_rejected(self):
        with self.assertRaises(ValueError):
            self._grep(pattern="")

    def test_pure_python_fallback_matches_rg_results(self):
        with mock.patch.object(code_search, "_rg_binary", return_value=None):
            result = self._grep(pattern="addToCart", glob="*.js")
        self.assertEqual(result["engine"], "python")
        paths = {m["path"] for m in result["matches"]}
        self.assertEqual(paths, {"src/cart.js"})

    def test_pure_python_skips_node_modules(self):
        with mock.patch.object(code_search, "_rg_binary", return_value=None):
            result = self._grep(pattern="addToCart")
        paths = {m["path"] for m in result["matches"]}
        self.assertNotIn("node_modules/lib.js", paths)

    def test_context_lines(self):
        with mock.patch.object(code_search, "_rg_binary", return_value=None):
            result = self._grep(pattern="return cartStore", context_lines=1)
        match = result["matches"][0]
        context_lines = {c["line"] for c in match["context"]}
        self.assertEqual(context_lines, {2, 4})


class GlobFilesTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _seed_repo(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def test_glob_recursive(self):
        result = glob_files(repo_root=self.root, pattern="**/*.js")
        paths = {f["path"] for f in result["files"]}
        self.assertIn("src/cart.js", paths)
        self.assertNotIn("node_modules/lib.js", paths)

    def test_glob_truncation(self):
        for i in range(5):
            (self.root / f"t{i}.css").write_text("a{}", encoding="utf-8")
        result = glob_files(repo_root=self.root, pattern="*.css", max_results=2)
        self.assertEqual(result["file_count"], 2)
        self.assertTrue(result["truncated"])


class ReadFileSliceTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _seed_repo(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def test_reads_range(self):
        result = read_file_slice(repo_root=self.root, file_path="src/cart.js", start_line=6, max_lines=2)
        self.assertEqual(result["start_line"], 6)
        self.assertIn("checkout", result["lines"][0]["text"])
        self.assertTrue(result["truncated"])

    def test_full_read_not_truncated(self):
        result = read_file_slice(repo_root=self.root, file_path="src/user.py")
        self.assertFalse(result["truncated"])
        self.assertEqual(result["total_lines"], 3)

    def test_path_escape_rejected(self):
        with self.assertRaises(ValueError):
            read_file_slice(repo_root=self.root / "src", file_path="../README.md")


class RepoOutlineTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _seed_repo(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def test_directory_tree_skips_noise(self):
        result = repo_outline(repo_root=self.root)
        paths = {e["path"] for e in result["entries"]}
        self.assertIn("src", paths)
        self.assertIn("src/cart.js", paths)
        self.assertNotIn("node_modules", paths)

    def test_file_symbols_js(self):
        result = repo_outline(repo_root=self.root, path="src/cart.js")
        names = {(s["name"], s["kind"]) for s in result["symbols"]}
        self.assertIn(("addToCart", "function"), names)
        self.assertIn(("checkout", "function"), names)

    def test_file_symbols_python(self):
        result = repo_outline(repo_root=self.root, path="src/user.py")
        names = {(s["name"], s["kind"]) for s in result["symbols"]}
        self.assertIn(("UserService", "class"), names)
        self.assertIn(("login", "function"), names)

    def test_unknown_path_rejected(self):
        with self.assertRaises(ValueError):
            repo_outline(repo_root=self.root, path="nope/missing.js")


if __name__ == "__main__":
    unittest.main()
