from __future__ import annotations


def render_report(case_meta: dict[str, object], summary: dict[str, object], hotspots: dict[str, object]) -> str:
    overview = summary["trace_overview"]
    stalls = summary["stall_windows"]
    causes = summary["suspected_causes"]
    actions = summary["recommended_actions"]
    top_scripts = hotspots.get("top_scripts", [])[:3]

    lines = [
        f"# Performance Report: {case_meta['label']}",
        "",
        "## Trace Overview",
        "",
        f"- Project: `{case_meta['project']}`",
        f"- Event count: `{overview['event_count']}`",
        f"- Task event count: `{overview['task_event_count']}`",
        f"- Time span: `{overview['time_span_ms']} ms`",
        "",
        "## Main Findings",
        "",
        f"- Long task count: `{stalls['long_task_count']}`",
        f"- Max blocking task: `{stalls['max_blocking_task_ms']} ms`",
    ]
    for item in top_scripts:
        lines.append(f"- Hot script: `{item['script']}` total `{item['total_duration_ms']} ms`")

    lines.extend(["", "## Likely Causes", ""])
    if causes:
        for cause in causes:
            lines.append(f"- {cause['title']} ({cause['confidence']})")
    else:
        lines.append("- No high-signal cause hypothesis yet.")

    lines.extend(["", "## Recommended Actions", ""])
    if actions:
        for action in actions:
            lines.append(f"- {action}")
    else:
        lines.append("- Record another trace with a narrower reproduction window.")

    return "\n".join(lines) + "\n"
