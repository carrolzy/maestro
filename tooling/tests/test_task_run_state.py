import json
import tempfile
import unittest
from pathlib import Path

from update_task_run_state import update_task_run_state


class TaskRunStateTests(unittest.TestCase):
    def test_update_task_run_state_creates_status_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            runtime_root = Path(tmp_dir)
            output_path = update_task_run_state(
                runtime_root=runtime_root,
                project="example-wxapp",
                task_slug="2026-05-19-cart-consistency",
                state="packaged",
            )

            self.assertTrue(output_path.exists())
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["project"], "example-wxapp")
            self.assertEqual(payload["state"], "packaged")

    def test_update_task_run_state_appends_history_across_transitions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            runtime_root = Path(tmp_dir)
            task_slug = "2026-05-19-cart-consistency"

            update_task_run_state(
                runtime_root=runtime_root,
                project="example-wxapp",
                task_slug=task_slug,
                state="packaged",
            )
            output_path = update_task_run_state(
                runtime_root=runtime_root,
                project="example-wxapp",
                task_slug=task_slug,
                state="written_back",
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "written_back")
            self.assertEqual([item["state"] for item in payload["history"]], ["packaged", "written_back"])

    def test_closed_state_requires_governance_tier(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaisesRegex(ValueError, "governance_tier"):
                update_task_run_state(
                    runtime_root=Path(tmp_dir),
                    project="example-wxapp",
                    task_slug="2026-08-14-closeout-gate",
                    state="closed",
                )

    def test_l1_to_l3_closeout_requires_documentation_impact(self) -> None:
        for tier in ("L1", "L2", "L3"):
            with self.subTest(tier=tier), tempfile.TemporaryDirectory() as tmp_dir:
                with self.assertRaisesRegex(ValueError, "documentation_impact"):
                    update_task_run_state(
                        runtime_root=Path(tmp_dir),
                        project="example-wxapp",
                        task_slug=f"2026-08-14-{tier.lower()}-closeout",
                        state="closed",
                        governance_tier=tier,
                    )

    def test_l2_closeout_records_updated_documentation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = update_task_run_state(
                runtime_root=Path(tmp_dir),
                project="example-wxapp",
                task_slug="2026-08-14-l2-closeout",
                state="closed",
                governance_tier="L2",
                documentation_impact={
                    "status": "updated",
                    "files": ["README.zh-CN.md", "docs/task-routing.md"],
                    "reason": "记录用户可见的路由升级。",
                },
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["governance_tier"], "L2")
            self.assertEqual(payload["documentation_impact"]["status"], "updated")
            self.assertEqual(payload["documentation_impact"]["files"], ["README.zh-CN.md", "docs/task-routing.md"])
            self.assertEqual(payload["history"][-1]["governance_tier"], "L2")

    def test_l0_closeout_can_skip_documentation_with_explicit_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = update_task_run_state(
                runtime_root=Path(tmp_dir),
                project="example-wxapp",
                task_slug="2026-08-14-l0-closeout",
                state="closed",
                governance_tier="L0",
                documentation_impact={
                    "status": "not_needed",
                    "reason": "仅修正文案且不改变用法或配置。",
                },
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["documentation_impact"]["status"], "not_needed")

    def test_l0_closeout_cannot_skip_documentation_without_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaisesRegex(ValueError, "reason"):
                update_task_run_state(
                    runtime_root=Path(tmp_dir),
                    project="example-wxapp",
                    task_slug="2026-08-14-l0-closeout",
                    state="closed",
                    governance_tier="L0",
                    documentation_impact={"status": "not_needed", "reason": ""},
                )
