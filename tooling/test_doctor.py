#!/usr/bin/env python3
"""Test-suite auditor — find redundant, orphaned, and stale tests in any repo.

Agent-driven development over-produces test files: each task tends to spawn a
new one (test-cart-fix.js, test-cart-final.js), throwaway probes get
"tidied" into test/ and committed, and tests outlive the modules they cover.
Because committed test files are git-tracked, artifact GC deliberately never
touches them — so the suite only ever grows.

This auditor reports four suspicion categories. Like `artifact_gc scan`, it
NEVER deletes anything: it produces a report with suggested actions for a
human to confirm.

Categories:
  - orphaned: the source module a test is anchored to no longer exists
  - task_named: task-style naming (-fix / -final / -v2 / date suffixes) —
    the fingerprint of a one-off probe that should have been scratch
  - stale: the covered source changed many times since the test last changed
    (needs `git`; skipped silently in non-git repos)
  - duplicate_coverage: multiple test files anchored to the same source module

Pure stdlib + the git CLI. Zero third-party deps.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

JsonDict = dict[str, Any]

# Directories that commonly hold tests, checked in repo root and one level in.
TEST_DIR_NAMES = ("test", "tests", "__tests__", "spec")

TEST_FILE_SUFFIXES = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".py", ".vue", ".php")

# Task-style naming: the fingerprint of one-off probes promoted into test/.
# `(?:\.(?:test|spec))?\.[a-z]+$` lets the suffix sit before either the bare
# extension (test-cart-fix.js) or a .test/.spec segment (cart-v2.test.js).
_EXT = r"(?:\.(?:test|spec))?\.[a-z]+$"
TASK_NAME_PATTERNS = (
    re.compile(r"[-_](fix|fixed|final|new|old|bak|backup|tmp|temp|copy)\d*" + _EXT, re.IGNORECASE),
    re.compile(r"[-_]v\d+" + _EXT, re.IGNORECASE),
    re.compile(r"[-_]\d{1,2}" + _EXT),                         # test-cart-2.js
    re.compile(r"[-_]20\d{2}[-_]?\d{2}[-_]?\d{2}"),            # date-stamped
    re.compile(r"[-_](debug|check|verify|probe|scratch)" + _EXT, re.IGNORECASE),
)

# How many source-side commits since the test's last change count as stale.
STALE_COMMIT_THRESHOLD = 5

# Integration/contract/e2e tests have no single source module — never orphans.
INTEGRATION_ANCHORS = ("conformance", "integration", "e2e", "smoke", "endtoend", "acceptance")

# Shortest anchor length eligible for fuzzy source matching (avoid 2-char noise).
_MIN_FUZZY_LEN = 4

# Common prefixes/suffixes that wrap the module name in a test filename.
_ANCHOR_STRIP = re.compile(
    r"^(test[-_.]?|spec[-_.]?)|([-_.]?(test|tests|spec|specs))(?=\.[a-z]+$)",
    re.IGNORECASE,
)


def _run_git(repo_root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            capture_output=True, text=True, timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout if result.returncode == 0 else ""


def _find_test_dirs(repo_root: Path) -> list[Path]:
    """Test directories at repo root or one level deep (src/tests etc.)."""
    found: list[Path] = []
    for name in TEST_DIR_NAMES:
        candidate = repo_root / name
        if candidate.is_dir():
            found.append(candidate)
    try:
        children = sorted(p for p in repo_root.iterdir() if p.is_dir())
    except OSError:
        children = []
    for child in children:
        if child.name.startswith(".") or child.name in ("node_modules", "dist", "build", "unpackage"):
            continue
        for name in TEST_DIR_NAMES:
            candidate = child / name
            if candidate.is_dir():
                found.append(candidate)
    return found


def _iter_test_files(test_dirs: list[Path]) -> list[Path]:
    files: list[Path] = []
    for d in test_dirs:
        for path in sorted(d.rglob("*")):
            if path.is_file() and path.suffix in TEST_FILE_SUFFIXES:
                files.append(path)
    return files


def _anchor_name(test_file: Path) -> str:
    """The module name a test file appears to be anchored to.

    test_cart.py → cart; cart.spec.ts → cart; CartTest.php → carttest (no
    strip — conservative); test-cart-fix.js → cart-fix (task suffix kept so
    task_named still fires on the raw name).
    """
    stem = test_file.name
    stripped = _ANCHOR_STRIP.sub("", stem)
    stripped = re.sub(r"\.[a-z]+$", "", stripped, flags=re.IGNORECASE)
    return stripped.strip("-_.").lower()


def _source_index(repo_root: Path, test_dirs: list[Path]) -> dict[str, list[str]]:
    """Map lowercase source-file stems AND directory names → repo-relative
    paths (tests excluded). Directory names are included because tests often
    anchor to a package (test_adapters.py ↔ adapters/)."""
    test_roots = {d.resolve() for d in test_dirs}
    index: dict[str, list[str]] = {}
    stack = [repo_root]
    while stack:
        current = stack.pop()
        try:
            entries = sorted(current.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.is_dir():
                if (entry.name.startswith(".") or entry.name in
                        ("node_modules", "dist", "build", "unpackage", "__pycache__", "venv", ".venv")):
                    continue
                if entry.resolve() in test_roots:
                    continue
                index.setdefault(entry.name.lower(), []).append(
                    entry.relative_to(repo_root).as_posix()
                )
                stack.append(entry)
                continue
            if entry.suffix not in TEST_FILE_SUFFIXES:
                continue
            index.setdefault(entry.stem.lower(), []).append(
                entry.relative_to(repo_root).as_posix()
            )
    return index


def _fuzzy_source_match(anchor: str, sources: dict[str, list[str]]) -> list[str]:
    """Resolve an anchor against source names, tolerating naming drift.

    Exact stem/dir match first; otherwise a containment match (anchor within a
    source name or vice versa, both ≥ _MIN_FUZZY_LEN) so test_workflow.py
    anchors to workflow_engine.py and test_task_run_state.py to
    update_task_run_state.py. Conservative on short names to avoid noise.
    """
    exact = sources.get(anchor)
    if exact:
        return exact
    if len(anchor) < _MIN_FUZZY_LEN:
        return []
    for name, paths in sources.items():
        if len(name) < _MIN_FUZZY_LEN:
            continue
        if anchor in name or name in anchor:
            return paths
        # Shared word-prefix (≥6 chars) covers inflection drift:
        # onboarding ↔ onboard_project. Long enough to avoid cart ↔ cartoon.
        prefix_len = 0
        for a, b in zip(anchor, name):
            if a != b:
                break
            prefix_len += 1
        if prefix_len >= 6:
            return paths
    return []


def _is_task_named(filename: str) -> bool:
    return any(p.search(filename) for p in TASK_NAME_PATTERNS)


def _commits_since(repo_root: Path, source_rel: str, since_ref_file: str) -> int:
    """Count commits touching source_rel since the last commit touching the test."""
    last_test_commit = _run_git(
        repo_root, "log", "-1", "--format=%H", "--", since_ref_file
    ).strip()
    if not last_test_commit:
        return 0
    out = _run_git(
        repo_root, "rev-list", "--count", f"{last_test_commit}..HEAD", "--", source_rel
    ).strip()
    try:
        return int(out)
    except ValueError:
        return 0


def audit_tests(*, repo_root: str | Path, stale_threshold: int = STALE_COMMIT_THRESHOLD) -> JsonDict:
    """Audit test directories of a repo. Read-only; returns a suspicion report."""
    root = Path(repo_root).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"repo_root is not a directory: {root}")
    stale_threshold = max(1, int(stale_threshold))

    test_dirs = _find_test_dirs(root)
    test_files = _iter_test_files(test_dirs)
    sources = _source_index(root, test_dirs)
    is_git = bool(_run_git(root, "rev-parse", "--is-inside-work-tree").strip() == "true")

    findings: list[JsonDict] = []
    anchor_map: dict[str, list[str]] = {}

    for tf in test_files:
        rel = tf.relative_to(root).as_posix()
        anchor = _anchor_name(tf)

        if _is_task_named(tf.name):
            findings.append({
                "path": rel,
                "category": "task_named",
                "detail": "task-style filename (fix/final/v2/date/debug suffix) — looks like a promoted one-off probe",
                "suggestion": "merge any real assertions into the module's canonical test file, then delete; future probes belong in the scratch area",
            })

        source_paths = _fuzzy_source_match(anchor, sources)
        # Also try progressively trimming trailing task-ish segments for the
        # orphan check, so test-cart-fix.js anchors to cart.js if it exists.
        if not source_paths and anchor:
            trimmed = re.sub(r"[-_](fix|fixed|final|new|old|v?\d+|debug|check|verify)$", "", anchor)
            if trimmed != anchor:
                source_paths = _fuzzy_source_match(trimmed, sources)
                anchor = trimmed if source_paths else anchor

        if anchor:
            anchor_map.setdefault(anchor, []).append(rel)

        if not source_paths:
            is_integration = any(key in anchor for key in INTEGRATION_ANCHORS)
            if anchor and not is_integration:  # unanchorable names still report
                findings.append({
                    "path": rel,
                    "category": "orphaned",
                    "detail": f"no source module named '{anchor}' found in the repo",
                    "suggestion": "if the module was removed/renamed, delete or re-anchor this test",
                })
            continue

        if is_git:
            source_rel = source_paths[0]
            behind = _commits_since(root, source_rel, rel)
            if behind >= stale_threshold:
                findings.append({
                    "path": rel,
                    "category": "stale",
                    "detail": f"source {source_rel} changed in {behind} commits since this test last changed",
                    "suggestion": "review whether the test still reflects current behavior; update or consciously confirm",
                })

    for anchor, rels in sorted(anchor_map.items()):
        if len(rels) > 1:
            for rel in rels:
                findings.append({
                    "path": rel,
                    "category": "duplicate_coverage",
                    "detail": f"{len(rels)} test files anchor to module '{anchor}': {', '.join(rels)}",
                    "suggestion": "consolidate into one canonical test file per module",
                })

    by_category: dict[str, int] = {}
    for f in findings:
        by_category[f["category"]] = by_category.get(f["category"], 0) + 1

    return {
        "repo_root": str(root),
        "test_dirs": [d.relative_to(root).as_posix() for d in test_dirs],
        "test_file_count": len(test_files),
        "git_history_checked": is_git,
        "findings": findings,
        "finding_count": len(findings),
        "by_category": by_category,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit a repo's test suite for redundancy (read-only).")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--stale-threshold", type=int, default=STALE_COMMIT_THRESHOLD,
                        help="Source commits since test change before flagging stale (default 5).")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = audit_tests(repo_root=args.repo_root, stale_threshold=args.stale_threshold)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print(f"test dirs: {', '.join(report['test_dirs']) or 'none found'}")
    print(f"test files: {report['test_file_count']}, findings: {report['finding_count']}")
    for category in ("orphaned", "task_named", "stale", "duplicate_coverage"):
        items = [f for f in report["findings"] if f["category"] == category]
        if not items:
            continue
        print(f"\n[{category}] ({len(items)})")
        for item in items:
            print(f"  {item['path']}")
            print(f"    {item['detail']}")
            print(f"    → {item['suggestion']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
