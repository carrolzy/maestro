#!/usr/bin/env python3
from __future__ import annotations

import gzip
import json
import os
import subprocess
import tarfile
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from artifact_gc import archive, clean, load_policy, restore, scan
from temp_registry import register_temp_file


def _make_system_root(tmp: Path) -> Path:
    (tmp / "base").mkdir()
    (tmp / "runtime").mkdir()
    (tmp / "memory" / "projects").mkdir(parents=True)
    return tmp


def _age(path: Path, days: int) -> None:
    """Set mtime of path (and its tree) to `days` days ago."""
    stamp = time.time() - days * 86400
    targets = [path, *path.rglob("*")] if path.is_dir() else [path]
    for target in targets:
        os.utime(target, (stamp, stamp))


def _make_task_run(root: Path, project: str, slug: str, *, days_old: int) -> Path:
    d = root / "runtime" / "task-runs" / project / slug
    d.mkdir(parents=True)
    (d / "status.json").write_text('{"state": "closed"}', encoding="utf-8")
    _age(d, days_old)
    return d


class ArtifactGcScanTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = _make_system_root(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def test_scan_reports_expired_task_run(self):
        _make_task_run(self.root, "proj", "old-task", days_old=120)
        _make_task_run(self.root, "proj", "fresh-task", days_old=1)
        report = scan(self.root)
        expired = report["categories"]["task_runs"]["expired"]
        self.assertEqual([e["slug"] for e in expired], ["old-task"])
        self.assertGreater(report["total_reclaimable_bytes"], 0)

    def test_scan_respects_policy_override(self):
        (self.root / "base" / "retention.json").write_text(
            json.dumps({"categories": {"task_runs": {"ttl_days": 5}}}), encoding="utf-8"
        )
        _make_task_run(self.root, "proj", "week-old", days_old=7)
        report = scan(self.root)
        self.assertEqual(len(report["categories"]["task_runs"]["expired"]), 1)

    def test_scan_skips_active_task(self):
        _make_task_run(self.root, "proj", "old-task", days_old=120)
        pointer = {"project": "proj", "task_slug": "old-task", "agent": "test",
                   "started_at": "2026-01-01T00:00:00+00:00"}
        (self.root / "runtime" / "active-task.json").write_text(
            json.dumps(pointer), encoding="utf-8"
        )
        report = scan(self.root)
        self.assertEqual(report["categories"]["task_runs"]["expired"], [])

    def test_scan_reports_expired_memory_case(self):
        case_dir = self.root / "memory" / "projects" / "proj" / "cases"
        case_dir.mkdir(parents=True)
        case = case_dir / "2025-01-01-old.md"
        case.write_text("# old case\n" * 50, encoding="utf-8")
        _age(case, 200)
        report = scan(self.root)
        self.assertEqual(len(report["categories"]["memory_cases"]["expired"]), 1)

    def test_scan_is_read_only(self):
        d = _make_task_run(self.root, "proj", "old-task", days_old=120)
        scan(self.root)
        self.assertTrue(d.exists())


class ArtifactGcArchiveTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = _make_system_root(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def test_archive_compresses_and_removes_original(self):
        d = _make_task_run(self.root, "proj", "old-task", days_old=120)
        result = archive(self.root)
        self.assertEqual(result["count"], 1)
        self.assertFalse(d.exists())
        dest = self.root / "runtime" / "archive" / "task-runs" / "proj" / "old-task.tar.gz"
        self.assertTrue(dest.exists())
        with tarfile.open(dest) as tar:
            names = tar.getnames()
        self.assertIn("old-task/status.json", names)

    def test_archive_leaves_fresh_artifacts_alone(self):
        d = _make_task_run(self.root, "proj", "fresh", days_old=1)
        result = archive(self.root)
        self.assertEqual(result["count"], 0)
        self.assertTrue(d.exists())

    def test_archive_memory_case_to_md_gz(self):
        case_dir = self.root / "memory" / "projects" / "proj" / "cases"
        case_dir.mkdir(parents=True)
        case = case_dir / "2025-01-01-old.md"
        case.write_text("# archived knowledge\n", encoding="utf-8")
        _age(case, 200)
        result = archive(self.root)
        self.assertEqual(result["count"], 1)
        self.assertFalse(case.exists())
        gz = case.with_suffix(".md.gz")
        self.assertTrue(gz.exists())
        with gzip.open(gz, "rt", encoding="utf-8") as fh:
            self.assertIn("archived knowledge", fh.read())

    def test_restore_roundtrip_task_run(self):
        _make_task_run(self.root, "proj", "old-task", days_old=120)
        archive(self.root)
        dest = self.root / "runtime" / "archive" / "task-runs" / "proj" / "old-task.tar.gz"
        result = restore(self.root, archive_path=str(dest))
        restored = self.root / "runtime" / "task-runs" / "proj" / "old-task"
        self.assertTrue((restored / "status.json").exists())
        self.assertFalse(dest.exists())
        self.assertEqual(result["restored"], str(restored))

    def test_restore_roundtrip_memory_case(self):
        case_dir = self.root / "memory" / "projects" / "proj" / "cases"
        case_dir.mkdir(parents=True)
        case = case_dir / "2025-01-01-old.md"
        case.write_text("# knowledge\n", encoding="utf-8")
        _age(case, 200)
        archive(self.root)
        gz = case.with_suffix(".md.gz")
        restore(self.root, archive_path=str(gz))
        self.assertTrue(case.exists())
        self.assertIn("knowledge", case.read_text(encoding="utf-8"))
        self.assertFalse(gz.exists())

    def test_restore_rejects_unknown_type(self):
        bogus = self.root / "runtime" / "whatever.zip"
        bogus.write_bytes(b"nope")
        with self.assertRaises(ValueError):
            restore(self.root, archive_path=str(bogus))


class ArtifactGcCleanTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = _make_system_root(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def _make_scratch(self, project: str, slug: str, *, days_old: int) -> Path:
        d = self.root / "runtime" / "scratch" / project / slug
        d.mkdir(parents=True)
        (d / "probe.test.js").write_text("console.log(1)\n", encoding="utf-8")
        _age(d, days_old)
        return d

    def test_clean_dry_run_by_default(self):
        d = self._make_scratch("proj", "old", days_old=60)
        result = clean(self.root)
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["deleted"], [str(d)])
        self.assertTrue(d.exists())

    def test_clean_apply_deletes_expired_scratch(self):
        d = self._make_scratch("proj", "old", days_old=60)
        fresh = self._make_scratch("proj2", "fresh", days_old=2)
        result = clean(self.root, apply=True)
        self.assertFalse(result["dry_run"])
        self.assertFalse(d.exists())
        self.assertTrue(fresh.exists())

    def test_clean_deletes_expired_registered_temp_file(self):
        temp = self.root / "some-biz-repo"
        temp.mkdir()
        target = temp / "verify-login.cjs"
        target.write_text("// probe\n", encoding="utf-8")
        register_temp_file(
            self.root / "runtime", file_path=str(target),
            project="proj", task_slug="t1", ttl_days=1,
        )
        future = datetime.now(timezone.utc) + timedelta(days=2)
        result = clean(self.root, now=future, apply=True)
        self.assertIn(str(target.resolve()), result["deleted"])
        self.assertFalse(target.exists())
        # registry entry dropped too
        from temp_registry import list_temp_files
        self.assertEqual(list_temp_files(self.root / "runtime"), [])

    def test_clean_never_deletes_git_tracked_temp_file(self):
        repo = self.root / "biz-repo"
        repo.mkdir()
        subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
        tracked = repo / "verify-flow.cjs"
        tracked.write_text("// tracked\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "verify-flow.cjs"], check=True)
        register_temp_file(
            self.root / "runtime", file_path=str(tracked),
            project="proj", task_slug="t1", ttl_days=1,
        )
        future = datetime.now(timezone.utc) + timedelta(days=2)
        result = clean(self.root, now=future, apply=True)
        self.assertTrue(tracked.exists())
        self.assertEqual(result["skipped"][0]["reason"], "git-tracked")


class RetentionPolicyTest(unittest.TestCase):
    def test_defaults_when_no_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            policy = load_policy(Path(tmp))
            self.assertEqual(policy["task_runs"]["ttl_days"], 90)
            self.assertEqual(policy["memory_cases"]["action"], "archive")

    def test_partial_override_merges(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "base").mkdir()
            (root / "base" / "retention.json").write_text(
                json.dumps({"categories": {"perf_cases": {"ttl_days": 7}}}),
                encoding="utf-8",
            )
            policy = load_policy(root)
            self.assertEqual(policy["perf_cases"]["ttl_days"], 7)
            self.assertEqual(policy["task_runs"]["ttl_days"], 90)


if __name__ == "__main__":
    unittest.main()
