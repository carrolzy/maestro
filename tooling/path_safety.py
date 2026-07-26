"""Containment checks for paths owned by Maestro roots."""
from __future__ import annotations

from pathlib import Path


def require_descendant(root: Path, candidate: Path) -> Path:
    """Resolve *candidate* and require it to remain under *root*."""
    resolved_root = root.expanduser().resolve()
    resolved_candidate = candidate.expanduser().resolve()
    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"Path escapes root: {candidate}") from exc
    return resolved_candidate


def resolve_relative_child(root: Path, raw_path: str) -> Path:
    """Resolve a relative path under *root* without allowing an escape."""
    relative_path = Path(raw_path)
    if relative_path.is_absolute():
        raise ValueError(f"Path must be relative: {raw_path}")
    return require_descendant(root, root / relative_path)
