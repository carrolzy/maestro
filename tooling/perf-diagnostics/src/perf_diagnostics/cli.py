from __future__ import annotations

import argparse
import json
from pathlib import Path

from perf_diagnostics.analyzers.heuristics import build_heuristics
from perf_diagnostics.analyzers.hotspots import analyze_hotspots
from perf_diagnostics.analyzers.stalls import analyze_stalls
from perf_diagnostics.case_dir import create_case_dir, load_case_meta
from perf_diagnostics.normalize import normalize_trace
from perf_diagnostics.reporting import render_report
from perf_diagnostics.trace_loader import load_trace
from perf_diagnostics.writeback import render_writeback


def main(
    argv: list[str] | None = None,
    *,
    system_root: Path | None = None,
    stdout_path: Path | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="Chrome Performance trace diagnostics helper.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--project", required=True)
    init_parser.add_argument("--trace", required=True)
    init_parser.add_argument("--label", required=True)
    init_parser.add_argument("--date", default=None)

    analyze_parser = subparsers.add_parser("analyze")
    analyze_parser.add_argument("--case-dir", required=True)

    writeback_parser = subparsers.add_parser("writeback")
    writeback_parser.add_argument("--case-dir", required=True)

    sync_parser = subparsers.add_parser("sync")
    sync_parser.add_argument("--case-dir", required=True)
    sync_parser.add_argument("--vault-root", required=True)
    sync_parser.add_argument("--note-path", default=None)
    sync_parser.add_argument("--slug", default=None)

    args = parser.parse_args(argv)
    resolved_root = system_root or Path(__file__).resolve().parents[4]

    if args.command == "init":
        case_dir = create_case_dir(
            system_root=resolved_root,
            project=args.project,
            trace_path=Path(args.trace),
            label=args.label,
            date_str=args.date,
        )
        _write_output(str(case_dir) + "\n", stdout_path)
        return 0

    case_dir = Path(args.case_dir)
    case_meta = load_case_meta(case_dir)

    if args.command == "analyze":
        trace = load_trace(case_dir / "01_raw" / "trace.json")
        normalized = normalize_trace(trace)
        stalls = analyze_stalls(normalized["task_events"])
        hotspots = analyze_hotspots(normalized["task_events"])
        heuristics = build_heuristics(normalized["trace_overview"], stalls, hotspots)

        _write_json(case_dir / "02_parsed" / "trace_overview.json", normalized["trace_overview"])
        _write_json(case_dir / "03_analysis" / "hotspots.json", hotspots)

        summary = {
            "case_meta": case_meta,
            "trace_overview": normalized["trace_overview"],
            "stall_windows": stalls,
            "top_hotspots": hotspots,
            "cross_page_signals": heuristics["cross_page_signals"],
            "request_render_signals": heuristics["request_render_signals"],
            "suspected_causes": heuristics["suspected_causes"],
            "recommended_actions": heuristics["recommended_actions"],
            "confidence": heuristics["confidence"],
        }
        _write_json(case_dir / "03_analysis" / "summary.json", summary)
        report = render_report(case_meta, summary, hotspots)
        (case_dir / "03_analysis" / "report.md").write_text(report, encoding="utf-8")
        _write_output(str(case_dir / "03_analysis" / "report.md") + "\n", stdout_path)
        return 0

    if args.command == "writeback":
        summary = json.loads((case_dir / "03_analysis" / "summary.json").read_text(encoding="utf-8"))
        writeback = render_writeback(case_meta, summary)
        output_path = case_dir / "04_writeback" / "writeback.md"
        output_path.write_text(writeback, encoding="utf-8")
        _write_output(str(output_path) + "\n", stdout_path)
        return 0

    source_file = case_dir / "04_writeback" / "writeback.md"
    if not source_file.exists():
        raise ValueError(f"Missing writeback draft: {source_file}")
    from writeback_and_sync_memory import writeback_and_sync_memory

    note_path = args.note_path or _default_note_path(case_meta)
    synced_case_path, index_path = writeback_and_sync_memory(
        vault_root=Path(args.vault_root),
        note_path=note_path,
        project=str(case_meta["project"]),
        source_file=source_file,
        memory_root=resolved_root,
        slug=args.slug,
    )
    output = "\n".join(
        [
            f"note_path={Path(args.vault_root) / note_path}",
            f"memory_case={synced_case_path}",
            f"index_path={index_path}",
        ]
    )
    _write_output(output + "\n", stdout_path)
    return 0


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_output(text: str, stdout_path: Path | None) -> None:
    if stdout_path is not None:
        stdout_path.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


def _default_note_path(case_meta: dict[str, object]) -> str:
    case_dir_name = Path(str(case_meta["case_dir"])).name
    return f"project-notes/codex-auto/{case_meta['project']}/{case_dir_name}.md"


if __name__ == "__main__":
    raise SystemExit(main())
