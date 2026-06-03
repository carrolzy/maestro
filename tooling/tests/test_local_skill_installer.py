import tempfile
import unittest
from pathlib import Path

from install_local_skills import main
from local_skill_installer import (
    MARKER_FILENAME,
    install_all_local_skills,
    install_local_skill,
    list_local_skills,
)


class LocalSkillInstallerTests(unittest.TestCase):
    def test_list_local_skills_returns_sorted_skill_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir)
            skills_root = system_root / "skills"
            (skills_root / "z-last").mkdir(parents=True)
            (skills_root / "z-last" / "SKILL.md").write_text("z", encoding="utf-8")
            (skills_root / "a-first").mkdir(parents=True)
            (skills_root / "a-first" / "SKILL.md").write_text("a", encoding="utf-8")
            (skills_root / "notes").mkdir(parents=True)
            (skills_root / "notes" / "README.md").write_text("ignore", encoding="utf-8")

            self.assertEqual(list_local_skills(system_root=system_root), ["a-first", "z-last"])

    def test_install_local_skill_copies_directory_and_writes_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir) / "system"
            dest_root = Path(tmp_dir) / "dest"
            skill_dir = system_root / "skills" / "project-intake"
            (skill_dir / "references").mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("# Intake", encoding="utf-8")
            (skill_dir / "references" / "prompt.md").write_text("ref", encoding="utf-8")

            target_dir = install_local_skill(
                system_root=system_root,
                dest_root=dest_root,
                skill_name="project-intake",
            )

            self.assertEqual(target_dir, dest_root / "project-intake")
            self.assertTrue((target_dir / "SKILL.md").exists())
            self.assertEqual((target_dir / "references" / "prompt.md").read_text(encoding="utf-8"), "ref")
            self.assertEqual(
                (target_dir / MARKER_FILENAME).read_text(encoding="utf-8").strip(),
                str(skill_dir.resolve()),
            )

    def test_install_local_skill_refuses_to_overwrite_unmanaged_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir) / "system"
            dest_root = Path(tmp_dir) / "dest"
            skill_dir = system_root / "skills" / "project-intake"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("# Intake", encoding="utf-8")
            unmanaged_dir = dest_root / "project-intake"
            unmanaged_dir.mkdir(parents=True)
            (unmanaged_dir / "SKILL.md").write_text("# User managed", encoding="utf-8")

            with self.assertRaisesRegex(FileExistsError, "already exists and is not managed"):
                install_local_skill(
                    system_root=system_root,
                    dest_root=dest_root,
                    skill_name="project-intake",
                )

    def test_install_local_skill_updates_existing_managed_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir) / "system"
            dest_root = Path(tmp_dir) / "dest"
            skill_dir = system_root / "skills" / "project-intake"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("# New Intake", encoding="utf-8")

            managed_dir = dest_root / "project-intake"
            managed_dir.mkdir(parents=True)
            (managed_dir / "SKILL.md").write_text("# Old Intake", encoding="utf-8")
            (managed_dir / MARKER_FILENAME).write_text(str(skill_dir.resolve()) + "\n", encoding="utf-8")

            install_local_skill(
                system_root=system_root,
                dest_root=dest_root,
                skill_name="project-intake",
            )

            self.assertEqual((managed_dir / "SKILL.md").read_text(encoding="utf-8"), "# New Intake")

    def test_install_local_skill_can_take_over_unmanaged_directory_when_explicitly_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir) / "system"
            dest_root = Path(tmp_dir) / "dest"
            skill_dir = system_root / "skills" / "project-intake"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("# New Intake", encoding="utf-8")

            unmanaged_dir = dest_root / "project-intake"
            unmanaged_dir.mkdir(parents=True)
            (unmanaged_dir / "SKILL.md").write_text("# Old Manual Intake", encoding="utf-8")

            install_local_skill(
                system_root=system_root,
                dest_root=dest_root,
                skill_name="project-intake",
                takeover_unmanaged=True,
            )

            self.assertEqual((unmanaged_dir / "SKILL.md").read_text(encoding="utf-8"), "# New Intake")
            self.assertEqual(
                (unmanaged_dir / MARKER_FILENAME).read_text(encoding="utf-8").strip(),
                str(skill_dir.resolve()),
            )

    def test_install_all_local_skills_installs_every_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir) / "system"
            dest_root = Path(tmp_dir) / "dest"
            for name in ("project-intake", "writeback-and-sync"):
                skill_dir = system_root / "skills" / name
                skill_dir.mkdir(parents=True)
                (skill_dir / "SKILL.md").write_text(name, encoding="utf-8")

            installed_dirs = install_all_local_skills(system_root=system_root, dest_root=dest_root)

            self.assertEqual([path.name for path in installed_dirs], ["project-intake", "writeback-and-sync"])
            self.assertTrue((dest_root / "project-intake" / "SKILL.md").exists())
            self.assertTrue((dest_root / "writeback-and-sync" / "SKILL.md").exists())

    def test_cli_list_prints_skill_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir)
            for name in ("project-intake", "writeback-and-sync"):
                skill_dir = system_root / "skills" / name
                skill_dir.mkdir(parents=True)
                (skill_dir / "SKILL.md").write_text(name, encoding="utf-8")

            with tempfile.TemporaryDirectory() as capture_dir:
                output_path = Path(capture_dir) / "stdout.txt"
                exit_code = main(
                    argv=["--list"],
                    system_root=system_root,
                    stdout_path=output_path,
                )
                output_text = output_path.read_text(encoding="utf-8")

            self.assertEqual(exit_code, 0)
            self.assertEqual(output_text, "project-intake\nwriteback-and-sync\n")

    def test_cli_takeover_replaces_unmanaged_directory_when_flag_is_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir)
            skill_dir = system_root / "skills" / "project-intake"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("# Repo Intake", encoding="utf-8")

            dest_root = Path(tmp_dir) / "dest"
            unmanaged_dir = dest_root / "project-intake"
            unmanaged_dir.mkdir(parents=True)
            (unmanaged_dir / "SKILL.md").write_text("# Manual Intake", encoding="utf-8")

            output_path = Path(tmp_dir) / "stdout.txt"
            exit_code = main(
                argv=["--takeover", "--dest", str(dest_root), "project-intake"],
                system_root=system_root,
                stdout_path=output_path,
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual((unmanaged_dir / "SKILL.md").read_text(encoding="utf-8"), "# Repo Intake")
            self.assertTrue((unmanaged_dir / MARKER_FILENAME).exists())
