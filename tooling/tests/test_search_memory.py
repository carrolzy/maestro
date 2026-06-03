import tempfile
import unittest
from pathlib import Path

from search_memory import main, search_memory


def _write_project(system_root: Path, project: str, summary: str = "Project summary.") -> None:
    project_dir = system_root / "projects" / project
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "business-context.md").write_text(
        f"# Business Context\n\n## Project in One Sentence\n\n{summary}\n",
        encoding="utf-8",
    )
    (project_dir / "project-override.md").write_text(
        "# Project Override\n\n## Project Terms\n\n- sample-term\n",
        encoding="utf-8",
    )


class SearchMemoryTests(unittest.TestCase):
    def test_search_memory_lists_project_cards_and_recent_cases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir)
            _write_project(system_root, "alpha", summary="Alpha project.")
            case_dir = system_root / "memory" / "projects" / "alpha" / "cases"
            case_dir.mkdir(parents=True, exist_ok=True)
            (case_dir / "2026-05-20-alpha-case.md").write_text(
                "# Alpha Case\n\nalpha incident\n",
                encoding="utf-8",
            )

            result = search_memory(system_root=system_root, project="alpha")

            self.assertEqual([item["slug"] for item in result["project_cards"]], ["alpha"])
            self.assertEqual([item["slug"] for item in result["recent_cases"]], ["2026-05-20-alpha-case"])
            self.assertEqual(result["project_override"]["slug"], "alpha")

    def test_search_memory_matches_patterns_and_rules_by_query(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir)
            _write_project(system_root, "alpha", summary="Alpha project.")
            pattern_dir = system_root / "memory" / "patterns"
            rule_dir = system_root / "memory" / "rules"
            pattern_dir.mkdir(parents=True, exist_ok=True)
            rule_dir.mkdir(parents=True, exist_ok=True)
            (pattern_dir / "button-lock.md").write_text(
                "# Button Lock Pattern\n\nsubmit button lock\n",
                encoding="utf-8",
            )
            (rule_dir / "sync-first.md").write_text(
                "# Sync First Rule\n\nnon-trivial work must sync\n",
                encoding="utf-8",
            )

            result = search_memory(system_root=system_root, query="sync button lock")

            self.assertEqual([item["slug"] for item in result["matched_patterns"]], ["button-lock"])
            self.assertEqual([item["slug"] for item in result["matched_rules"]], ["sync-first"])

    def test_search_memory_rejects_unknown_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir)
            with self.assertRaisesRegex(ValueError, "Unknown project"):
                search_memory(system_root=system_root, project="missing-project")

    def test_search_memory_without_project_lists_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir)
            _write_project(system_root, "alpha", summary="Alpha project.")
            _write_project(system_root, "beta", summary="Beta project.")
            alpha_case_dir = system_root / "memory" / "projects" / "alpha" / "cases"
            beta_case_dir = system_root / "memory" / "projects" / "beta" / "cases"
            alpha_case_dir.mkdir(parents=True, exist_ok=True)
            beta_case_dir.mkdir(parents=True, exist_ok=True)
            (alpha_case_dir / "2026-05-20-alpha-case.md").write_text("# Alpha Case\n", encoding="utf-8")
            (beta_case_dir / "2026-05-20-beta-case.md").write_text("# Beta Case\n", encoding="utf-8")

            result = search_memory(system_root=system_root)

            self.assertEqual([item["slug"] for item in result["project_cards"]], ["alpha", "beta"])
            self.assertEqual(len(result["recent_cases"]), 2)

    def test_cli_writes_structured_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir)
            _write_project(system_root, "alpha", summary="Alpha project.")
            case_dir = system_root / "memory" / "projects" / "alpha" / "cases"
            pattern_dir = system_root / "memory" / "patterns"
            rule_dir = system_root / "memory" / "rules"
            case_dir.mkdir(parents=True, exist_ok=True)
            pattern_dir.mkdir(parents=True, exist_ok=True)
            rule_dir.mkdir(parents=True, exist_ok=True)
            (case_dir / "2026-05-20-alpha-case.md").write_text(
                "# Alpha Case\n\nbutton lock regression\n",
                encoding="utf-8",
            )
            (pattern_dir / "button-lock.md").write_text(
                "# Button Lock Pattern\n\nsubmit button lock\n",
                encoding="utf-8",
            )
            (rule_dir / "sync-first.md").write_text(
                "# Sync First Rule\n\nnon-trivial work must sync\n",
                encoding="utf-8",
            )
            output_path = system_root / "stdout.txt"

            exit_code = main(
                argv=["--project", "alpha", "--query", "button sync"],
                system_root=system_root,
                stdout_path=output_path,
            )

            self.assertEqual(exit_code, 0)
            output = output_path.read_text(encoding="utf-8")
            self.assertIn("Project Cards", output)
            self.assertIn("Recent Cases", output)
            self.assertIn("Matched Patterns", output)
            self.assertIn("Matched Rules", output)
