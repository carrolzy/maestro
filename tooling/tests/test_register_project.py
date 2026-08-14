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
    (templates_root / "agents.md").write_text(
        "<!-- maestro:managed:start -->\nproject={{PROJECT_SLUG}}\nroot={{MAESTRO_ROOT}}\n<!-- maestro:managed:end -->\n",
        encoding="utf-8",
    )
    (templates_root / "project-baseline.md").write_text(
        "# Project Baseline Spec: {{PROJECT_SLUG}}\n\n## Status\n\n- Needs Curation\n\n## Evidence Sources\n\n- `business-context.md`\n- `project-override.md`\n- `task-context.md`\n",
        encoding="utf-8",
    )


class RegisterProjectTests(unittest.TestCase):
    def test_repository_agents_template_uses_chinese_task_routing_entry(self) -> None:
        root = Path(__file__).resolve().parents[2]
        content = (root / "templates" / "agents.md").read_text(encoding="utf-8")

        self.assertIn("# Maestro 项目工作流", content)
        self.assertNotIn("# Maestro Project Workflow", content)
        self.assertLess(content.index("task-routing"), content.index("project-intake"))
        for tier in ("L0", "L1", "L2", "L3"):
            self.assertIn(tier, content)
        self.assertIn("只升不降", content)
        self.assertIn("高优先级项目规则", content)

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

    def test_register_project_seeds_project_baseline_spec(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir)
            _write_templates(system_root)

            project_dir = register_project(
                system_root=system_root,
                project="sample-project",
                summary="Sample project summary.",
            )

            baseline = project_dir / "spec" / "project-baseline.md"
            self.assertTrue(baseline.exists())
            content = baseline.read_text(encoding="utf-8")
            self.assertIn("# Project Baseline Spec: sample-project", content)
            self.assertIn("Needs Curation", content)

    def test_force_registration_preserves_existing_project_baseline_spec(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir)
            _write_templates(system_root)
            project_dir = register_project(
                system_root=system_root,
                project="sample-project",
                summary="Sample project summary.",
            )
            baseline = project_dir / "spec" / "project-baseline.md"
            baseline.parent.mkdir(parents=True, exist_ok=True)
            baseline.write_text("# Curated baseline\n\nDo not replace.\n", encoding="utf-8")

            register_project(
                system_root=system_root,
                project="sample-project",
                summary="Replacement summary.",
                force=True,
            )

            self.assertEqual(baseline.read_text(encoding="utf-8"), "# Curated baseline\n\nDo not replace.\n")

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

    def test_register_project_writes_managed_agents_workflow_to_business_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir) / "system"
            repo_root = Path(tmp_dir) / "business-repo"
            repo_root.mkdir()
            _write_templates(system_root)

            register_project(
                system_root=system_root,
                project="sample-project",
                summary="Sample project summary.",
                repo_root=repo_root,
            )

            agents_file = repo_root / "AGENTS.md"
            self.assertTrue(agents_file.exists())
            content = agents_file.read_text(encoding="utf-8")
            self.assertIn("project=sample-project", content)
            self.assertIn(f"root={system_root.resolve()}", content)

    def test_existing_project_can_attach_or_update_managed_agents_block_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir) / "system"
            repo_root = Path(tmp_dir) / "business-repo"
            repo_root.mkdir()
            (repo_root / "AGENTS.md").write_text("# User rules\n\nKeep this content.\n", encoding="utf-8")
            _write_templates(system_root)

            register_project(
                system_root=system_root,
                project="sample-project",
                summary="Sample project summary.",
            )
            register_project(
                system_root=system_root,
                project="sample-project",
                summary="Ignored during attach.",
                repo_root=repo_root,
            )

            content = (repo_root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("# User rules", content)
            self.assertIn("Keep this content.", content)
            self.assertEqual(content.count("<!-- maestro:managed:start -->"), 1)

    def test_existing_managed_block_is_replaced_without_duplicating_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir) / "system"
            repo_root = Path(tmp_dir) / "business-repo"
            repo_root.mkdir()
            _write_templates(system_root)
            register_project(
                system_root=system_root,
                project="sample-project",
                summary="Sample project summary.",
            )
            (repo_root / "AGENTS.md").write_text(
                "# User rules\n\n<!-- maestro:managed:start -->\nold\n<!-- maestro:managed:end -->\n\nKeep this content.\n",
                encoding="utf-8",
            )

            register_project(
                system_root=system_root,
                project="sample-project",
                summary="Ignored during attach.",
                repo_root=repo_root,
            )

            content = (repo_root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertNotIn("\nold\n", content)
            self.assertIn("project=sample-project", content)
            self.assertIn("Keep this content.", content)
            self.assertEqual(content.count("<!-- maestro:managed:start -->"), 1)

    def test_repository_template_rebind_preserves_high_priority_user_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir) / "system"
            repo_root = Path(tmp_dir) / "business-repo"
            repo_root.mkdir()
            _write_templates(system_root)
            repository_template = Path(__file__).resolve().parents[2] / "templates" / "agents.md"
            (system_root / "templates" / "agents.md").write_text(
                repository_template.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            register_project(
                system_root=system_root,
                project="sample-project",
                summary="Sample project summary.",
            )
            user_rules = "# 高优先级项目规则\n\n## 规则一\n\n保留我。\n"
            (repo_root / "AGENTS.md").write_text(
                "<!-- maestro:managed:start -->\nold\n<!-- maestro:managed:end -->\n\n" + user_rules,
                encoding="utf-8",
            )

            register_project(
                system_root=system_root,
                project="sample-project",
                summary="Ignored during attach.",
                repo_root=repo_root,
            )

            content = (repo_root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("task-routing", content)
            self.assertIn(user_rules.strip(), content)
            self.assertEqual(content.count("<!-- maestro:managed:start -->"), 1)
            self.assertEqual(content.count("# 高优先级项目规则"), 1)

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
