import importlib
import json
import tempfile
import unittest
from pathlib import Path


class TaskRoutingPolicyTests(unittest.TestCase):
    def _repository_policy_path(self) -> Path:
        return Path(__file__).resolve().parents[2] / "base" / "task-routing-policy.json"

    def test_repository_policy_loads_with_stable_tier_order(self) -> None:
        try:
            task_router = importlib.import_module("task_router")
        except ModuleNotFoundError:
            task_router = None

        self.assertIsNotNone(task_router, "task_router module must exist")
        loader = getattr(task_router, "load_routing_policy", None)
        self.assertTrue(callable(loader), "load_routing_policy must be callable")

        policy = loader(self._repository_policy_path())

        self.assertEqual(policy["tier_order"], ["L0", "L1", "L2", "L3"])
        self.assertEqual(policy["defaults"]["unconfigured_project_min_tier"], "L1")
        self.assertEqual(policy["confidence_rules"]["automatic_fast_path"], "high")
        self.assertTrue(policy["routing_constraints"]["monotonic_upgrade_only"])
        self.assertEqual(set(policy["tiers"]), {"L0", "L1", "L2", "L3"})
        self.assertIn("change_spec", policy["tiers"]["L2"]["required_steps"])
        self.assertIn("production_operation", policy["global_risks"])
        self.assertEqual(policy["global_risks"]["production_operation"]["min_tier"], "L3")
        self.assertEqual(
            [task_router.tier_rank(tier) for tier in policy["tier_order"]],
            [0, 1, 2, 3],
        )

    def test_policy_rejects_a_missing_required_field(self) -> None:
        task_router = importlib.import_module("task_router")
        payload = json.loads(self._repository_policy_path().read_text(encoding="utf-8"))
        payload.pop("global_risks")

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "policy.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "global_risks"):
                task_router.load_routing_policy(path)

    def test_policy_rejects_unsupported_enum_values(self) -> None:
        task_router = importlib.import_module("task_router")
        original = json.loads(self._repository_policy_path().read_text(encoding="utf-8"))
        cases = (
            ("tier_order", lambda payload: payload["tier_order"].__setitem__(3, "L4")),
            ("unconfigured_project_min_tier", lambda payload: payload["defaults"].__setitem__("unconfigured_project_min_tier", "L9")),
            ("automatic_fast_path", lambda payload: payload["confidence_rules"].__setitem__("automatic_fast_path", "certain")),
            ("production_operation", lambda payload: payload["global_risks"]["production_operation"].__setitem__("min_tier", "L9")),
        )

        for expected_error, mutate in cases:
            with self.subTest(expected_error=expected_error), tempfile.TemporaryDirectory() as tmp_dir:
                payload = json.loads(json.dumps(original))
                mutate(payload)
                path = Path(tmp_dir) / "policy.json"
                path.write_text(json.dumps(payload), encoding="utf-8")

                with self.assertRaisesRegex(ValueError, expected_error):
                    task_router.load_routing_policy(path)


if __name__ == "__main__":
    unittest.main()
