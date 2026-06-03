from __future__ import annotations


def render_writeback(case_meta: dict[str, object], summary: dict[str, object]) -> str:
    findings = summary["suspected_causes"]
    actions = summary["recommended_actions"]
    signals = summary["cross_page_signals"] + summary["request_render_signals"]

    lines = [
        f"# {case_meta['label']} performance diagnostics",
        "",
        "## Request",
        "",
        f"Performance investigation for `{case_meta['project']}` based on Chrome Performance exported JSON.",
        "",
        f"- Source trace: `{case_meta['source_trace_path']}`",
        "",
        "## Context Used",
        "",
        f"- Case dir: `{case_meta['case_dir']}`",
        f"- Confidence: `{summary['confidence']}`",
        f"- Trace event count: `{summary['trace_overview']['event_count']}`",
        f"- Time span: `{summary['trace_overview']['time_span_ms']} ms`",
        "",
        "## Implementation",
        "",
    ]
    if signals:
        for signal in signals:
            lines.append(f"- {signal}")
    else:
        lines.append("- No strong signals extracted from this trace.")

    lines.extend(["", "## Verification", ""])
    lines.append(
        f"- Long task count: `{summary['stall_windows']['long_task_count']}`; max blocking task: `{summary['stall_windows']['max_blocking_task_ms']} ms`."
    )
    lines.append("- Tool-generated first-pass diagnostics only; follow-up reproduction still required.")

    lines.extend(["", "## Risks / Follow-up", ""])
    if actions:
        for action in actions:
            lines.append(f"- {action}")
    else:
        lines.append("- Capture another trace around a narrower user interaction window.")

    lines.extend(["", "## File References", ""])
    if findings:
        for finding in findings:
            lines.append(f"- {finding['title']} ({finding['confidence']})")
    else:
        lines.append("- No stable root-cause hypothesis yet.")

    return "\n".join(lines) + "\n"
