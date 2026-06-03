import json
import tempfile
import unittest
from pathlib import Path

from perf_diagnostics.case_dir import create_case_dir


class CaseDirTests(unittest.TestCase):
    def test_create_case_dir_copies_trace_and_writes_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir)
            trace_path = system_root / "Profile.json"
            trace_path.write_text('{"traceEvents":[]}', encoding="utf-8")

            case_dir = create_case_dir(
                system_root=system_root,
                project="example-wxapp",
                trace_path=trace_path,
                label="home-cms-return-lag",
                date_str="2026-05-26",
            )

            self.assertEqual(case_dir.name, "2026-05-26-home-cms-return-lag")
            self.assertTrue((case_dir / "01_raw" / "trace.json").exists())
            meta = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["project"], "example-wxapp")
            self.assertEqual(meta["label"], "home-cms-return-lag")
            self.assertEqual(meta["source_trace_path"], str(trace_path))
