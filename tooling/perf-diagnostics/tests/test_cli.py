import json
import tempfile
import unittest
from pathlib import Path

from perf_diagnostics.cli import main
from writeback_and_sync_memory import REQUIRED_NOTE_SECTIONS


FIXTURES = Path(__file__).parent / "fixtures"


class CliTests(unittest.TestCase):
    def test_cli_end_to_end_creates_analysis_and_writeback_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir)
            trace_path = FIXTURES / "miniapp_hotspot_trace.json"

            init_output = system_root / "init.txt"
            exit_code = main(
                [
                    "init",
                    "--project",
                    "example-wxapp",
                    "--trace",
                    str(trace_path),
                    "--label",
                    "home-cms-return-lag",
                    "--date",
                    "2026-05-26",
                ],
                system_root=system_root,
                stdout_path=init_output,
            )

            self.assertEqual(exit_code, 0)
            case_dir = Path(init_output.read_text(encoding="utf-8").strip())

            analyze_output = system_root / "analyze.txt"
            exit_code = main(
                ["analyze", "--case-dir", str(case_dir)],
                system_root=system_root,
                stdout_path=analyze_output,
            )

            self.assertEqual(exit_code, 0)
            summary = json.loads((case_dir / "03_analysis" / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["stall_windows"]["long_task_count"], 3)
            self.assertTrue((case_dir / "03_analysis" / "report.md").exists())

            writeback_output = system_root / "writeback.txt"
            exit_code = main(
                ["writeback", "--case-dir", str(case_dir)],
                system_root=system_root,
                stdout_path=writeback_output,
            )

            self.assertEqual(exit_code, 0)
            writeback = (case_dir / "04_writeback" / "writeback.md").read_text(encoding="utf-8")
            self.assertIn("## Request", writeback)
            self.assertIn("## Implementation", writeback)
            for section in REQUIRED_NOTE_SECTIONS:
                self.assertIn(f"## {section}", writeback)

    def test_cli_report_contains_main_findings_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir)
            trace_path = FIXTURES / "miniapp_hotspot_trace.json"

            init_output = system_root / "init.txt"
            main(
                [
                    "init",
                    "--project",
                    "example-wxapp",
                    "--trace",
                    str(trace_path),
                    "--label",
                    "cms-return-performance",
                    "--date",
                    "2026-05-26",
                ],
                system_root=system_root,
                stdout_path=init_output,
            )
            case_dir = Path(init_output.read_text(encoding="utf-8").strip())

            main(["analyze", "--case-dir", str(case_dir)], system_root=system_root)

            report = (case_dir / "03_analysis" / "report.md").read_text(encoding="utf-8")
            self.assertIn("## Trace Overview", report)
            self.assertIn("## Main Findings", report)
            self.assertIn("## Recommended Actions", report)

    def test_cli_sync_writes_note_and_memory_case(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir)
            trace_path = FIXTURES / "miniapp_hotspot_trace.json"
            (system_root / "projects" / "example-wxapp").mkdir(parents=True, exist_ok=True)

            init_output = system_root / "init.txt"
            main(
                [
                    "init",
                    "--project",
                    "example-wxapp",
                    "--trace",
                    str(trace_path),
                    "--label",
                    "sync-case",
                    "--date",
                    "2026-05-26",
                ],
                system_root=system_root,
                stdout_path=init_output,
            )
            case_dir = Path(init_output.read_text(encoding="utf-8").strip())
            main(["analyze", "--case-dir", str(case_dir)], system_root=system_root)
            main(["writeback", "--case-dir", str(case_dir)], system_root=system_root)

            vault_root = system_root / "vault"
            sync_output = system_root / "sync.txt"
            exit_code = main(
                [
                    "sync",
                    "--case-dir",
                    str(case_dir),
                    "--vault-root",
                    str(vault_root),
                ],
                system_root=system_root,
                stdout_path=sync_output,
            )

            self.assertEqual(exit_code, 0)
            note_output = vault_root / "project-notes" / "codex-auto" / "example-wxapp" / "2026-05-26-sync-case.md"
            memory_case = system_root / "memory" / "projects" / "example-wxapp" / "cases" / "2026-05-26-2026-05-26-sync-case.md"
            index_path = system_root / "memory" / "projects" / "example-wxapp" / "index.md"

            self.assertTrue(note_output.exists())
            self.assertTrue(memory_case.exists())
            self.assertTrue(index_path.exists())
