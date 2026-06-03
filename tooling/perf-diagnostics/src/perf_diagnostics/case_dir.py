from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path


def create_case_dir(
    *,
    system_root: Path,
    project: str,
    trace_path: Path,
    label: str,
    date_str: str | None = None,
) -> Path:
    if not trace_path.exists():
        raise ValueError(f"Trace file not found: {trace_path}")

    slug = _slugify(label)
    case_date = date_str or datetime.now().strftime("%Y-%m-%d")
    case_dir = system_root / "runtime" / "perf-cases" / project / f"{case_date}-{slug}"
    for name in ("01_raw", "02_parsed", "03_analysis", "04_writeback"):
        (case_dir / name).mkdir(parents=True, exist_ok=True)

    shutil.copyfile(trace_path, case_dir / "01_raw" / "trace.json")
    meta = {
        "project": project,
        "label": slug,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_trace_path": str(trace_path),
        "case_dir": str(case_dir),
    }
    (case_dir / "case.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return case_dir


def load_case_meta(case_dir: Path) -> dict[str, object]:
    meta_path = case_dir / "case.json"
    if not meta_path.exists():
        raise ValueError(f"Missing case metadata: {meta_path}")
    return json.loads(meta_path.read_text(encoding="utf-8"))


def _slugify(text: str) -> str:
    lowered = text.strip().lower()
    slug = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "-", lowered)
    slug = slug.strip("-")
    return slug or "trace-case"
