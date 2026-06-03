import json
import tempfile
import unittest
from pathlib import Path

from perf_diagnostics.trace_loader import load_trace


class TraceLoaderTests(unittest.TestCase):
    def test_load_trace_accepts_valid_traceevents_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "trace.json"
            path.write_text(json.dumps({"traceEvents": [{"name": "RunTask"}]}), encoding="utf-8")

            result = load_trace(path)

            self.assertEqual(len(result["traceEvents"]), 1)

    def test_load_trace_accepts_top_level_trace_event_array(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "trace.json"
            path.write_text(json.dumps([{"name": "RunTask"}]), encoding="utf-8")

            result = load_trace(path)

            self.assertEqual(len(result["traceEvents"]), 1)

    def test_load_trace_rejects_malformed_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "trace.json"
            path.write_text("{", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Malformed JSON"):
                load_trace(path)

    def test_load_trace_requires_traceevents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "trace.json"
            path.write_text(json.dumps({"events": []}), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "traceEvents"):
                load_trace(path)
