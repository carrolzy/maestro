import json
import tempfile
import unittest
from pathlib import Path

from spec_coding import (
    approve_change_spec,
    create_change_spec,
    get_project_baseline,
    seed_project_baseline,
    spec_gate,
)


class SpecCodingTests(unittest.TestCase):
    def _seed_system(self, root: Path) -> Path:
        project_dir = root / "projects" / "alpha"
        (project_dir / "spec").mkdir(parents=True)
        (project_dir / "spec" / "project-baseline.md").write_text(
            "# Project Baseline Spec: alpha\n\n## Status\n\n- Curated for test coverage.\n",
            encoding="utf-8",
        )
        package_dir = root / "runtime" / "task-packages" / "alpha" / "2026-08-04-quantity"
        package_dir.mkdir(parents=True)
        (package_dir / "package.json").write_text(
            json.dumps({"project": "alpha", "sources": ["projects/alpha/spec/project-baseline.md"]}),
            encoding="utf-8",
        )
        return package_dir

    def _create_valid_draft(self, root: Path, package_dir: Path) -> dict:
        return create_change_spec(
            system_root=root,
            project="alpha",
            package_dir=package_dir,
            title="Refund quantity interaction",
            requirement="Only update the refund selector quantity interaction.",
            governance_tier="L2",
            profile="frontend",
            allowed_files=[{"path": "src/pages3/refund/refund-goods-selector.vue", "reason": "Owns local refund quantity UI state."}],
            allowed_behaviors=["Keep quantity between one and the order item maximum."],
            non_goals=["Do not modify cart state or refund API contracts."],
            acceptance_criteria=["Input, increment, and decrement keep the quantity within the supported range."],
            tasks=[{"id": "T1", "outcome": "Update selector interaction", "allowed_files": ["src/pages3/refund/refund-goods-selector.vue"], "acceptance_criteria": ["AC1"]}],
            verification={"automated": ["npm run type-check"], "manual": ["Verify input and plus/minus boundaries."], "regression": ["Verify refund handoff payload."]},
            technical_approach="Keep state local to the refund selector and reuse its current quantity normalization path.",
        )

    def test_get_and_seed_project_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            project_dir = root / "projects" / "alpha"
            project_dir.mkdir(parents=True)
            templates = root / "templates"
            templates.mkdir()
            (templates / "project-baseline.md").write_text("# Project Baseline Spec: {{PROJECT_SLUG}}\n", encoding="utf-8")

            seeded = seed_project_baseline(system_root=root, project="alpha")
            baseline = get_project_baseline(system_root=root, project="alpha")

            self.assertEqual(seeded, project_dir / "spec" / "project-baseline.md")
            self.assertTrue(baseline["exists"])
            self.assertEqual(Path(baseline["path"]).resolve(), seeded.resolve())
            self.assertIn("alpha", baseline["content"])

    def test_draft_is_rendered_and_gate_requires_explicit_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            package_dir = self._seed_system(root)

            result = self._create_valid_draft(root, package_dir)
            gate = spec_gate(system_root=root, spec_path=Path(result["spec_path"]))

            self.assertTrue(Path(result["spec_path"]).exists())
            self.assertTrue(Path(result["markdown_path"]).exists())
            self.assertEqual(result["spec"]["status"], "draft")
            self.assertFalse(gate["passed"])
            self.assertIn("missing explicit approval", gate["blockers"])
            self.assertIn("Non-goals", Path(result["markdown_path"]).read_text(encoding="utf-8"))

    def test_approval_records_actor_time_and_source_then_gate_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            result = self._create_valid_draft(root, self._seed_system(root))

            approved = approve_change_spec(
                system_root=root,
                spec_path=Path(result["spec_path"]),
                approver="apple",
                source_reference="2026-08-04 user confirmation in requirement review",
            )
            gate = spec_gate(system_root=root, spec_path=Path(result["spec_path"]))

            self.assertEqual(approved["spec"]["status"], "approved_for_implementation")
            self.assertEqual(approved["spec"]["approval"]["approver"], "apple")
            self.assertTrue(approved["spec"]["approval"]["approved_at"])
            self.assertTrue(gate["passed"])
            self.assertEqual(gate["blockers"], [])
            package = json.loads((root / "runtime" / "task-packages" / "alpha" / "2026-08-04-quantity" / "package.json").read_text(encoding="utf-8"))
            self.assertTrue(package["change_spec"]["exists"])
            self.assertEqual(package["change_spec"]["status"], "approved_for_implementation")

    def test_open_questions_block_approval_and_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            result = self._create_valid_draft(root, self._seed_system(root))
            spec_path = Path(result["spec_path"])
            payload = json.loads(spec_path.read_text(encoding="utf-8"))
            payload["open_questions"] = ["The maximum quantity source has not been confirmed."]
            spec_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            gate = spec_gate(system_root=root, spec_path=spec_path)
            with self.assertRaisesRegex(ValueError, "open questions"):
                approve_change_spec(
                    system_root=root,
                    spec_path=spec_path,
                    approver="apple",
                    source_reference="review",
                )

            self.assertFalse(gate["passed"])
            self.assertIn("unresolved open questions", gate["blockers"])

    def test_change_spec_rejects_a_package_from_another_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            package_dir = self._seed_system(root)
            (package_dir / "package.json").write_text(json.dumps({"project": "beta"}), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "belongs to project beta"):
                self._create_valid_draft(root, package_dir)


if __name__ == "__main__":
    unittest.main()
