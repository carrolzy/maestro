"""Tests for active-task pointer and the forced checkpoint hook."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from active_task import clear_active_task, get_active_task, set_active_task
from checkpoint import append_to_session_checkpoint, list_checkpoints, save_checkpoint, Checkpoint

TOOLING_DIR = Path(__file__).resolve().parents[1]
HOOK_SCRIPT = TOOLING_DIR / "hooks" / "checkpoint_hook.py"


class ActiveTaskPointerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_set_and_get(self) -> None:
        set_active_task(self.root, "app", "task-1", "claude")
        active = get_active_task(self.root)
        assert active is not None
        self.assertEqual(active["project"], "app")
        self.assertEqual(active["task_slug"], "task-1")
        self.assertEqual(active["agent"], "claude")
        self.assertTrue(active["started_at"])

    def test_get_none_when_unset(self) -> None:
        self.assertIsNone(get_active_task(self.root))

    def test_clear(self) -> None:
        set_active_task(self.root, "app", "task-1", "claude")
        self.assertTrue(clear_active_task(self.root))
        self.assertIsNone(get_active_task(self.root))

    def test_clear_returns_false_when_nothing(self) -> None:
        self.assertFalse(clear_active_task(self.root))

    def test_set_overwrites(self) -> None:
        set_active_task(self.root, "app", "task-1", "codex")
        set_active_task(self.root, "app", "task-2", "claude")
        active = get_active_task(self.root)
        self.assertEqual(active["task_slug"], "task-2")
        self.assertEqual(active["agent"], "claude")


class SessionMergeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_consecutive_edits_merge_into_one(self) -> None:
        for f in ["a.vue", "b.vue", "c.js"]:
            append_to_session_checkpoint(
                self.root, "app", "t1", agent="claude", session_id="s1", file_modified=f
            )
        cps = list_checkpoints(self.root, "app", "t1")
        self.assertEqual(len(cps), 1)
        self.assertEqual(cps[0].files_modified, ["a.vue", "b.vue", "c.js"])
        self.assertEqual(cps[0].step, "auto-edit")

    def test_duplicate_file_not_added_twice(self) -> None:
        append_to_session_checkpoint(self.root, "app", "t1", agent="claude", session_id="s1", file_modified="a.vue")
        append_to_session_checkpoint(self.root, "app", "t1", agent="claude", session_id="s1", file_modified="a.vue")
        cps = list_checkpoints(self.root, "app", "t1")
        self.assertEqual(cps[0].files_modified, ["a.vue"])

    def test_different_session_starts_new_checkpoint(self) -> None:
        append_to_session_checkpoint(self.root, "app", "t1", agent="claude", session_id="s1", file_modified="a.vue")
        append_to_session_checkpoint(self.root, "app", "t1", agent="codex", session_id="s2", file_modified="b.vue")
        cps = list_checkpoints(self.root, "app", "t1")
        self.assertEqual(len(cps), 2)

    def test_explicit_checkpoint_seals_auto_edit(self) -> None:
        # auto-edit, then explicit, then auto-edit again → 3 checkpoints
        append_to_session_checkpoint(self.root, "app", "t1", agent="claude", session_id="s1", file_modified="a.vue")
        save_checkpoint(self.root, "app", "t1", Checkpoint(
            agent="claude", step="verification", state="completed", summary="ran tests"
        ))
        append_to_session_checkpoint(self.root, "app", "t1", agent="claude", session_id="s1", file_modified="b.vue")
        cps = list_checkpoints(self.root, "app", "t1")
        self.assertEqual(len(cps), 3)
        self.assertEqual(cps[0].step, "auto-edit")
        self.assertEqual(cps[0].files_modified, ["a.vue"])
        self.assertEqual(cps[1].step, "verification")
        self.assertEqual(cps[2].step, "auto-edit")
        self.assertEqual(cps[2].files_modified, ["b.vue"])


class HookScriptTests(unittest.TestCase):
    """Drive the actual hook script as a subprocess (like Claude Code does)."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.runtime = self.root / "runtime"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run_hook(self, payload: dict) -> int:
        env = {**os.environ, "PYTHONPATH": str(TOOLING_DIR), "AI_EFF_RUNTIME_ROOT": str(self.runtime)}
        result = subprocess.run(
            [sys.executable, str(HOOK_SCRIPT)],
            input=json.dumps(payload), text=True, env=env, capture_output=True,
        )
        return result.returncode

    def test_no_active_task_is_silent(self) -> None:
        rc = self._run_hook({"tool_name": "Edit", "tool_input": {"file_path": "a.vue"}, "session_id": "s1"})
        self.assertEqual(rc, 0)
        self.assertEqual(list_checkpoints(self.runtime, "app", "t1"), [])

    def test_edit_with_active_task_records_checkpoint(self) -> None:
        set_active_task(self.runtime, "app", "t1", "claude")
        rc = self._run_hook({"tool_name": "Edit", "tool_input": {"file_path": "a.vue"}, "session_id": "s1"})
        self.assertEqual(rc, 0)
        cps = list_checkpoints(self.runtime, "app", "t1")
        self.assertEqual(len(cps), 1)
        self.assertIn("a.vue", cps[0].files_modified)

    def test_three_edits_merge(self) -> None:
        set_active_task(self.runtime, "app", "t1", "claude")
        for f in ["a.vue", "b.vue", "c.js"]:
            self._run_hook({"tool_name": "Edit", "tool_input": {"file_path": f}, "session_id": "s1"})
        cps = list_checkpoints(self.runtime, "app", "t1")
        self.assertEqual(len(cps), 1)
        self.assertEqual(len(cps[0].files_modified), 3)

    def test_non_edit_tool_ignored(self) -> None:
        set_active_task(self.runtime, "app", "t1", "claude")
        rc = self._run_hook({"tool_name": "Bash", "tool_input": {"command": "ls"}, "session_id": "s1"})
        self.assertEqual(rc, 0)
        self.assertEqual(list_checkpoints(self.runtime, "app", "t1"), [])

    def test_malformed_payload_is_silent(self) -> None:
        env = {**os.environ, "PYTHONPATH": str(TOOLING_DIR), "AI_EFF_RUNTIME_ROOT": str(self.runtime)}
        result = subprocess.run(
            [sys.executable, str(HOOK_SCRIPT)],
            input="not json at all", text=True, env=env, capture_output=True,
        )
        self.assertEqual(result.returncode, 0)

    def test_write_tool_recorded(self) -> None:
        set_active_task(self.runtime, "app", "t1", "claude")
        rc = self._run_hook({"tool_name": "Write", "tool_input": {"file_path": "new.js"}, "session_id": "s1"})
        self.assertEqual(rc, 0)
        cps = list_checkpoints(self.runtime, "app", "t1")
        self.assertEqual(len(cps), 1)


if __name__ == "__main__":
    unittest.main()
