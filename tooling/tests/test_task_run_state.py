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
