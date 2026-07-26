import tempfile
import unittest
import json
from pathlib import Path

from ai_efficiency_mcp_server import AiEfficiencyMcpServer
from workflow_engine import WorkflowEngine
from workflow_state import (
    StepState,
    aggregate_state,
    can_transition,
    is_terminal,
    transition,
)


def _seed_system(root: Path) -> None:
    proj = root / "projects" / "alpha"
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "business-context.md").write_text(
        "# Business Context\n\n## Project in One Sentence\n\nAlpha project for workflow tests.\n",
        encoding="utf-8",
    )
    (proj / "project-override.md").write_text("# Project Override\n\n## Project Terms\n\n- test\n", encoding="utf-8")
    (proj / "task-context.md").write_text("# Task Context\n\n## Current Task\n\n- test\n", encoding="utf-8")
    templates = root / "templates"
    templates.mkdir(parents=True, exist_ok=True)
    for n in ("business-context", "project-override", "task-context"):
        (templates / f"{n}.md").write_text(f"# {n}\n\n## Section\n\nplaceholder\n", encoding="utf-8")


# ── state machine ─────────────────────────────────────────────────────


class StateMachineTests(unittest.TestCase):
    def test_valid_transitions(self) -> None:
        self.assertTrue(can_transition(StepState.PENDING, StepState.IN_PROGRESS))
        self.assertTrue(can_transition(StepState.IN_PROGRESS, StepState.VERIFYING))
        self.assertTrue(can_transition(StepState.IN_PROGRESS, StepState.COMPLETED))
        self.assertTrue(can_transition(StepState.IN_PROGRESS, StepState.FAILED))
        self.assertTrue(can_transition(StepState.VERIFYING, StepState.COMPLETED))
        self.assertTrue(can_transition(StepState.VERIFYING, StepState.FAILED))
        self.assertTrue(can_transition(StepState.FAILED, StepState.IN_PROGRESS))  # retry

    def test_invalid_transitions(self) -> None:
        self.assertFalse(can_transition(StepState.PENDING, StepState.COMPLETED))
        self.assertFalse(can_transition(StepState.COMPLETED, StepState.IN_PROGRESS))
        self.assertFalse(can_transition(StepState.COMPLETED, StepState.FAILED))

    def test_transition_raises_on_invalid(self) -> None:
        with self.assertRaises(ValueError):
            transition(StepState.PENDING, StepState.COMPLETED)

    def test_transition_returns_new_state_on_valid(self) -> None:
        result = transition(StepState.PENDING, StepState.IN_PROGRESS)
        self.assertEqual(result, StepState.IN_PROGRESS)

    def test_is_terminal(self) -> None:
        self.assertTrue(is_terminal(StepState.COMPLETED))
        self.assertTrue(is_terminal(StepState.FAILED))
        self.assertFalse(is_terminal(StepState.PENDING))
        self.assertFalse(is_terminal(StepState.IN_PROGRESS))
        self.assertFalse(is_terminal(StepState.VERIFYING))

    def test_aggregate_empty(self) -> None:
        self.assertEqual(aggregate_state([]), StepState.PENDING)

    def test_aggregate_all_completed(self) -> None:
        self.assertEqual(
            aggregate_state([StepState.COMPLETED, StepState.COMPLETED]),
            StepState.COMPLETED,
        )

    def test_aggregate_one_failed(self) -> None:
        self.assertEqual(
            aggregate_state([StepState.COMPLETED, StepState.FAILED, StepState.PENDING]),
            StepState.FAILED,
        )

    def test_aggregate_one_pending(self) -> None:
        self.assertEqual(
            aggregate_state([StepState.COMPLETED, StepState.PENDING]),
            StepState.PENDING,
        )

    def test_aggregate_in_progress_priority(self) -> None:
        self.assertEqual(
            aggregate_state([StepState.COMPLETED, StepState.IN_PROGRESS]),
            StepState.IN_PROGRESS,
        )

    def test_aggregate_verifying_priority(self) -> None:
        self.assertEqual(
            aggregate_state([StepState.COMPLETED, StepState.VERIFYING]),
            StepState.VERIFYING,
        )


# ── engine ────────────────────────────────────────────────────────────


class WorkflowEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        _seed_system(self.root)
        self.server = AiEfficiencyMcpServer(system_root=self.root)
        self.engine = WorkflowEngine(self.server)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _def(self, steps: list[dict], **kwargs) -> dict:
        d = {"project": "alpha", "task_slug": "test-wf", "steps": steps}
        d.update(kwargs)
        return d

    # ── basic execution ──

    def test_single_step_linear(self) -> None:
        result = self.engine.run(self._def([
            {"id": "s1", "tool": "search_memory", "args": {"project": "alpha", "query": "alpha"}},
        ]))
        self.assertEqual(result["aggregate_state"], "completed")
        self.assertEqual(len(result["steps"]), 1)
        self.assertEqual(result["steps"][0]["state"], "completed")
        self.assertEqual(result["steps"][0]["attempts"], 1)

    def test_identified_workflow_persists_result_for_status_query(self) -> None:
        result = self.engine.run(self._def([
            {"id": "s1", "tool": "search_memory", "args": {"project": "alpha", "query": "alpha"}},
        ], task_slug="persisted"))

        status_path = self.root / "runtime" / "task-runs" / "alpha" / "persisted" / "status.json"
        workflow_path = status_path.with_name("workflow.json")
        self.assertEqual(json.loads(status_path.read_text(encoding="utf-8"))["state"], "completed")
        self.assertEqual(json.loads(workflow_path.read_text(encoding="utf-8"))["steps"], result["steps"])
        status = self.server.invoke("get_workflow_status", {"project": "alpha", "task_slug": "persisted"})
        self.assertEqual(status["state"], "completed")
        self.assertEqual(status["workflow"]["steps"], result["steps"])

    def test_two_step_sequential(self) -> None:
        result = self.engine.run(self._def([
            {"id": "search", "tool": "search_memory", "args": {"project": "alpha", "query": "alpha"}},
            {"id": "validate", "tool": "validate_project", "args": {"project": "alpha"}, "depends_on": ["search"]},
        ]))
        self.assertEqual(result["aggregate_state"], "completed")
        self.assertEqual(result["steps"][0]["state"], "completed")
        self.assertEqual(result["steps"][1]["state"], "completed")

    def test_two_step_parallel(self) -> None:
        result = self.engine.run(self._def([
            {"id": "search", "tool": "search_memory", "args": {"project": "alpha", "query": "alpha"}},
            {"id": "list", "tool": "list_project_types", "args": {}},
        ]))
        self.assertEqual(result["aggregate_state"], "completed")
        states = {s["id"]: s["state"] for s in result["steps"]}
        self.assertEqual(states["search"], "completed")
        self.assertEqual(states["list"], "completed")

    def test_diamond_dependency(self) -> None:
        result = self.engine.run(self._def([
            {"id": "a", "tool": "search_memory", "args": {"project": "alpha", "query": "alpha"}},
            {"id": "b", "tool": "list_project_types", "args": {}, "depends_on": ["a"]},
            {"id": "c", "tool": "validate_project", "args": {"project": "alpha"}, "depends_on": ["a"]},
            {"id": "d", "tool": "search_memory", "args": {"project": "alpha", "query": "alpha"}, "depends_on": ["b", "c"]},
        ]))
        self.assertEqual(result["aggregate_state"], "completed")
        for s in result["steps"]:
            self.assertEqual(s["state"], "completed", msg=f"step {s['id']}")

    # ── validation ──

    def test_duplicate_id_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.run(self._def([
                {"id": "a", "tool": "search_memory", "args": {}},
                {"id": "a", "tool": "search_memory", "args": {}},
            ]))

    def test_missing_id_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.run(self._def([
                {"tool": "search_memory", "args": {}},
            ]))

    def test_unknown_dependency_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.run(self._def([
                {"id": "a", "tool": "search_memory", "args": {}, "depends_on": ["ghost"]},
            ]))

    def test_circular_dependency_raises(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            self.engine.run(self._def([
                {"id": "a", "tool": "search_memory", "args": {}, "depends_on": ["b"]},
                {"id": "b", "tool": "list_project_types", "args": {}, "depends_on": ["a"]},
            ]))
        self.assertIn("circular", str(ctx.exception).lower())

    def test_empty_steps(self) -> None:
        result = self.engine.run(self._def([]))
        self.assertEqual(result["aggregate_state"], "pending")
        self.assertEqual(result["steps"], [])

    # ── error handling ──

    def test_bad_tool_fails_step(self) -> None:
        result = self.engine.run(self._def([
            {"id": "bad", "tool": "nonexistent", "args": {}},
        ]))
        self.assertEqual(result["steps"][0]["state"], "failed")

    def test_failed_step_blocks_dependents(self) -> None:
        result = self.engine.run(self._def([
            {"id": "fail", "tool": "nonexistent", "args": {}},
            {"id": "after", "tool": "search_memory", "args": {"query": "x"}, "depends_on": ["fail"]},
        ]))
        self.assertEqual(result["steps"][0]["state"], "failed")
        self.assertEqual(result["steps"][1]["state"], "failed")
        self.assertIn("dependency failed", result["steps"][1].get("output", {}).get("error", ""))

    def test_verification_always_fail(self) -> None:
        result = self.engine.run(self._def([
            {"id": "v", "tool": "list_project_types", "args": {}, "verify": {"condition": "always_fail"}},
        ]))
        self.assertEqual(result["steps"][0]["state"], "failed")
        self.assertTrue(result["steps"][0].get("output", {}).get("verification_failed"))

    def test_verification_no_error_passes(self) -> None:
        result = self.engine.run(self._def([
            {"id": "v", "tool": "list_project_types", "args": {}, "verify": {"condition": "no_error"}},
        ]))
        self.assertEqual(result["steps"][0]["state"], "completed")

    # ── retry ──

    def test_retry_on_failure(self) -> None:
        result = self.engine.run(self._def([
            {"id": "r", "tool": "nonexistent", "args": {}, "retry": {"max_attempts": 3}},
        ]))
        self.assertEqual(result["steps"][0]["state"], "failed")
        self.assertEqual(result["steps"][0]["attempts"], 3)

    # ── fan_out built-in ──

    def test_fan_out_parallel(self) -> None:
        result = self.engine.run(self._def([
            {"id": "f", "tool": "fan_out", "args": {"items": [
                {"tool": "search_memory", "args": {"project": "alpha", "query": "alpha"}},
                {"tool": "list_project_types", "args": {}},
                {"tool": "validate_project", "args": {"project": "alpha"}},
            ]}},
        ]))
        self.assertEqual(result["steps"][0]["state"], "completed")
        self.assertEqual(len(result["steps"][0]["output"]), 3)

    def test_fan_out_empty_items(self) -> None:
        result = self.engine.run(self._def([
            {"id": "f", "tool": "fan_out", "args": {"items": []}},
        ]))
        self.assertEqual(result["steps"][0]["state"], "completed")
        self.assertEqual(result["steps"][0]["output"], [])


if __name__ == "__main__":
    unittest.main()
