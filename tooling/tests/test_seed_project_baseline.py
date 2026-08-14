import tempfile
import unittest
from pathlib import Path

from seed_project_baseline import main, seed_project_baseline


def _write_registered_project(system_root: Path, project: str) -> Path:
    project_dir = system_root / "projects" / project
    project_dir.mkdir(parents=True)
    (project_dir / "business-context.md").write_text("# Business Context\n\nKeep this content.\n", encoding="utf-8")
    (project_dir / "project-override.md").write_text("# Project Override\n", encoding="utf-8")
    (project_dir / "task-context.md").write_text("# Task Context\n", encoding="utf-8")
    return project_dir


def _write_baseline_template(system_root: Path) -> None:
    templates_root = system_root / "templates"
    templates_root.mkdir(parents=True)
    (templates_root / "project-baseline.md").write_text(
        "# Project Baseline Spec: {{PROJECT_SLUG}}\n\n## Status\n\n- Needs Curation\n",
        encoding="utf-8",
    )


class SeedProjectBaselineTests(unittest.TestCase):
    def test_seeds_missing_baseline_without_rewriting_project_cards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir)
            project_dir = _write_registered_project(system_root, "sample-project")
            _write_baseline_template(system_root)

            baseline = seed_project_baseline(system_root=system_root, project="sample-project")

            self.assertEqual(baseline, project_dir / "spec" / "project-baseline.md")
            self.assertIn("sample-project", baseline.read_text(encoding="utf-8"))
            self.assertEqual((project_dir / "business-context.md").read_text(encoding="utf-8"), "# Business Context\n\nKeep this content.\n")

    def test_preserves_existing_curated_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir)
            project_dir = _write_registered_project(system_root, "sample-project")
            _write_baseline_template(system_root)
            baseline = project_dir / "spec" / "project-baseline.md"
            baseline.parent.mkdir()
            baseline.write_text("# Curated baseline\n", encoding="utf-8")

            seed_project_baseline(system_root=system_root, project="sample-project")

            self.assertEqual(baseline.read_text(encoding="utf-8"), "# Curated baseline\n")

    def test_rejects_unknown_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir)
            _write_baseline_template(system_root)

            with self.assertRaisesRegex(ValueError, "Unknown project"):
                seed_project_baseline(system_root=system_root, project="missing-project")

    def test_cli_writes_seeded_baseline_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir)
            project_dir = _write_registered_project(system_root, "sample-project")
            _write_baseline_template(system_root)
            output_path = system_root / "stdout.txt"

            exit_code = main(
                argv=["--project", "sample-project"],
                system_root=system_root,
                stdout_path=output_path,
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(output_path.read_text(encoding="utf-8"), f"{project_dir / 'spec' / 'project-baseline.md'}\n")
