#!/usr/bin/env python3
"""Agentic code-search primitives — grep, glob, slice-read, and outline.

Claude Code proved the pattern: no persistent code index, ever. Code changes
with every commit, so any static index (embeddings, ctags files) is a stale
snapshot the moment it's built. Instead, expose fast *live* search primitives
and let the calling model drive a multi-hop loop (search → read → follow
references). The intelligence lives in the model; these tools only guarantee
fresh results straight from the working tree.

Maestro is the hub, business repos live elsewhere — every primitive takes a
`repo_root` so any MCP client (Codex, Claude, raw-API models) can search any
registered project's code through one protocol.

`grep_code` uses ripgrep when available (fast, .gitignore-aware) and degrades
to a pure-Python scanner otherwise. Zero third-party deps either way.
"""
from __future__ import annotations

import fnmatch
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

JsonDict = dict[str, Any]

DEFAULT_MAX_MATCHES = 50
DEFAULT_CONTEXT_LINES = 2
MAX_FILE_BYTES = 2_000_000  # pure-Python scanner skips files larger than this

# Directories that are never worth searching (mirrors ripgrep's defaults
# closely enough for the fallback scanner).
SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", "unpackage", ".venv", "venv",
    "__pycache__", ".idea", ".vscode", "coverage", ".next", ".nuxt",
}


def _resolve_repo_root(repo_root: str | Path) -> Path:
    root = Path(repo_root).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"repo_root is not a directory: {root}")
    return root


def _rg_binary() -> str | None:
    """Real ripgrep binary, or None (interactive shells may alias rg)."""
    return shutil.which("rg")


# ── grep ────────────────────────────────────────────────────────────────────

def grep_code(
    *,
    repo_root: str | Path,
    pattern: str,
    glob: str | None = None,
    case_insensitive: bool = False,
    fixed_string: bool = False,
    max_matches: int = DEFAULT_MAX_MATCHES,
    context_lines: int = DEFAULT_CONTEXT_LINES,
) -> JsonDict:
    """Search live file contents. Returns matches as {path, line, text, context}."""
    root = _resolve_repo_root(repo_root)
    if not pattern:
        raise ValueError("pattern is required")
    max_matches = max(1, min(int(max_matches), 500))
    context_lines = max(0, min(int(context_lines), 10))

    rg = _rg_binary()
    if rg:
        matches, truncated = _grep_with_rg(
            rg, root, pattern,
            glob=glob, case_insensitive=case_insensitive,
            fixed_string=fixed_string, max_matches=max_matches,
            context_lines=context_lines,
        )
        engine = "ripgrep"
    else:
        matches, truncated = _grep_pure_python(
            root, pattern,
            glob=glob, case_insensitive=case_insensitive,
            fixed_string=fixed_string, max_matches=max_matches,
            context_lines=context_lines,
        )
        engine = "python"

    return {
        "repo_root": str(root),
        "pattern": pattern,
        "engine": engine,
        "matches": matches,
        "match_count": len(matches),
        "truncated": truncated,
    }


