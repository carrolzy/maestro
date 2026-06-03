import tempfile
import unittest
from pathlib import Path

from context_pack import build_context_pack, main


class ContextPackTests(unittest.TestCase):
    def test_build_context_pack_includes_key_sections(self) -> None:
        system_root = Path(__file__).resolve().parents[2]
        text = build_context_pack(
            system_root=system_root,
            project="example-wxapp",
            requirement="购物车确认订单一致性",
        )
        self.assertIn("# Task Package", text)
        self.assertIn("## Request", text)
        self.assertIn("## Project", text)

    def test_cli_writes_to_out_file(self) -> None:
        system_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "pack.md"
            exit_code = main(
                argv=["--project", "example-wxapp", "--requirement", "购物车一致性", "--out", str(out)],
                system_root=system_root,
            )
            self.assertEqual(exit_code, 0)
            self.assertIn("# Task Package", out.read_text(encoding="utf-8"))
