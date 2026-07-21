#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from test_doctor import _anchor_name, _is_task_named, audit_tests


def _write(path: Path, content: str = "// t\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), *args],
        check=True, capture_output=True,
        env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
             "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin:/usr/local/bin"},
    )


class AnchorNameTest(unittest.TestCase):
    def test_common_shapes(self):
        cases = {
            "test_cart.py": "cart",
            "cart.spec.ts": "cart",
            "cart.test.js": "cart",
            "test-cart-fix.js": "cart-fix",
            "spec_user.py": "user",
        }
        for filename, expected in cases.items():
            self.assertEqual(_anchor_name(Path(filename)), expected, filename)


class TaskNamedTest(unittest.TestCase):
    def test_task_suffixes_flagged(self):
        for name in ("test-cart-fix.js", "test-cart-final.cjs", "cart-v2.test.js",
                     "test-cart-2.js", "test-login-debug.js", "test-2026-07-01-cart.js"):
            self.assertTrue(_is_task_named(name), name)

    def test_canonical_names_not_flagged(self):
        for name in ("test_cart.py", "cart.spec.ts", "user.test.js", "test_workflow.py"):
            self.assertFalse(_is_task_named(name), name)


class AuditTestsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_orphaned_test_detected(self):
        _write(self.root / "src" / "cart.js")
        _write(self.root / "tests" / "test_cart.js")
        _write(self.root / "tests" / "test_wishlist.js")  # wishlist.js does not exist
        report = audit_tests(repo_root=self.root)
        orphans = [f["path"] for f in report["findings"] if f["category"] == "orphaned"]
        self.assertEqual(orphans, ["tests/test_wishlist.js"])

    def test_task_named_detected_and_anchored_to_real_module(self):
        _write(self.root / "src" / "cart.js")
        _write(self.root / "tests" / "test-cart-fix.js")
        report = audit_tests(repo_root=self.root)
        cats = {f["category"] for f in report["findings"] if f["path"] == "tests/test-cart-fix.js"}
        self.assertIn("task_named", cats)
        self.assertNotIn("orphaned", cats)  # trimmed anchor resolves to cart.js

    def test_duplicate_coverage_detected(self):
        _write(self.root / "src" / "cart.js")
        _write(self.root / "tests" / "test_cart.js")
        _write(self.root / "tests" / "cart.spec.js")
        report = audit_tests(repo_root=self.root)
        dups = [f for f in report["findings"] if f["category"] == "duplicate_coverage"]
        self.assertEqual(len(dups), 2)

    def test_clean_suite_yields_no_findings(self):
        _write(self.root / "src" / "cart.js")
        _write(self.root / "tests" / "test_cart.js")
        report = audit_tests(repo_root=self.root)
        self.assertEqual(report["finding_count"], 0)
        self.assertFalse(report["git_history_checked"])

    def test_nested_test_dirs_found(self):
        _write(self.root / "src" / "cart.js")
        _write(self.root / "src" / "__tests__" / "cart.test.js")
        report = audit_tests(repo_root=self.root)
        self.assertIn("src/__tests__", report["test_dirs"])
        self.assertEqual(report["test_file_count"], 1)

    def test_stale_detection_via_git(self):
        _git(self.root, "init", "-q")
        _write(self.root / "src" / "cart.js", "v1\n")
        _write(self.root / "tests" / "test_cart.js")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "initial")
        # Source evolves 5 times; the test never changes.
        for i in range(5):
            _write(self.root / "src" / "cart.js", f"v{i + 2}\n")
            _git(self.root, "add", "-A")
            _git(self.root, "commit", "-qm", f"change {i}")
        report = audit_tests(repo_root=self.root, stale_threshold=5)
        self.assertTrue(report["git_history_checked"])
        stale = [f for f in report["findings"] if f["category"] == "stale"]
        self.assertEqual(len(stale), 1)
        self.assertEqual(stale[0]["path"], "tests/test_cart.js")

    def test_fresh_test_not_stale(self):
        _git(self.root, "init", "-q")
        _write(self.root / "src" / "cart.js", "v1\n")
        _write(self.root / "tests" / "test_cart.js")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "initial")
        report = audit_tests(repo_root=self.root)
        self.assertEqual([f for f in report["findings"] if f["category"] == "stale"], [])

    def test_report_is_read_only(self):
        _write(self.root / "tests" / "test-orphan-fix.js")
        audit_tests(repo_root=self.root)
        self.assertTrue((self.root / "tests" / "test-orphan-fix.js").exists())

    def test_bad_repo_root_rejected(self):
        with self.assertRaises(ValueError):
            audit_tests(repo_root=self.root / "nope")

    def test_no_false_orphans_for_fuzzy_and_integration_anchors(self):
        # Regression: real Maestro layouts that a naive exact-stem match
        # falsely flagged as orphaned on first live run.
        _write(self.root / "src" / "workflow_engine.py")      # test_workflow ↔ prefix
        _write(self.root / "src" / "update_task_run_state.py")  # ↔ containment
        _write(self.root / "src" / "adapters" / "openai.py")  # test_adapters ↔ dir name
        _write(self.root / "src" / "onboard_project.py")      # onboarding ↔ word prefix
        for name in ("test_workflow.py", "test_task_run_state.py",
                     "test_adapters.py", "test_onboarding.py",
                     "test_mcp_conformance.py"):              # integration exemption
            _write(self.root / "tests" / name, "# t\n")
        report = audit_tests(repo_root=self.root)
        self.assertEqual(
            [f for f in report["findings"] if f["category"] == "orphaned"], []
        )


if __name__ == "__main__":
    unittest.main()
