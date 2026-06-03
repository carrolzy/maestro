import tempfile
import unittest
from pathlib import Path

from register_project import main, register_project


def _write_templates(system_root: Path) -> None:
    templates_root = system_root / "templates"
    templates_root.mkdir(parents=True, exist_ok=True)
    (templates_root / "business-context.md").write_text(
        "# Business Context\n\n## Project in One Sentence\n\n## Business Goals\n\n## User Roles\n\n## Core Business Objects\n\n## Key Business Flows\n\n## Page or Module Mapping\n\n## Critical Rules and Boundaries\n\n## Interface Semantics\n\n## Historical Pitfalls\n",
        encoding="utf-8",
    )
    (templates_root / "project-override.md").write_text(
        "# Project Override\n\n## Project Terms\n\n## Module Responsibilities\n\n## Interface or Domain Notes\n\n## Special Components or Utilities\n\n## Release Flow\n\n## Known Incidents and Forbidden Zones\n",
        encoding="utf-8",
    )
    (templates_root / "task-context.md").write_text(
        "# Task Context\n\n## Current Task\n\n## Why This Task Exists\n\n## Business Delta for This Task\n\n## Constraints for This Task\n\n## Verification Focus\n",
        encoding="utf-8",
    )


class RegisterProjectTests(unittest.TestCase):
    def test_register_project_creates_canonical_project_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir)
            _write_templates(system_root)

            project_dir = register_project(
                system_root=system_root,
                project="sample-project",
                summary="Sample project summary.",
            )

            self.assertEqual(project_dir, system_root / "projects" / "sample-project")
            self.assertTrue((project_dir / "business-context.md").exists())
            self.assertTrue((project_dir / "project-override.md").exists())
            self.assertTrue((project_dir / "task-context.md").exists())

    def test_register_project_rejects_malformed_slug(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir)
            _write_templates(system_root)

            with self.assertRaisesRegex(ValueError, "Invalid project slug"):
                register_project(
                    system_root=system_root,
                    project="Bad Project!",
                    summary="Bad slug.",
                )

    def test_register_project_rejects_existing_project_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir)
            _write_templates(system_root)
            project_dir = system_root / "projects" / "sample-project"
            project_dir.mkdir(parents=True)
            (project_dir / "business-context.md").write_text("old", encoding="utf-8")

            with self.assertRaisesRegex(FileExistsError, "already exists"):
                register_project(
                    system_root=system_root,
                    project="sample-project",
                    summary="Sample project summary.",
                )

    def test_register_project_force_overwrites_only_canonical_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir)
            _write_templates(system_root)
            project_dir = system_root / "projects" / "sample-project"
            project_dir.mkdir(parents=True)
            (project_dir / "business-context.md").write_text("old business", encoding="utf-8")
            (project_dir / "project-override.md").write_text("old override", encoding="utf-8")
            (project_dir / "task-context.md").write_text("old task", encoding="utf-8")
            (project_dir / "notes.txt").write_text("keep me", encoding="utf-8")

            register_project(
                system_root=system_root,
                project="sample-project",
                summary="New summary.",
                force=True,
            )

            self.assertIn("New summary.", (project_dir / "business-context.md").read_text(encoding="utf-8"))
            self.assertEqual((project_dir / "notes.txt").read_text(encoding="utf-8"), "keep me")

    def test_register_project_seeds_summary_and_project_type_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir)
            _write_templates(system_root)

            project_dir = register_project(
                system_root=system_root,
                project="sample-project",
                summary="Chrome plugin for internal capture work.",
                project_type="chrome-extension",
            )

            business_context = (project_dir / "business-context.md").read_text(encoding="utf-8")
            task_context = (project_dir / "task-context.md").read_text(encoding="utf-8")
            self.assertIn("Chrome plugin for internal capture work.", business_context)
            self.assertIn("chrome-extension", task_context)

    def test_cli_register_project_writes_project_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir)
            _write_templates(system_root)
            output_path = system_root / "stdout.txt"

            exit_code = main(
                argv=["--project", "sample-project", "--summary", "CLI project."],
                system_root=system_root,
                stdout_path=output_path,
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(output_path.read_text(encoding="utf-8"), f"{system_root / 'projects' / 'sample-project'}\n")

