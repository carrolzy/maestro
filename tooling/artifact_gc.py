#!/usr/bin/env python3
"""Artifact lifecycle engine — scan, archive, restore, and clean Maestro artifacts.

Everything the system produces eventually goes cold: task runs, task packages,
perf traces, memory cases, scratch scripts, and temp files parked in business
repos. Left alone they grow without bound (a single perf trace can be 60 MB).
This engine applies the retention policy in `base/retention.json`:

  - **archive** categories (task_runs, task_packages, perf_cases, memory_cases)
    are gzip-compressed into an archive layer once they age out. Nothing is
    ever silently deleted — `restore` reverses any archive.
  - **delete** categories (scratch, registered temp files) are genuinely
    throwaway: useful during the post-release verification window, garbage
    after. `clean` removes them once expired — dry-run by default, and a temp
    file that is git-tracked in its repo is never touched.

Memory patterns and rules are permanent assets: not governed here at all.

Layout:
  runtime/archive/task-runs/<project>/<slug>.tar.gz
  runtime/archive/task-packages/<project>/<slug>.tar.gz
  runtime/archive/perf-cases/<project>/<slug>.tar.gz
  memory/projects/<project>/cases/<case>.md.gz   (compressed in place)

Pure stdlib (tarfile/gzip). Zero third-party deps.
"""
from __future__ import annotations

import argparse
import gzip
import json
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from active_task import get_active_task
from temp_registry import expired_temp_files, remove_entries

JsonDict = dict[str, Any]

DEFAULT_POLICY = {
    "scratch": {"action": "delete", "ttl_days": 30},
    "temp_files": {"action": "delete", "ttl_days": 30},
    "task_runs": {"action": "archive", "ttl_days": 90},
    "task_packages": {"action": "archive", "ttl_days": 90},
    "perf_cases": {"action": "archive", "ttl_days": 30},
    "memory_cases": {"action": "archive", "ttl_days": 180},
}

# Category → runtime subdirectory holding <project>/<slug> artifact dirs.
_RUNTIME_DIRS = {
    "task_runs": "task-runs",
    "task_packages": "task-packages",
    "perf_cases": "perf-cases",
}


def load_policy(system_root: Path) -> dict[str, JsonDict]:
    """Load retention policy, falling back to defaults per missing category."""
    path = system_root / "base" / "retention.json"
    policy = {name: dict(spec) for name, spec in DEFAULT_POLICY.items()}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for name, spec in (data.get("categories") or {}).items():
                if name in policy and isinstance(spec, dict):
                    policy[name].update(spec)
        except (json.JSONDecodeError, OSError):
            pass
    return policy


def _newest_mtime(path: Path) -> float:
    """Newest mtime of a file, or of any file within a directory tree."""
    if path.is_file():
        return path.stat().st_mtime
    newest = path.stat().st_mtime
    for child in path.rglob("*"):
        try:
            newest = max(newest, child.stat().st_mtime)
        except OSError:
            continue
    return newest


def _is_expired(path: Path, ttl_days: int, now: datetime) -> bool:
    cutoff = now - timedelta(days=ttl_days)
    return datetime.fromtimestamp(_newest_mtime(path), tz=timezone.utc) < cutoff


