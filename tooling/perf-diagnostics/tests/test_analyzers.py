import json
import unittest
from pathlib import Path

from perf_diagnostics.analyzers.heuristics import build_heuristics
from perf_diagnostics.analyzers.hotspots import analyze_hotspots
from perf_diagnostics.analyzers.stalls import analyze_stalls
from perf_diagnostics.normalize import normalize_trace


FIXTURES = Path(__file__).parent / "fixtures"


class AnalyzerTests(unittest.TestCase):
    def test_normalize_trace_extracts_overview(self) -> None:
        trace = json.loads((FIXTURES / "minimal_trace.json").read_text(encoding="utf-8"))

        normalized = normalize_trace(trace)

        self.assertEqual(normalized["trace_overview"]["event_count"], 2)
        self.assertEqual(normalized["trace_overview"]["time_span_ms"], 28.0)

    def test_stalls_capture_long_tasks_and_windows(self) -> None:
        trace = json.loads((FIXTURES / "miniapp_hotspot_trace.json").read_text(encoding="utf-8"))

        normalized = normalize_trace(trace)
        stalls = analyze_stalls(normalized["task_events"])

        self.assertEqual(stalls["long_task_count"], 3)
        self.assertEqual(stalls["max_blocking_task_ms"], 91.0)
        self.assertEqual(len(stalls["stall_windows"]), 3)

    def test_hotspots_group_heavy_work_by_script_and_keyword(self) -> None:
        trace = json.loads((FIXTURES / "miniapp_hotspot_trace.json").read_text(encoding="utf-8"))

        normalized = normalize_trace(trace)
        hotspots = analyze_hotspots(normalized["task_events"])

        self.assertEqual(hotspots["top_scripts"][0]["script"], "pages5/marketing/cms-activity-page.js")
        self.assertIn("patch", hotspots["top_keywords"][0]["keyword"])

    def test_heuristics_rank_miniapp_causes(self) -> None:
        trace = json.loads((FIXTURES / "miniapp_hotspot_trace.json").read_text(encoding="utf-8"))

        normalized = normalize_trace(trace)
        stalls = analyze_stalls(normalized["task_events"])
        hotspots = analyze_hotspots(normalized["task_events"])
        heuristics = build_heuristics(normalized["trace_overview"], stalls, hotspots)

        self.assertTrue(heuristics["cross_page_signals"])
        self.assertTrue(heuristics["suspected_causes"])
        self.assertIn("旧页异步残留", heuristics["suspected_causes"][0]["title"])
