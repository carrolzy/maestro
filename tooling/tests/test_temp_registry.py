#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from temp_registry import (
    expired_temp_files,
    list_temp_files,
    matches_temp_pattern,
    refresh_task_temp_files,
    register_temp_file,
    remove_entries,
)


class TempRegistryTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.runtime = Path(self._tmp.name) / "runtime"
        self.runtime.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def test_register_and_list(self):
        entry = register_temp_file(
            self.runtime, file_path="/tmp/x/test-probe.cjs",
            project="proj", task_slug="t1", reason="post-release check",
        )
        self.assertEqual(entry["project"], "proj")
        entries = list_temp_files(self.runtime)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["reason"], "post-release check")

    def test_reregister_refreshes_not_duplicates(self):
        register_temp_file(self.runtime, file_path="/tmp/a.cjs", project="p", task_slug="t", ttl_days=1)
        register_temp_file(self.runtime, file_path="/tmp/a.cjs", project="p", task_slug="t", ttl_days=99)
        entries = list_temp_files(self.runtime)
        self.assertEqual(len(entries), 1)

    def test_list_filter_by_project(self):
        register_temp_file(self.runtime, file_path="/tmp/a.cjs", project="p1", task_slug="t")
        register_temp_file(self.runtime, file_path="/tmp/b.cjs", project="p2", task_slug="t")
        self.assertEqual(len(list_temp_files(self.runtime, project="p1")), 1)

    def test_expired_detection(self):
        register_temp_file(self.runtime, file_path="/tmp/a.cjs", project="p", task_slug="t", ttl_days=5)
        now = datetime.now(timezone.utc)
        self.assertEqual(expired_temp_files(self.runtime, now=now), [])
        future = now + timedelta(days=6)
        self.assertEqual(len(expired_temp_files(self.runtime, now=future)), 1)

    def test_refresh_restarts_ttl_at_task_close(self):
        register_temp_file(self.runtime, file_path="/tmp/a.cjs", project="p", task_slug="t", ttl_days=1)
        # About to expire — then the task closes and the clock restarts.
        refreshed = refresh_task_temp_files(self.runtime, project="p", task_slug="t", ttl_days=30)
        self.assertEqual(refreshed, 1)
        soon = datetime.now(timezone.utc) + timedelta(days=2)
        self.assertEqual(expired_temp_files(self.runtime, now=soon), [])

    def test_remove_entries(self):
        register_temp_file(self.runtime, file_path="/tmp/a.cjs", project="p", task_slug="t")
        removed = remove_entries(self.runtime, ["/tmp/a.cjs"])
        self.assertEqual(removed, 1)
        self.assertEqual(list_temp_files(self.runtime), [])

    def test_temp_name_patterns(self):
        for name in ("tmp-check.js", "cart-debug.cjs", "a.test.cjs", "verify-login.py", "scratch-1.js"):
            self.assertTrue(matches_temp_pattern(name), name)
        for name in ("index.js", "cart.spec.ts", "app.test.js"):
            # app.test.js is a *tracked test* convention in many repos — only
            # .cjs/.mjs probe variants are auto-flagged.
            self.assertFalse(matches_temp_pattern(name), name)


if __name__ == "__main__":
    unittest.main()
