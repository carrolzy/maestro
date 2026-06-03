import tempfile
import unittest
from pathlib import Path

from writeback_and_sync_memory import writeback_and_sync_memory


class WritebackAndSyncMemoryTests(unittest.TestCase):
    def test_writeback_and_sync_memory_rejects_unknown_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            system_root = tmp_root / "system"
            vault_root = tmp_root / "vault"
            source_file = tmp_root / "source.md"
            source_file.write_text(
                (
                    "# Request\n\n"
                    "Unknown project.\n\n"
                    "## Context Used\n\n- temp\n\n"
                    "## Implementation\n\n- temp\n\n"
                    "## Verification\n\n- temp\n\n"
                    "## Risks / Follow-up\n\n- temp\n\n"
                    "## File References\n\n- temp.md\n"
                ),
                encoding="utf-8",
            )
            (system_root / "projects" / "known-project").mkdir(parents=True)

            with self.assertRaisesRegex(ValueError, "Unknown project"):
                writeback_and_sync_memory(
                    vault_root=vault_root,
                    note_path="project-notes/codex-auto/not-a-real-project/2026-05-20-unknown.md",
                    project="not-a-real-project",
                    source_file=source_file,
                    memory_root=system_root,
                )

    def test_writeback_and_sync_memory_rejects_note_missing_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            system_root = tmp_root / "system"
            vault_root = tmp_root / "vault"
            source_file = tmp_root / "source.md"
            source_file.write_text("one-line note\n", encoding="utf-8")
            (system_root / "projects" / "example-capture").mkdir(parents=True)

            with self.assertRaisesRegex(ValueError, "missing required sections"):
                writeback_and_sync_memory(
                    vault_root=vault_root,
                    note_path="project-notes/codex-auto/example-capture/2026-05-20-trivial.md",
                    project="example-capture",
                    source_file=source_file,
                    memory_root=system_root,
                )

    def test_writeback_and_sync_memory_happy_path_still_writes_and_syncs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            system_root = tmp_root / "system"
            vault_root = tmp_root / "vault"
            source_file = tmp_root / "source.md"
            source_file.write_text(
                (
                    "# Request\n\n"
                    "Happy path.\n\n"
                    "## Context Used\n\n- temp\n\n"
                    "## Implementation\n\n- temp\n\n"
                    "## Verification\n\n- temp\n\n"
                    "## Risks / Follow-up\n\n- temp\n\n"
                    "## File References\n\n- temp.md\n"
                ),
                encoding="utf-8",
            )
            (system_root / "projects" / "example-capture").mkdir(parents=True)

            case_path, index_path = writeback_and_sync_memory(
                vault_root=vault_root,
                note_path="project-notes/codex-auto/example-capture/2026-05-20-happy.md",
                project="example-capture",
                source_file=source_file,
                memory_root=system_root,
            )

            self.assertTrue((vault_root / "project-notes/codex-auto/example-capture/2026-05-20-happy.md").exists())
            self.assertTrue(case_path.exists())
            self.assertTrue(index_path.exists())