def _grep_with_rg(
    rg: str, root: Path, pattern: str, *,
    glob: str | None, case_insensitive: bool, fixed_string: bool,
    max_matches: int, context_lines: int,
) -> tuple[list[JsonDict], bool]:
    cmd = [rg, "--json", "--max-count", str(max_matches)]
    if context_lines:
        cmd += ["--context", str(context_lines)]
    if case_insensitive:
        cmd.append("--ignore-case")
    if fixed_string:
        cmd.append("--fixed-strings")
    if glob:
        cmd += ["--glob", glob]
    for ignored in sorted(SKIP_DIRS):
        cmd += ["--glob", f"!{ignored}/**"]
    cmd += ["--", pattern, "."]

    try:
        result = subprocess.run(
            cmd, cwd=root, capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError(f"ripgrep failed: {exc}") from exc
    if result.returncode == 2:
        raise ValueError(f"ripgrep error: {result.stderr.strip()[:500]}")

    matches: list[JsonDict] = []
    context_buf: dict[str, list[JsonDict]] = {}
    for line in result.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        etype = event.get("type")
        data = event.get("data", {})
        if etype not in ("match", "context"):
            continue
        path = ((data.get("path") or {}).get("text", "")).removeprefix("./")
        text = ((data.get("lines") or {}).get("text") or "").rstrip("\n")
        line_no = data.get("line_number")
        if etype == "context":
            context_buf.setdefault(path, []).append({"line": line_no, "text": text})
            continue
        if len(matches) >= max_matches:
            return matches, True
        matches.append({
            "path": path,
            "line": line_no,
            "text": text,
            "context": context_buf.pop(path, []),
        })
    return matches, False


def _iter_searchable_files(root: Path, glob: str | None) -> list[Path]:
    files: list[Path] = []
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = sorted(current.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.is_dir():
                if entry.name not in SKIP_DIRS and not entry.name.startswith("."):
                    stack.append(entry)
                continue
            rel = entry.relative_to(root).as_posix()
            if glob and not (fnmatch.fnmatch(rel, glob) or fnmatch.fnmatch(entry.name, glob)):
                continue
            files.append(entry)
    files.sort()
    return files


def _grep_pure_python(
    root: Path, pattern: str, *,
    glob: str | None, case_insensitive: bool, fixed_string: bool,
    max_matches: int, context_lines: int,
) -> tuple[list[JsonDict], bool]:
    flags = re.IGNORECASE if case_insensitive else 0
    regex = re.compile(re.escape(pattern) if fixed_string else pattern, flags)

    matches: list[JsonDict] = []
    for file_path in _iter_searchable_files(root, glob):
        try:
            if file_path.stat().st_size > MAX_FILE_BYTES:
                continue
            raw = file_path.read_bytes()
        except OSError:
            continue
        if b"\x00" in raw[:8192]:
            continue  # binary
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        lines = text.splitlines()
        rel = file_path.relative_to(root).as_posix()
        for i, line_text in enumerate(lines):
            if not regex.search(line_text):
                continue
            if len(matches) >= max_matches:
                return matches, True
            lo = max(0, i - context_lines)
            hi = min(len(lines), i + context_lines + 1)
            context = [
                {"line": n + 1, "text": lines[n]}
                for n in range(lo, hi) if n != i
            ]
            matches.append({
                "path": rel,
                "line": i + 1,
                "text": line_text,
                "context": context,
            })
    return matches, False


# ── glob ────────────────────────────────────────────────────────────────────

def glob_files(
    *,
    repo_root: str | Path,
    pattern: str,
    max_results: int = 100,
) -> JsonDict:
    """List files matching a glob pattern, newest first."""
    root = _resolve_repo_root(repo_root)
    if not pattern:
        raise ValueError("pattern is required")
    max_results = max(1, min(int(max_results), 1000))

    found: list[tuple[float, Path]] = []
    for path in root.glob(pattern):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(root).parts
        if any(part in SKIP_DIRS for part in rel_parts[:-1]):
            continue
        try:
            found.append((path.stat().st_mtime, path))
        except OSError:
            continue
    found.sort(key=lambda x: (-x[0], x[1].as_posix()))
    truncated = len(found) > max_results
    files = [
        {"path": p.relative_to(root).as_posix(), "mtime": int(mtime)}
        for mtime, p in found[:max_results]
    ]
    return {
        "repo_root": str(root),
        "pattern": pattern,
        "files": files,
        "file_count": len(files),
        "truncated": truncated,
    }


# ── read slice ──────────────────────────────────────────────────────────────

def read_file_slice(
    *,
    repo_root: str | Path,
    file_path: str,
    start_line: int = 1,
    max_lines: int = 200,
) -> JsonDict:
    """Read a line range of a file. Keeps context windows small by design."""
    root = _resolve_repo_root(repo_root)
    target = (root / file_path).resolve()
    if not str(target).startswith(str(root)):
        raise ValueError(f"file_path escapes repo_root: {file_path}")
    if not target.is_file():
        raise ValueError(f"Not a file: {file_path}")
    start_line = max(1, int(start_line))
    max_lines = max(1, min(int(max_lines), 1000))

    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise ValueError(f"Cannot read {file_path}: {exc}") from exc
    lines = text.splitlines()
    total = len(lines)
    end_line = min(total, start_line - 1 + max_lines)
    slice_lines = [
        {"line": n + 1, "text": lines[n]}
        for n in range(start_line - 1, end_line)
    ]
    return {
        "repo_root": str(root),
        "path": target.relative_to(root).as_posix(),
        "start_line": start_line,
        "end_line": end_line,
        "total_lines": total,
        "lines": slice_lines,
        "truncated": end_line < total,
    }


# ── outline ─────────────────────────────────────────────────────────────────

# Regex-based symbol extraction (a lightweight ctags). Computed on demand from
# live files, never persisted — that is the freshness guarantee.
_SYMBOL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("function", re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)")),
    ("function", re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>")),
    ("class", re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+([A-Za-z_$][\w$]*)")),
    ("function", re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)")),
    ("class", re.compile(r"^\s*class\s+([A-Za-z_]\w*)")),
    ("method", re.compile(r"^\s{2,}(?:public|private|protected|static|async)\s+(?:async\s+)?([A-Za-z_$][\w$]*)\s*\(")),
    ("interface", re.compile(r"^\s*(?:export\s+)?(?:interface|type|enum)\s+([A-Za-z_$][\w$]*)")),
]

_OUTLINE_EXTENSIONS = {
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".py", ".php",
    ".java", ".go", ".rb", ".swift", ".kt",
}


def _extract_symbols(text: str) -> list[JsonDict]:
    symbols: list[JsonDict] = []
    for i, line in enumerate(text.splitlines()):
        for kind, regex in _SYMBOL_PATTERNS:
            m = regex.match(line)
            if m:
                symbols.append({"name": m.group(1), "kind": kind, "line": i + 1})
                break
    return symbols


def repo_outline(
    *,
    repo_root: str | Path,
    path: str | None = None,
    max_depth: int = 3,
    max_entries: int = 200,
) -> JsonDict:
    """Directory tree; for a single file, its extracted symbols.

    Always computed live — never cached to disk, so it can't go stale.
    """
    root = _resolve_repo_root(repo_root)
    max_depth = max(1, min(int(max_depth), 8))
    max_entries = max(1, min(int(max_entries), 1000))

    if path:
        target = (root / path).resolve()
        if not str(target).startswith(str(root)):
            raise ValueError(f"path escapes repo_root: {path}")
        if target.is_file():
            text = target.read_text(encoding="utf-8", errors="replace")
            symbols = (
                _extract_symbols(text)
                if target.suffix in _OUTLINE_EXTENSIONS
                else []
            )
            return {
                "repo_root": str(root),
                "path": target.relative_to(root).as_posix(),
                "kind": "file",
                "symbols": symbols[:max_entries],
                "entries": [],
                "truncated": len(symbols) > max_entries,
            }
        if not target.is_dir():
            raise ValueError(f"No such path: {path}")
        base = target
    else:
        base = root

    entries: list[JsonDict] = []
    truncated = False

    def walk(directory: Path, depth: int) -> None:
        nonlocal truncated
        if depth > max_depth or truncated:
            return
        try:
            children = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name))
        except OSError:
            return
        for child in children:
            if child.name.startswith(".") or child.name in SKIP_DIRS:
                continue
            if len(entries) >= max_entries:
                truncated = True
                return
            rel = child.relative_to(root).as_posix()
            entries.append({
                "path": rel,
                "kind": "dir" if child.is_dir() else "file",
                "depth": depth,
            })
            if child.is_dir():
                walk(child, depth + 1)

    walk(base, 1)
    return {
        "repo_root": str(root),
        "path": base.relative_to(root).as_posix() if base != root else ".",
        "kind": "dir",
        "symbols": [],
        "entries": entries,
        "truncated": truncated,
    }