def _dir_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def _is_git_tracked(file_path: Path) -> bool:
    """True if the file is tracked by the git repo that contains it.

    Errs on the safe side: if git can't be consulted, treat as tracked
    (i.e. protected from deletion).
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(file_path.parent), "ls-files", "--error-unmatch", file_path.name],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return True
    return result.returncode == 0


def _active_task_slug(system_root: Path) -> tuple[str, str] | None:
    active = get_active_task(system_root / "runtime")
    if active:
        return (active["project"], active["task_slug"])
    return None


def _iter_runtime_artifacts(system_root: Path, category: str):
    """Yield (project, slug, path) for <runtime>/<dir>/<project>/<slug>."""
    base = system_root / "runtime" / _RUNTIME_DIRS[category]
    if not base.is_dir():
        return
    for project_dir in sorted(base.iterdir()):
        if not project_dir.is_dir() or project_dir.name.startswith("."):
            continue
        for slug_dir in sorted(project_dir.iterdir()):
            if slug_dir.is_dir() and not slug_dir.name.startswith("."):
                yield project_dir.name, slug_dir.name, slug_dir


def _iter_memory_cases(system_root: Path):
    """Yield (project, case_path) for uncompressed memory case files."""
    base = system_root / "memory" / "projects"
    if not base.is_dir():
        return
    for project_dir in sorted(base.iterdir()):
        case_dir = project_dir / "cases"
        if not case_dir.is_dir():
            continue
        for case in sorted(case_dir.glob("*.md")):
            yield project_dir.name, case


def _iter_scratch(system_root: Path):
    """Yield (project, slug, path) for scratch task directories."""
    base = system_root / "runtime" / "scratch"
    if not base.is_dir():
        return
    for project_dir in sorted(base.iterdir()):
        if not project_dir.is_dir():
            continue
        for slug_dir in sorted(project_dir.iterdir()):
            if slug_dir.is_dir():
                yield project_dir.name, slug_dir.name, slug_dir


def scan(system_root: Path, *, now: datetime | None = None) -> JsonDict:
    """Report expired artifacts per category and the bytes each would free.

    Read-only: never modifies anything.
    """
    current = now or datetime.now(timezone.utc)
    policy = load_policy(system_root)
    active = _active_task_slug(system_root)
    report: JsonDict = {"categories": {}, "total_reclaimable_bytes": 0}

    for category in _RUNTIME_DIRS:
        ttl = int(policy[category]["ttl_days"])
        items = []
        for project, slug, path in _iter_runtime_artifacts(system_root, category):
            if active == (project, slug):
                continue  # never touch the active task
            if _is_expired(path, ttl, current):
                size = _dir_size(path)
                items.append({"project": project, "slug": slug, "path": str(path), "bytes": size})
        report["categories"][category] = {
            "action": policy[category]["action"],
            "ttl_days": ttl,
            "expired": items,
            "bytes": sum(i["bytes"] for i in items),
        }

    ttl = int(policy["memory_cases"]["ttl_days"])
    cases = []
    for project, case in _iter_memory_cases(system_root):
        if _is_expired(case, ttl, current):
            cases.append({"project": project, "path": str(case), "bytes": case.stat().st_size})
    report["categories"]["memory_cases"] = {
        "action": "archive",
        "ttl_days": ttl,
        "expired": cases,
        "bytes": sum(c["bytes"] for c in cases),
    }

    ttl = int(policy["scratch"]["ttl_days"])
    scratch_items = []
    for project, slug, path in _iter_scratch(system_root):
        if active == (project, slug):
            continue
        if _is_expired(path, ttl, current):
            scratch_items.append({"project": project, "slug": slug, "path": str(path), "bytes": _dir_size(path)})
    report["categories"]["scratch"] = {
        "action": "delete",
        "ttl_days": ttl,
        "expired": scratch_items,
        "bytes": sum(i["bytes"] for i in scratch_items),
    }

    temp_items = []
    for entry in expired_temp_files(system_root / "runtime", now=current):
        path = Path(entry["path"])
        if not path.exists():
            temp_items.append({**entry, "bytes": 0, "status": "already_gone"})
            continue
        tracked = _is_git_tracked(path)
        temp_items.append({
            **entry,
            "bytes": path.stat().st_size,
            "status": "git_tracked_protected" if tracked else "deletable",
        })
    report["categories"]["temp_files"] = {
        "action": "delete",
        "ttl_days": int(policy["temp_files"]["ttl_days"]),
        "expired": temp_items,
        "bytes": sum(i["bytes"] for i in temp_items if i.get("status") == "deletable"),
    }

    report["total_reclaimable_bytes"] = sum(
        c["bytes"] for c in report["categories"].values()
    )
    return report


def archive(system_root: Path, *, now: datetime | None = None) -> JsonDict:
    """Compress expired archive-category artifacts. Reversible via restore()."""
    current = now or datetime.now(timezone.utc)
    policy = load_policy(system_root)
    active = _active_task_slug(system_root)
    archived: list[JsonDict] = []
    bytes_before = 0
    bytes_after = 0

    for category, subdir in _RUNTIME_DIRS.items():
        ttl = int(policy[category]["ttl_days"])
        for project, slug, path in _iter_runtime_artifacts(system_root, category):
            if active == (project, slug) or not _is_expired(path, ttl, current):
                continue
            dest_dir = system_root / "runtime" / "archive" / subdir / project
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / f"{slug}.tar.gz"
            original = _dir_size(path)
            with tarfile.open(dest, "w:gz") as tar:
                tar.add(path, arcname=slug)
            shutil.rmtree(path)
            # Drop the now-empty project dir to keep listings clean.
            try:
                path.parent.rmdir()
            except OSError:
                pass
            compressed = dest.stat().st_size
            bytes_before += original
            bytes_after += compressed
            archived.append({
                "category": category, "project": project, "slug": slug,
                "archive": str(dest), "bytes_before": original, "bytes_after": compressed,
            })

    ttl = int(policy["memory_cases"]["ttl_days"])
    for project, case in _iter_memory_cases(system_root):
        if not _is_expired(case, ttl, current):
            continue
        original = case.stat().st_size
        dest = case.with_suffix(case.suffix + ".gz")
        with case.open("rb") as src, gzip.open(dest, "wb") as out:
            shutil.copyfileobj(src, out)
        case.unlink()
        compressed = dest.stat().st_size
        bytes_before += original
        bytes_after += compressed
        archived.append({
            "category": "memory_cases", "project": project, "slug": case.stem,
            "archive": str(dest), "bytes_before": original, "bytes_after": compressed,
        })

    return {
        "archived": archived,
        "count": len(archived),
        "bytes_before": bytes_before,
        "bytes_after": bytes_after,
        "bytes_saved": bytes_before - bytes_after,
    }


def restore(system_root: Path, *, archive_path: str) -> JsonDict:
    """Reverse an archive: .tar.gz back to its directory, .md.gz back to .md."""
    path = Path(archive_path).expanduser().resolve()
    if not path.exists():
        raise ValueError(f"Archive not found: {path}")

    if path.name.endswith(".tar.gz"):
        # runtime/archive/<subdir>/<project>/<slug>.tar.gz →
        # runtime/<subdir>/<project>/<slug>/
        archive_root = (system_root / "runtime" / "archive").resolve()
        try:
            rel = path.relative_to(archive_root)
        except ValueError as exc:
            raise ValueError(f"tar.gz archives must live under {archive_root}") from exc
        dest_parent = system_root / "runtime" / rel.parent
        dest_parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(path, "r:gz") as tar:
            try:
                tar.extractall(dest_parent, filter="data")
            except TypeError:
                # Python < 3.10.12: no filter kwarg. Archives are self-produced,
                # but still guard against absolute/parent-escaping members.
                for member in tar.getmembers():
                    target = (dest_parent / member.name).resolve()
                    if not str(target).startswith(str(dest_parent.resolve())):
                        raise ValueError(f"Unsafe path in archive: {member.name}")
                tar.extractall(dest_parent)
        path.unlink()
        restored_to = dest_parent / path.name.removesuffix(".tar.gz")
        return {"restored": str(restored_to), "archive_removed": str(path)}

    if path.name.endswith(".md.gz"):
        dest = path.with_name(path.name.removesuffix(".gz"))
        with gzip.open(path, "rb") as src, dest.open("wb") as out:
            shutil.copyfileobj(src, out)
        path.unlink()
        return {"restored": str(dest), "archive_removed": str(path)}

    raise ValueError(f"Unsupported archive type: {path.name} (expected .tar.gz or .md.gz)")


def clean(system_root: Path, *, now: datetime | None = None, apply: bool = False) -> JsonDict:
    """Delete expired scratch dirs and registered temp files.

    Dry-run unless apply=True. Git-tracked temp files are never deleted.
    """
    current = now or datetime.now(timezone.utc)
    report = scan(system_root, now=current)
    deleted: list[str] = []
    skipped: list[JsonDict] = []

    for item in report["categories"]["scratch"]["expired"]:
        path = Path(item["path"])
        if apply:
            shutil.rmtree(path, ignore_errors=True)
            try:
                path.parent.rmdir()
            except OSError:
                pass
        deleted.append(item["path"])

    removed_entries: list[str] = []
    for item in report["categories"]["temp_files"]["expired"]:
        path = Path(item["path"])
        if item.get("status") == "git_tracked_protected":
            skipped.append({"path": item["path"], "reason": "git-tracked"})
            continue
        if item.get("status") == "already_gone":
            removed_entries.append(item["path"])
            continue
        if apply:
            try:
                path.unlink()
            except OSError as exc:
                skipped.append({"path": item["path"], "reason": str(exc)})
                continue
        deleted.append(item["path"])
        removed_entries.append(item["path"])

    if apply and removed_entries:
        remove_entries(system_root / "runtime", removed_entries)

    return {
        "dry_run": not apply,
        "deleted": deleted,
        "skipped": skipped,
        "bytes_freed": report["categories"]["scratch"]["bytes"] + report["categories"]["temp_files"]["bytes"],
    }


def _human(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f}{unit}" if unit != "B" else f"{int(value)}B"
        value /= 1024
    return f"{value:.1f}GB"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Maestro artifact lifecycle (scan/archive/restore/clean)")
    parser.add_argument("command", choices=["scan", "archive", "restore", "clean"])
    parser.add_argument("--system-root", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--archive-path", help="restore: path to a .tar.gz or .md.gz produced by archive")
    parser.add_argument("--yes", action="store_true", help="clean: actually delete (default is dry-run)")
    parser.add_argument("--json", action="store_true", help="emit raw JSON")
    args = parser.parse_args(argv)

    system_root = Path(args.system_root).expanduser().resolve()

    if args.command == "scan":
        result = scan(system_root)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            for name, cat in result["categories"].items():
                print(f"{name} ({cat['action']}, ttl {cat['ttl_days']}d): "
                      f"{len(cat['expired'])} expired, {_human(cat['bytes'])}")
            print(f"total reclaimable: {_human(result['total_reclaimable_bytes'])}")
        return 0

    if args.command == "archive":
        result = archive(system_root)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            for item in result["archived"]:
                print(f"archived {item['category']} {item['project']}/{item['slug']} "
                      f"{_human(item['bytes_before'])} → {_human(item['bytes_after'])}")
            print(f"{result['count']} archived, saved {_human(result['bytes_saved'])}")
        return 0

    if args.command == "restore":
        if not args.archive_path:
            parser.error("restore requires --archive-path")
        result = restore(system_root, archive_path=args.archive_path)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    result = clean(system_root, apply=args.yes)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        mode = "DELETED" if args.yes else "would delete (dry-run, pass --yes to apply)"
        for path in result["deleted"]:
            print(f"{mode}: {path}")
        for item in result["skipped"]:
            print(f"skipped: {item['path']} ({item['reason']})")
        print(f"bytes freed: {_human(result['bytes_freed'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
