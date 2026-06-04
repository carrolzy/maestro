#!/usr/bin/env python3
"""Canonical tool registry — the single source of truth for Maestro's tools.

Every surface that exposes Maestro's core operations as callable tools (the MCP
server, and the per-provider adapters in `tooling/adapters/`) consumes the same
specs from here. Each spec declares the tool's `name`, a human `title`, a
`description`, and full `inputSchema` + `outputSchema` (with per-field
descriptions). Keeping this list in one place means a Claude, OpenAI/DeepSeek, or
Gemini integration never re-declares tools by hand and never drifts from the MCP
contract.

Pure data, zero runtime dependencies.
"""
from __future__ import annotations

from typing import Any

JsonDict = dict[str, Any]


def _tool_schema(
    name: str,
    title: str,
    description: str,
    properties: JsonDict,
    *,
    output_schema: JsonDict,
    required: list[str] | None = None,
) -> JsonDict:
    return {
        "name": name,
        "title": title,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "required": required or [],
            "additionalProperties": False,
        },
        "outputSchema": output_schema,
    }


TOOL_SPECS: list[JsonDict] = [
    _tool_schema(
        "search_memory",
        "Search Memory",
        "Search local project cards, recent memory cases, reusable patterns, and standing rules.",
        {
            "project": {"type": "string", "description": "Project slug to scope the search to; omit to search across projects."},
            "query": {"type": "string", "description": "Free-text query; tokens are matched against cards, cases, patterns, and rules."},
            "max_projects": {"type": "integer", "minimum": 1, "description": "Maximum project cards to return (default 5)."},
            "max_cases": {"type": "integer", "minimum": 1, "description": "Maximum recent cases to return (default 5)."},
            "max_matches": {"type": "integer", "minimum": 1, "description": "Maximum pattern/rule matches to return (default 5)."},
        },
        output_schema={
            "type": "object",
            "properties": {
                "project_cards": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "slug": {"type": "string"},
                            "business_context": {"type": ["string", "null"]},
                            "summary": {"type": "string"},
                        },
                    },
                },
                "project_override": {"type": ["object", "null"]},
                "recent_cases": {"type": "array"},
                "matched_patterns": {"type": "array"},
                "matched_rules": {"type": "array"},
            },
            "required": ["project_cards", "project_override", "recent_cases", "matched_patterns", "matched_rules"],
            "additionalProperties": False,
        },
    ),
    _tool_schema(
        "build_task_package",
        "Build Task Package",
        "Build a task package from project context and requirement text.",
        {
            "project": {"type": "string", "description": "Registered project slug."},
            "requirement": {"type": "string", "description": "The task requirement in natural language."},
            "slug": {"type": "string", "description": "Optional output slug; derived from the requirement when omitted."},
            "output_root": {"type": "string", "description": "Override directory for generated task-package artifacts."},
            "runtime_root": {"type": "string", "description": "Runtime root for task-run state (defaults to <system>/runtime)."},
            "vault_root": {"type": "string", "description": "Obsidian vault root, when also writing back."},
            "note_path": {"type": "string", "description": "Relative vault note path, when also writing back."},
            "dev_doc_path": {"type": "string", "description": "Optional development technical document to summarize into the package."},
            "memory_root": {"type": "string", "description": "Memory root override for the synced case."},
            "task_slug": {"type": "string", "description": "Task-run slug to record lifecycle state under."},
        },
        required=["project", "requirement"],
        output_schema={
            "type": "object",
            "properties": {
                "output_dir": {"type": "string"},
                "package": {"type": "object"},
            },
            "required": ["output_dir"],
            "additionalProperties": False,
        },
    ),
    _tool_schema(
        "register_project",
        "Register Project",
        "Register a new project shell from the canonical templates.",
        {
            "project": {"type": "string", "description": "New project slug (kebab-case)."},
            "summary": {"type": "string", "description": "One-sentence project summary seeded into the cards."},
            "project_type": {"type": "string", "description": "Optional project-type hint, e.g. uniapp-mini-program."},
            "force": {"type": "boolean", "description": "Overwrite the three canonical files if the project already exists."},
        },
        required=["project", "summary"],
        output_schema={
            "type": "object",
            "properties": {"project_dir": {"type": "string"}},
            "required": ["project_dir"],
            "additionalProperties": False,
        },
    ),
    _tool_schema(
        "update_task_run_state",
        "Update Task Run State",
        "Write or append a task-run lifecycle state.",
        {
            "runtime_root": {"type": "string", "description": "Runtime root (defaults to <system>/runtime)."},
            "project": {"type": "string", "description": "Project slug."},
            "task_slug": {"type": "string", "description": "Task-run slug."},
            "state": {"type": "string", "description": "Lifecycle state, e.g. packaged, written_back, synced, closed."},
        },
        required=["project", "task_slug", "state"],
        output_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "project": {"type": "string"},
                "task_slug": {"type": "string"},
                "state": {"type": "string"},
            },
            "required": ["path", "project", "task_slug", "state"],
            "additionalProperties": False,
        },
    ),
    _tool_schema(
        "writeback_and_sync_memory",
        "Write Back and Sync Memory",
        "Write a markdown note into the vault and sync it into project memory.",
        {
            "vault_root": {"type": "string", "description": "Obsidian vault root (defaults to the server's configured vault)."},
            "note_path": {"type": "string", "description": "Relative note path inside the vault."},
            "project": {"type": "string", "description": "Project slug the note belongs to."},
            "source_file": {"type": "string", "description": "Markdown source file to write into the vault and mirror into memory."},
            "memory_root": {"type": "string", "description": "Memory root override (defaults to the system root)."},
            "slug": {"type": "string", "description": "Optional output slug override."},
            "append": {"type": "boolean", "description": "Append to an existing note instead of replacing it."},
        },
        required=["note_path", "project", "source_file"],
        output_schema={
            "type": "object",
            "properties": {
                "case_path": {"type": "string"},
                "index_path": {"type": "string"},
            },
            "required": ["case_path", "index_path"],
            "additionalProperties": False,
        },
    ),
    _tool_schema(
        "doctor_local_skills",
        "Doctor Local Skills",
        "Assess repo-owned local skill installation status.",
        {
            "dest_root": {"type": "string", "description": "Skills install directory to inspect (defaults to the server's configured destination)."},
        },
        output_schema={
            "type": "object",
            "properties": {
                "dest_root": {"type": "string"},
                "skills": {"type": "object"},
            },
            "required": ["dest_root", "skills"],
            "additionalProperties": False,
        },
    ),
    _tool_schema(
        "validate_project",
        "Validate Project",
        "Check a registered project's readiness: canonical files, playbook, business card, project type.",
        {
            "project": {"type": "string", "description": "Project slug to validate."},
        },
        required=["project"],
        output_schema={
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "valid": {"type": "boolean"},
                "checks": {"type": "object"},
                "issues": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["project", "valid", "checks", "issues"],
            "additionalProperties": False,
        },
    ),
    _tool_schema(
        "list_project_types",
        "List Project Types",
        "List available project-type templates with descriptions, rules, and pitfalls.",
        {},
        output_schema={
            "type": "object",
            "properties": {
                "project_types": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                            "rules": {"type": "array", "items": {"type": "string"}},
                            "pitfalls": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                },
            },
            "required": ["project_types"],
            "additionalProperties": False,
        },
    ),
]


def tool_names() -> list[str]:
    """All registered tool names, in registry order."""
    return [spec["name"] for spec in TOOL_SPECS]


def get_spec(name: str) -> JsonDict:
    """Return the canonical spec for a tool, or raise KeyError if unknown."""
    for spec in TOOL_SPECS:
        if spec["name"] == name:
            return spec
    raise KeyError(f"Unknown tool: {name}")
