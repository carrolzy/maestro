import json
import tempfile
import unittest
from pathlib import Path

from build_task_package import build_task_package


class BuildTaskPackageTests(unittest.TestCase):
    def test_build_task_package_creates_json_and_markdown_outputs(self) -> None:
        system_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_root = Path(tmp_dir)
            result = build_task_package(
                system_root=system_root,
                project="example-wxapp",
                requirement="购物车加购后确认订单金额需要保持一致",
                output_root=output_root,
            )

            self.assertTrue((result.output_dir / "package.json").exists())
            self.assertTrue((result.output_dir / "package.md").exists())
            payload = json.loads((result.output_dir / "package.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["project"], "example-wxapp")
            self.assertIn("购物车加购后确认订单金额需要保持一致", payload["requirement"])

    def test_build_task_package_fails_for_unknown_project(self) -> None:
        system_root = Path(__file__).resolve().parents[2]
        with self.assertRaisesRegex(ValueError, "Unknown project"):
            build_task_package(
                system_root=system_root,
                project="not-a-real-project",
                requirement="任意需求",
            )

    def test_build_task_package_collects_project_source_files(self) -> None:
        system_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = build_task_package(
                system_root=system_root,
                project="example-wxapp",
                requirement="购物车、门店和确认订单联动风险检查",
                output_root=Path(tmp_dir),
            )

            payload = json.loads((result.output_dir / "package.json").read_text(encoding="utf-8"))
            self.assertIn("sources", payload)
            self.assertIn("projects/example-wxapp/business-context.md", payload["sources"])
            self.assertIn("projects/example-wxapp/project-override.md", payload["sources"])
            self.assertIn("projects/example-wxapp/task-context.md", payload["sources"])

    def test_build_task_package_includes_project_baseline_and_change_spec_state(self) -> None:
        system_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = build_task_package(
                system_root=system_root,
                project="wwj-wxapp",
                requirement="退款商品数量交互变更需要先确认规格状态",
                output_root=Path(tmp_dir),
            )

            payload = json.loads((result.output_dir / "package.json").read_text(encoding="utf-8"))
            markdown = (result.output_dir / "package.md").read_text(encoding="utf-8")
            self.assertTrue(payload["project_baseline"]["exists"])
            self.assertIn("projects/wwj-wxapp/spec/project-baseline.md", payload["sources"])
            self.assertEqual(payload["change_spec"]["status"], "not_created")
            self.assertIn("Project Baseline", markdown)
            self.assertIn("Change Spec", markdown)

    def test_build_task_package_includes_summary_and_open_questions(self) -> None:
        system_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = build_task_package(
                system_root=system_root,
                project="example-wxapp",
                requirement="购物车相关需求",
                output_root=Path(tmp_dir),
            )

            payload = json.loads((result.output_dir / "package.json").read_text(encoding="utf-8"))
            self.assertIn("business_summary", payload)
            self.assertTrue(payload["business_summary"])
            self.assertIn("open_questions", payload)
            self.assertIn("risk_flags", payload)

    def test_build_task_package_reads_memory_lists(self) -> None:
        system_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = build_task_package(
                system_root=system_root,
                project="example-wxapp",
                requirement="需要购物车和按钮态的经验参考",
                output_root=Path(tmp_dir),
            )

            payload = json.loads((result.output_dir / "package.json").read_text(encoding="utf-8"))
            self.assertIn("recent_cases", payload)
            self.assertIn("matched_patterns", payload)
            self.assertIn("matched_rules", payload)

    def test_build_task_package_applies_playbook_guidance(self) -> None:
        system_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = build_task_package(
                system_root=system_root,
                project="example-wxapp",
                requirement="购物车加购后确认订单金额需要保持一致",
                output_root=Path(tmp_dir),
            )

            payload = json.loads((result.output_dir / "package.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["project_type"], "uniapp-mini-program")
            self.assertTrue(payload["suspected_modules"])
            self.assertTrue(payload["risk_flags"])

    def test_build_task_package_writes_back_and_syncs_package_markdown(self) -> None:
        system_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            output_root = tmp_root / "task-packages"
            runtime_root = tmp_root / "runtime"
            vault_root = tmp_root / "vault"
            memory_root = tmp_root
            note_path = "project-notes/codex-auto/system/example-wxapp-task-package.md"

            result = build_task_package(
                system_root=system_root,
                project="example-wxapp",
                requirement="购物车加购后需要自动写回知识库并同步记忆",
                output_root=output_root,
                runtime_root=runtime_root,
                vault_root=vault_root,
                note_path=note_path,
                memory_root=memory_root,
                task_slug="2026-05-19-example-wxapp-auto-closeout",
            )

            self.assertTrue((vault_root / note_path).exists())
            self.assertTrue((memory_root / "memory" / "projects" / "example-wxapp" / "cases").exists())
            synced_cases = list((memory_root / "memory" / "projects" / "example-wxapp" / "cases").glob("*.md"))
            self.assertTrue(synced_cases)
            status_path = runtime_root / "task-runs" / "example-wxapp" / "2026-05-19-example-wxapp-auto-closeout" / "status.json"
            self.assertTrue(status_path.exists())
            payload = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "closed")
            self.assertEqual([item["state"] for item in payload["history"]], ["packaged", "written_back", "synced", "closed"])

    def test_build_task_package_marks_pending_closeout_without_writeback_target(self) -> None:
        system_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            output_root = tmp_root / "task-packages"
            runtime_root = tmp_root / "runtime"

            build_task_package(
                system_root=system_root,
                project="example-wxapp",
                requirement="只打包，不做写回的场景",
                output_root=output_root,
                runtime_root=runtime_root,
                task_slug="2026-05-19-example-wxapp-pending-closeout",
            )

            status_path = runtime_root / "task-runs" / "example-wxapp" / "2026-05-19-example-wxapp-pending-closeout" / "status.json"
            payload = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertEqual([item["state"] for item in payload["history"]], ["packaged", "pending-closeout"])
