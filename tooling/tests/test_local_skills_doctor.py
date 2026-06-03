import tempfile
import unittest
from pathlib import Path

from local_skills_doctor import assess_local_skills, bootstrap_local_skills
from doctor_local_skills import main
from local_skill_installer import MARKER_FILENAME


class LocalSkillsDoctorTests(unittest.TestCase):
    def test_assess_local_skills_reports_missing_installed_drifted_and_unmanaged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir) / "system"
            dest_root = Path(tmp_dir) / "dest"
            for name, body in (
                ("project-intake", "# intake v1"),
                ("memory-read-first", "# memory v1"),
                ("writeback-and-sync", "# writeback v1"),
                ("verification-before-close", "# verify v1"),
            ):
                skill_dir = system_root / "skills" / name
                skill_dir.mkdir(parents=True)
                (skill_dir / "SKILL.md").write_text(body, encoding="utf-8")

            installed_dir = dest_root / "project-intake"
            installed_dir.mkdir(parents=True)
            (installed_dir / "SKILL.md").write_text("# intake v1", encoding="utf-8")
            (installed_dir / MARKER_FILENAME).write_text(
                str((system_root / "skills" / "project-intake").resolve()) + "\n",
                encoding="utf-8",
            )

            drifted_dir = dest_root / "memory-read-first"
            drifted_dir.mkdir(parents=True)
            (drifted_dir / "SKILL.md").write_text("# stale copy", encoding="utf-8")
            (drifted_dir / MARKER_FILENAME).write_text(
                str((system_root / "skills" / "memory-read-first").resolve()) + "\n",
                encoding="utf-8",
            )

            unmanaged_dir = dest_root / "writeback-and-sync"
            unmanaged_dir.mkdir(parents=True)
            (unmanaged_dir / "SKILL.md").write_text("# user managed", encoding="utf-8")

            statuses = assess_local_skills(system_root=system_root, dest_root=dest_root)

            self.assertEqual(statuses["project-intake"].status, "installed")
            self.assertEqual(statuses["memory-read-first"].status, "drifted")
            self.assertEqual(statuses["writeback-and-sync"].status, "unmanaged")
            self.assertEqual(statuses["verification-before-close"].status, "missing")

    def test_bootstrap_local_skills_installs_missing_and_repairs_drifted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir) / "system"
            dest_root = Path(tmp_dir) / "dest"
            source_dir = system_root / "skills" / "project-intake"
            source_dir.mkdir(parents=True)
            (source_dir / "SKILL.md").write_text("# fresh", encoding="utf-8")

            drifted_dir = dest_root / "project-intake"
            drifted_dir.mkdir(parents=True)
            (drifted_dir / "SKILL.md").write_text("# stale", encoding="utf-8")
            (drifted_dir / MARKER_FILENAME).write_text(str(source_dir.resolve()) + "\n", encoding="utf-8")

            results = bootstrap_local_skills(system_root=system_root, dest_root=dest_root)

            self.assertEqual(results["project-intake"], "reinstalled")
            self.assertEqual((drifted_dir / "SKILL.md").read_text(encoding="utf-8"), "# fresh")

    def test_bootstrap_local_skills_skips_unmanaged_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir) / "system"
            dest_root = Path(tmp_dir) / "dest"
            source_dir = system_root / "skills" / "project-intake"
            source_dir.mkdir(parents=True)
            (source_dir / "SKILL.md").write_text("# fresh", encoding="utf-8")

            unmanaged_dir = dest_root / "project-intake"
            unmanaged_dir.mkdir(parents=True)
            (unmanaged_dir / "SKILL.md").write_text("# user managed", encoding="utf-8")

            results = bootstrap_local_skills(system_root=system_root, dest_root=dest_root)

            self.assertEqual(results["project-intake"], "skipped-unmanaged")
            self.assertEqual((unmanaged_dir / "SKILL.md").read_text(encoding="utf-8"), "# user managed")

    def test_cli_doctor_prints_human_readable_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir)
            skill_dir = system_root / "skills" / "project-intake"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("# intake", encoding="utf-8")
            output_path = Path(tmp_dir) / "stdout.txt"

            exit_code = main(
                argv=["--dest", str(Path(tmp_dir) / "dest")],
                system_root=system_root,
                stdout_path=output_path,
            )

            output_text = output_path.read_text(encoding="utf-8")
            self.assertEqual(exit_code, 1)
            self.assertIn("project-intake: missing", output_text)
            self.assertIn("Restart Codex after installing or reinstalling skills.", output_text)
