"""Tests for agent checkpoint system and A2A handoff."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from checkpoint import (
    Checkpoint,
    build_resume_context,
    list_checkpoints,
    load_latest_checkpoint,
    save_checkpoint,
)
from update_task_run_state import update_task_run_state


class CheckpointSaveLoadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_save_and_load_latest(self) -> None:
        cp = Checkpoint(
            agent="codex", step="intake", state="completed",
            summary="Built task package", output={"dir": "/tmp/out"},
            files_modified=["package.md"], next_hint="implementation",
        )
        save_checkpoint(self.root, "my-app", "task-1", cp)
        loaded = load_latest_checkpoint(self.root, "my-app", "task-1")
        assert loaded is not None
        self.assertEqual(loaded.agent, "codex")
        self.assertEqual(loaded.step, "intake")
        self.assertEqual(loaded.state, "completed")
        self.assertEqual(loaded.summary, "Built task package")
        self.assertEqual(loaded.output, {"dir": "/tmp/out"})
        self.assertEqual(loaded.files_modified, ["package.md"])
        self.assertEqual(loaded.next_hint, "implementation")
        self.assertTrue(loaded.timestamp)

    def test_latest_is_highest_seq(self) -> None:
        save_checkpoint(self.root, "app", "t1", Checkpoint(agent="codex", step="a", state="completed", summary="First"))
        save_checkpoint(self.root, "app", "t1", Checkpoint(agent="codex", step="b", state="completed", summary="Second"))
        save_checkpoint(self.root, "app", "t1", Checkpoint(agent="codex", step="c", state="in_progress", summary="Third"))
        latest = load_latest_checkpoint(self.root, "app", "t1")
        assert latest is not None
        self.assertEqual(latest.step, "c")
        self.assertEqual(latest.summary, "Third")

    def test_load_none_for_missing(self) -> None:
        self.assertIsNone(load_latest_checkpoint(self.root, "no", "task"))

    def test_list_returns_ordered(self) -> None:
        save_checkpoint(self.root, "app", "t2", Checkpoint(agent="codex", step="a", state="completed", summary="A"))
        save_checkpoint(self.root, "app", "t2", Checkpoint(agent="claude", step="b", state="completed", summary="B"))
        all_cps = list_checkpoints(self.root, "app", "t2")
        self.assertEqual(len(all_cps), 2)
        self.assertEqual(all_cps[0].agent, "codex")
        self.assertEqual(all_cps[1].agent, "claude")

    def test_list_empty_for_missing(self) -> None:
        self.assertEqual(list_checkpoints(self.root, "no", "task"), [])


class ResumeContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _seed_codex_workflow(self) -> None:
        """Simulate: Codex intakes → starts implementing → checkpoint."""
        update_task_run_state(
            runtime_root=self.root, project="app", task_slug="task-1",
            state="packaged", agent="codex",
        )
        save_checkpoint(self.root, "app", "task-1", Checkpoint(
            agent="codex", step="intake", state="completed",
            summary="Built task package for cart feature",
            output={"package_dir": "/tmp/packages/2026-06-04-cart"},
            files_modified=["package.md", "package.json"],
            next_hint="implementation",
        ))
        update_task_run_state(
            runtime_root=self.root, project="app", task_slug="task-1",
            state="in_progress", agent="codex",
        )
        save_checkpoint(self.root, "app", "task-1", Checkpoint(
            agent="codex", step="implementation", state="in_progress",
            summary="Started modifying cart.vue, midway through",
            files_modified=["components/cart/cart.vue"],
            next_hint="finish cart.vue changes, then verify",
        ))

    def test_can_resume(self) -> None:
        self._seed_codex_workflow()
        ctx = build_resume_context(self.root, "app", "task-1")
        self.assertTrue(ctx["can_resume"])
        self.assertEqual(ctx["last_agent"], "codex")
        self.assertEqual(ctx["last_state"], "in_progress")

    def test_cannot_resume_closed_task(self) -> None:
        update_task_run_state(
            runtime_root=self.root, project="app", task_slug="done",
            state="closed", agent="codex",
            governance_tier="L0",
            documentation_impact={
                "status": "not_needed",
                "reason": "测试仅验证关闭任务不可恢复。",
            },
        )
        ctx = build_resume_context(self.root, "app", "done")
        self.assertFalse(ctx["can_resume"])

    def test_can_resume_handed_off_task(self) -> None:
        """A handed-off task MUST stay resumable so the next agent can pick it up."""
        self._seed_codex_workflow()
        save_checkpoint(self.root, "app", "task-1", Checkpoint(
            agent="codex", step="handoff", state="completed",
            summary="Handed off to claude",
            next_hint="Task handed to claude. Use resume_task to pick up.",
        ))
        update_task_run_state(
            runtime_root=self.root, project="app", task_slug="task-1",
            state="handed_off", agent="codex",
        )
        ctx = build_resume_context(self.root, "app", "task-1")
        self.assertTrue(ctx["can_resume"])
        self.assertEqual(ctx["last_state"], "handed_off")

    def test_recent_checkpoints_expose_agent_not_seq(self) -> None:
        """recent_checkpoints carries the agent name under an 'agent' key."""
        self._seed_codex_workflow()
        ctx = build_resume_context(self.root, "app", "task-1")
        self.assertTrue(ctx["recent_checkpoints"])
        latest = ctx["recent_checkpoints"][-1]
        self.assertIn("agent", latest)
        self.assertNotIn("seq", latest)
        self.assertEqual(latest["agent"], "codex")

    def test_completed_steps_only(self) -> None:
        self._seed_codex_workflow()
        ctx = build_resume_context(self.root, "app", "task-1")
        # Only "intake" is completed; "implementation" is in_progress
        self.assertEqual(len(ctx["completed_steps"]), 1)
        self.assertEqual(ctx["completed_steps"][0]["step"], "intake")

    def test_files_modified_deduped(self) -> None:
        self._seed_codex_workflow()
        ctx = build_resume_context(self.root, "app", "task-1")
        self.assertIn("components/cart/cart.vue", ctx["files_modified"])

    def test_next_hint_from_latest(self) -> None:
        self._seed_codex_workflow()
        ctx = build_resume_context(self.root, "app", "task-1")
        self.assertEqual(ctx["next_step_hint"], "finish cart.vue changes, then verify")

    def test_resume_context_pack_is_markdown(self) -> None:
        self._seed_codex_workflow()
        ctx = build_resume_context(self.root, "app", "task-1")
        pack = ctx["resume_context_pack"]
        self.assertIn("# Task Resume Pack", pack)
        self.assertIn("codex", pack)
        self.assertIn("cart", pack)
        self.assertIn("## Instructions for Resuming Agent", pack)
        self.assertIn("Do NOT redo completed steps", pack)

    def test_resume_context_pack_for_prompt_injection(self) -> None:
        """The pack must be self-contained — injectable without further tools."""
        self._seed_codex_workflow()
        ctx = build_resume_context(self.root, "app", "task-1")
        pack = ctx["resume_context_pack"]
        # Should contain all critical context a new agent needs
        self.assertIn("app", pack)
        self.assertIn("task-1", pack)
        self.assertIn("intake", pack)
        self.assertIn("cart.vue", pack)


class AgentStateTrackingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_agent_recorded_in_status(self) -> None:
        import json
        update_task_run_state(
            runtime_root=self.root, project="app", task_slug="t1",
            state="in_progress", agent="claude",
        )
        status = json.loads((self.root / "task-runs" / "app" / "t1" / "status.json").read_text(encoding="utf-8"))
        self.assertEqual(status["agent"], "claude")
        self.assertEqual(status["history"][0]["agent"], "claude")

    def test_agent_carried_forward(self) -> None:
        import json
        update_task_run_state(
            runtime_root=self.root, project="app", task_slug="t2",
            state="packaged", agent="codex",
        )
        # Second call without agent — should carry forward "codex"
        update_task_run_state(
            runtime_root=self.root, project="app", task_slug="t2",
            state="in_progress",
        )
        status = json.loads((self.root / "task-runs" / "app" / "t2" / "status.json").read_text(encoding="utf-8"))
        self.assertEqual(status["agent"], "codex")

    def test_backward_compat_no_agent(self) -> None:
        """Closing without an agent still works when closeout metadata is present."""
        update_task_run_state(
            runtime_root=self.root, project="app", task_slug="t3",
            state="closed",
            governance_tier="L0",
            documentation_impact={
                "status": "not_needed",
                "reason": "测试不涉及用户可见文档。",
            },
        )
        self.assertTrue((self.root / "task-runs" / "app" / "t3" / "status.json").exists())


if __name__ == "__main__":
    unittest.main()
