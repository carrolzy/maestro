import importlib
from concurrent.futures import ThreadPoolExecutor
import json
import shutil
import subprocess
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


class TaskRoutingDecisionTests(unittest.TestCase):
    def _seed_clean_repo(self, root: Path, candidate_file: str) -> Path:
        target = root / candidate_file
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("<style scoped></style>\n", encoding="utf-8")
        subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Routing Test"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.email", "routing@example.com"], cwd=root, check=True)
        subprocess.run(["git", "add", candidate_file], cwd=root, check=True)
        subprocess.run(["git", "commit", "-m", "seed"], cwd=root, check=True, capture_output=True)
        return root

    def _seed_project(self, root: Path, *, configured: bool = True) -> tuple[Path, Path]:
        repository_root = Path(__file__).resolve().parents[2]
        (root / "base").mkdir(parents=True)
        shutil.copyfile(
            repository_root / "base" / "task-routing-policy.json",
            root / "base" / "task-routing-policy.json",
        )
        project_dir = root / "projects" / "alpha"
        project_dir.mkdir(parents=True)
        if configured:
            (project_dir / "playbook.json").write_text(
                json.dumps(
                    {
                        "routing": {
                            "fast_path_signals": ["local_scoped_style"],
                            "risk_rules": [],
                            "risky_paths": [],
                        }
                    }
                ),
                encoding="utf-8",
            )

        repo_root = root / "repo"
        (repo_root / "src").mkdir(parents=True)
        (repo_root / "src" / "card.vue").write_text("<style scoped></style>\n", encoding="utf-8")
        subprocess.run(["git", "init", "-b", "main"], cwd=repo_root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Routing Test"], cwd=repo_root, check=True)
        subprocess.run(["git", "config", "user.email", "routing@example.com"], cwd=repo_root, check=True)
        subprocess.run(["git", "add", "src/card.vue"], cwd=repo_root, check=True)
        subprocess.run(["git", "commit", "-m", "seed"], cwd=repo_root, check=True, capture_output=True)
        return root, repo_root

    def test_local_scoped_style_routes_to_high_confidence_l0(self) -> None:
        task_router = importlib.import_module("task_router")
        route_task = getattr(task_router, "route_task", None)
        self.assertTrue(callable(route_task), "route_task must be callable")

        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root, repo_root = self._seed_project(Path(tmp_dir))
            result = route_task(
                system_root=system_root,
                project="alpha",
                requirement="调整卡片局部间距",
                repo_root=repo_root,
                candidate_files=["src/card.vue"],
                observed_signals=["local_scoped_style"],
                uncertainties=[],
                requested_actions=[],
            )

        self.assertEqual(result["tier"], "L0")
        self.assertEqual(result["confidence"], "high")
        self.assertEqual(result["risk_hits"], [])
        self.assertFalse(result["requires_user_confirmation"])
        self.assertIn("focused_verification", result["required_steps"])
        self.assertIn("branch", result["skipped_steps"])
        self.assertIn("change_spec", result["skipped_steps"])

    def test_global_hard_risks_raise_the_minimum_tier(self) -> None:
        task_router = importlib.import_module("task_router")
        cases = (
            ("transaction", [], "L2", "change_spec"),
            ("local_scoped_style", ["production_operation"], "L3", "risk_confirmation"),
        )

        for signal, requested_actions, expected_tier, expected_step in cases:
            with self.subTest(expected_tier=expected_tier), tempfile.TemporaryDirectory() as tmp_dir:
                system_root, repo_root = self._seed_project(Path(tmp_dir))
                result = task_router.route_task(
                    system_root=system_root,
                    project="alpha",
                    requirement="快速调整目标行为",
                    repo_root=repo_root,
                    candidate_files=["src/card.vue"],
                    observed_signals=[signal],
                    uncertainties=[],
                    requested_actions=requested_actions,
                )

            self.assertEqual(result["tier"], expected_tier)
            self.assertIn(expected_step, result["required_steps"])
            self.assertTrue(result["hard_vetoes"])
            self.assertTrue(result["requires_user_confirmation"])

    def test_unconfigured_or_uncertain_tasks_cannot_enter_l0(self) -> None:
        task_router = importlib.import_module("task_router")
        cases = (
            (False, [], "medium", "unconfigured_project"),
            (True, ["目标组件是否为公共组件尚未确认"], "low", "ambiguous_requirement"),
        )

        for configured, uncertainties, expected_confidence, expected_risk in cases:
            with self.subTest(expected_risk=expected_risk), tempfile.TemporaryDirectory() as tmp_dir:
                system_root, repo_root = self._seed_project(Path(tmp_dir), configured=configured)
                result = task_router.route_task(
                    system_root=system_root,
                    project="alpha",
                    requirement="调整卡片局部间距",
                    repo_root=repo_root,
                    candidate_files=["src/card.vue"],
                    observed_signals=["local_scoped_style"],
                    uncertainties=uncertainties,
                    requested_actions=[],
                )

            self.assertEqual(result["tier"], "L1")
            self.assertEqual(result["confidence"], expected_confidence)
            self.assertIn(expected_risk, result["risk_hits"])
            self.assertTrue(result["requires_user_confirmation"])

    def test_global_files_and_expanded_scope_block_the_fast_path(self) -> None:
        task_router = importlib.import_module("task_router")
        cases = (
            (["common/theme.css"], "global_or_common_file"),
            (["src/card.vue", "src/card.scss", "src/card.test.js"], "scope_exceeds_fast_path"),
        )

        for candidate_files, expected_risk in cases:
            with self.subTest(expected_risk=expected_risk), tempfile.TemporaryDirectory() as tmp_dir:
                system_root, repo_root = self._seed_project(Path(tmp_dir))
                result = task_router.route_task(
                    system_root=system_root,
                    project="alpha",
                    requirement="调整局部样式",
                    repo_root=repo_root,
                    candidate_files=candidate_files,
                    observed_signals=["local_scoped_style"],
                    uncertainties=[],
                    requested_actions=[],
                )

            self.assertEqual(result["tier"], "L1")
            self.assertIn(expected_risk, result["risk_hits"])
            self.assertIn(expected_risk, result["hard_vetoes"])

    def test_dirty_candidate_file_blocks_l0(self) -> None:
        task_router = importlib.import_module("task_router")
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root, repo_root = self._seed_project(Path(tmp_dir))
            (repo_root / "src" / "card.vue").write_text("<style scoped>.card { gap: 8px; }</style>\n", encoding="utf-8")

            result = task_router.route_task(
                system_root=system_root,
                project="alpha",
                requirement="调整卡片局部间距",
                repo_root=repo_root,
                candidate_files=["src/card.vue"],
                observed_signals=["local_scoped_style"],
                uncertainties=[],
                requested_actions=[],
            )

        self.assertEqual(result["tier"], "L1")
        self.assertIn("target_file_overlap", result["risk_hits"])
        self.assertTrue(result["requires_user_confirmation"])

    def test_rerouting_never_downgrades_the_current_tier(self) -> None:
        task_router = importlib.import_module("task_router")
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root, repo_root = self._seed_project(Path(tmp_dir))
            result = task_router.route_task(
                system_root=system_root,
                project="alpha",
                requirement="范围收敛为局部样式",
                repo_root=repo_root,
                candidate_files=["src/card.vue"],
                observed_signals=["local_scoped_style"],
                uncertainties=[],
                requested_actions=[],
                current_tier="L2",
            )

        self.assertEqual(result["tier"], "L2")
        self.assertIn("change_spec", result["required_steps"])
        self.assertNotIn("change_spec", result["skipped_steps"])

    def test_real_project_routing_keeps_local_style_fast_and_domain_risks_governed(self) -> None:
        task_router = importlib.import_module("task_router")
        system_root = Path(__file__).resolve().parents[2]
        cases = (
            ("gcc-wxapp", "pages2/goods-detail/index.vue", "local_scoped_style", "L0"),
            ("gcc-wxapp", "pages3/confirm-order/index.vue", "shopping_cart", "L2"),
            ("wwj-wxapp", "src/pages2/goods-detail/index.vue", "local_scoped_style", "L0"),
            ("wwj-wxapp", "src/api/request.ts", "request_signature", "L2"),
        )

        for project, candidate_file, signal, expected_tier in cases:
            with self.subTest(project=project, signal=signal), tempfile.TemporaryDirectory() as tmp_dir:
                repo_root = self._seed_clean_repo(Path(tmp_dir), candidate_file)
                result = task_router.route_task(
                    system_root=system_root,
                    project=project,
                    requirement="验证真实项目路由边界",
                    repo_root=repo_root,
                    candidate_files=[candidate_file],
                    observed_signals=[signal],
                    uncertainties=[],
                    requested_actions=[],
                )

            self.assertEqual(result["tier"], expected_tier)
            if expected_tier == "L2":
                self.assertIn(signal, result["risk_hits"])
                self.assertIn("change_spec", result["required_steps"])

    def test_routing_log_records_only_minimal_decision_metadata(self) -> None:
        task_router = importlib.import_module("task_router")
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root, repo_root = self._seed_project(Path(tmp_dir))
            requirement = "调整卡片局部间距，不得把完整内容写入观测日志"
            result = task_router.route_task(
                system_root=system_root,
                project="alpha",
                requirement=requirement,
                repo_root=repo_root,
                candidate_files=["src/card.vue"],
                observed_signals=["local_scoped_style"],
                uncertainties=[],
                requested_actions=[],
            )
            log_path = system_root / "runtime" / "routing-decisions.jsonl"
            self.assertTrue(log_path.is_file())
            raw_line = log_path.read_text(encoding="utf-8").strip()
            record = json.loads(raw_line)

        self.assertEqual(result["warnings"], [])
        self.assertEqual(record["project"], "alpha")
        self.assertEqual(record["tier"], "L0")
        self.assertGreaterEqual(record["elapsed_ms"], 0)
        self.assertEqual(record["risk_tags"], [])
        self.assertFalse(record["upgraded"])
        self.assertFalse(record["user_override"])
        self.assertNotIn(requirement, raw_line)
        self.assertNotIn("src/card.vue", raw_line)
        self.assertNotIn("requirement", record)
        self.assertNotIn("candidate_files", record)

    def test_logging_failure_warns_without_changing_the_tier(self) -> None:
        task_router = importlib.import_module("task_router")
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root, repo_root = self._seed_project(Path(tmp_dir))
            (system_root / "runtime").write_text("not a directory", encoding="utf-8")
            result = task_router.route_task(
                system_root=system_root,
                project="alpha",
                requirement="调整卡片局部间距",
                repo_root=repo_root,
                candidate_files=["src/card.vue"],
                observed_signals=["local_scoped_style"],
                uncertainties=[],
                requested_actions=[],
            )

        self.assertEqual(result["tier"], "L0")
        self.assertTrue(any("log failed" in warning for warning in result["warnings"]))

    def test_concurrent_routing_logs_keep_one_json_record_per_line(self) -> None:
        task_router = importlib.import_module("task_router")
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root, repo_root = self._seed_project(Path(tmp_dir))

            def route_once(index: int) -> dict:
                return task_router.route_task(
                    system_root=system_root,
                    project="alpha",
                    requirement=f"局部样式调整 {index}",
                    repo_root=repo_root,
                    candidate_files=["src/card.vue"],
                    observed_signals=["local_scoped_style"],
                    uncertainties=[],
                    requested_actions=[],
                )

            with ThreadPoolExecutor(max_workers=8) as executor:
                results = list(executor.map(route_once, range(24)))

            lines = (system_root / "runtime" / "routing-decisions.jsonl").read_text(encoding="utf-8").splitlines()
            records = [json.loads(line) for line in lines]

        self.assertEqual(len(records), 24)
        self.assertTrue(all(result["warnings"] == [] for result in results))
        self.assertTrue(all(record["tier"] == "L0" for record in records))


if __name__ == "__main__":
    unittest.main()
