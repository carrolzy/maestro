#!/usr/bin/env python3
"""Runtime targets for installing repo-local skills.

Maestro's skills are plain Markdown procedures; only their *install location*
differs per agent runtime. This registry keeps the skill installer
model-agnostic: any runtime is just a name mapped to a default skills
directory and a friendly label.

Resolution order for the install destination:
  1. an explicit --dest / dest argument
  2. the AI_EFF_SKILLS_DEST environment variable
  3. the selected runtime's default directory
"""
from __future__ import annotations

import os
from pathlib import Path

ENV_SKILLS_DEST = "AI_EFF_SKILLS_DEST"
DEFAULT_RUNTIME = "codex"

RUNTIMES: dict[str, dict[str, str]] = {
    "codex": {"skills_dir": "~/.codex/skills", "label": "Codex"},
    "claude": {"skills_dir": "~/.claude/skills", "label": "Claude Code"},
    "generic": {"skills_dir": "~/.config/agent-skills", "label": "the agent runtime"},
}


def known_runtimes() -> list[str]:
    return sorted(RUNTIMES)


def runtime_label(runtime: str) -> str:
    return RUNTIMES.get(runtime, RUNTIMES["generic"])["label"]


def restart_message(runtime: str) -> str:
    return f"Restart {runtime_label(runtime)} after installing or reinstalling skills."


def resolve_skills_dest(
    *,
    runtime: str = DEFAULT_RUNTIME,
    dest: str | None = None,
    env: dict[str, str] | None = None,
) -> Path:
    """Resolve the skills install directory following the documented priority."""
    environ = env if env is not None else os.environ
    if dest:
        chosen = dest
    elif environ.get(ENV_SKILLS_DEST):
        chosen = environ[ENV_SKILLS_DEST]
    else:
        chosen = RUNTIMES.get(runtime, RUNTIMES["generic"])["skills_dir"]
    return Path(chosen).expanduser().resolve()
