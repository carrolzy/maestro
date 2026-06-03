#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

from local_skills_doctor import assess_local_skills
from register_project import register_project
from search_memory import search_memory
from task_package_builder import build_task_package
from update_task_run_state import update_task_run_state
from writeback_and_sync_memory import writeback_and_sync_memory


JsonDict = dict[str, Any]

DEFAULT_PROTOCOL_VERSION = "2025-06-18"
SUPPORTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")


class AiEfficiencyMcpServer:
    def __init__(
        self,
        *,
        system_root: Path,
        vault_root: Path | None = None,
        skills_dest_root: Path | None = None,
    ) -> None:
        self.system_root = Path(system_root).expanduser().resolve()
        self.vault_root = (
            Path(vault_root).expanduser().resolve()
            if vault_root
            else Path(os.environ.get("AI_EFF_VAULT_ROOT", Path.home() / "Documents" / "my-knowledge-base")).expanduser().resolve()
        )
        self.skills_dest_root = (
            Path(skills_dest_root).expanduser().resolve()
            if skills_dest_root
            else Path(os.environ.get("AI_EFF_SKILLS_DEST", Path.home() / ".codex" / "skills")).expanduser().resolve()
        )
        self._tools: dict[str, Callable[[JsonDict], JsonDict]] = {
            "search_memory": self._call_search_memory,
            "build_task_package": self._call_build_task_package,
            "register_project": self._call_register_project,
            "update_task_run_state": self._call_update_task_run_state,
            "writeback_and_sync_memory": self._call_writeback_and_sync_memory,
            "doctor_local_skills": self._call_doctor_local_skills,
        }

    def handle_request(self, request: JsonDict) -> JsonDict | None:
        method = request.get("method")
        request_id = request.get("id")

        if request_id is None:
            return None

        try:
            if method == "initialize":
                params = _as_dict(request.get("params") or {}, "params")
                requested = params.get("protocolVersion")
                protocol_version = requested if requested in SUPPORTED_PROTOCOL_VERSIONS else DEFAULT_PROTOCOL_VERSION
                result = {
                    "protocolVersion": protocol_version,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "maestro", "title": "Maestro", "version": "0.1.0"},
                }
                return _success_response(request_id=request_id, result=result)
            if method == "ping":
                return _success_response(request_id=request_id, result={})
            if method == "tools/list":
                return _success_response(request_id=request_id, result={"tools": _tool_definitions()})
            if method == "tools/call":
                params = _as_dict(request.get("params"), "params")
                tool_name = _required_string(params, "name")
                arguments = _as_dict(params.get("arguments", {}), "arguments")
                return _success_response(request_id=request_id, result=self.call_tool(tool_name, arguments))
            return _error_response(request_id=request_id, code=-32601, message=f"Unknown method: {method}")
        except Exception as exc:
            return _error_response(request_id=request_id, code=-32603, message=str(exc))

    def call_tool(self, tool_name: str, arguments: JsonDict) -> JsonDict:
        tool = self._tools.get(tool_name)
        if tool is None:
            return _tool_error(f"Unknown tool: {tool_name}")

        try:
            payload = tool(arguments)
        except Exception as exc:
            return _tool_error(str(exc))

        return _tool_result(payload)

    def _call_search_memory(self, arguments: JsonDict) -> JsonDict:
        return search_memory(
            system_root=self.system_root,
            project=_optional_string(arguments, "project"),
            query=_optional_string(arguments, "query"),
            max_projects=_optional_int(arguments, "max_projects", 5),
            max_cases=_optional_int(arguments, "max_cases", 5),
            max_matches=_optional_int(arguments, "max_matches", 5),
        )

    def _call_build_task_package(self, arguments: JsonDict) -> JsonDict:
        result = build_task_package(
            system_root=self.system_root,
            project=_required_string(arguments, "project"),
            requirement=_required_string(arguments, "requirement"),
            slug=_optional_string(arguments, "slug"),
            output_root=_optional_path(arguments, "output_root"),
            runtime_root=_optional_path(arguments, "runtime_root"),
            vault_root=_optional_path(arguments, "vault_root"),
            note_path=_optional_string(arguments, "note_path"),
            dev_doc_path=_optional_path(arguments, "dev_doc_path"),
            memory_root=_optional_path(arguments, "memory_root"),
            task_slug=_optional_string(arguments, "task_slug"),
        )
        package_json = result.output_dir / "package.json"
        payload: JsonDict = {"output_dir": str(result.output_dir)}
        if package_json.exists():
            payload["package"] = json.loads(package_json.read_text(encoding="utf-8"))
        return payload

    def _call_register_project(self, arguments: JsonDict) -> JsonDict:
        project_dir = register_project(
            system_root=self.system_root,
            project=_required_string(arguments, "project"),
            summary=_required_string(arguments, "summary"),
            project_type=_optional_string(arguments, "project_type"),
            force=bool(arguments.get("force", False)),
        )
        return {"project_dir": str(project_dir)}

    def _call_update_task_run_state(self, arguments: JsonDict) -> JsonDict:
        runtime_root = _optional_path(arguments, "runtime_root") or (self.system_root / "runtime")
        output_path = update_task_run_state(
            runtime_root=runtime_root,
            project=_required_string(arguments, "project"),
            task_slug=_required_string(arguments, "task_slug"),
            state=_required_string(arguments, "state"),
        )
        return {
            "path": str(output_path),
            "project": _required_string(arguments, "project"),
            "task_slug": _required_string(arguments, "task_slug"),
            "state": _required_string(arguments, "state"),
        }

    def _call_writeback_and_sync_memory(self, arguments: JsonDict) -> JsonDict:
        output_path, index_path = writeback_and_sync_memory(
            vault_root=_optional_path(arguments, "vault_root") or self.vault_root,
            note_path=_required_string(arguments, "note_path"),
            project=_required_string(arguments, "project"),
            source_file=_required_path(arguments, "source_file"),
            memory_root=_optional_path(arguments, "memory_root") or self.system_root,
            project_root=self.system_root,
            slug=_optional_string(arguments, "slug"),
            append=bool(arguments.get("append", False)),
        )
        return {"case_path": str(output_path), "index_path": str(index_path)}

    def _call_doctor_local_skills(self, arguments: JsonDict) -> JsonDict:
        dest_root = _optional_path(arguments, "dest_root") or self.skills_dest_root
        statuses = assess_local_skills(system_root=self.system_root, dest_root=dest_root)
        return {
            "dest_root": str(dest_root),
            "skills": {
                name: {
                    "status": status.status,
                    "detail": status.detail,
                }
                for name, status in statuses.items()
            },
        }


def _tool_definitions() -> list[JsonDict]:
    return [
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
    ]


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


def write_jsonl_responses(*, server: AiEfficiencyMcpServer, lines: list[str], stdout_path: Path | None = None) -> None:
    responses = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        response = server.handle_request(json.loads(stripped))
        if response is not None:
            responses.append(json.dumps(response, ensure_ascii=False))

    output = "\n".join(responses)
    if output:
        output += "\n"
    if stdout_path is None:
        print(output, end="")
    else:
        stdout_path.write_text(output, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the AI efficiency system MCP server over JSONL stdio.")
    parser.add_argument("--system-root", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--vault-root", default=None)
    parser.add_argument("--skills-dest-root", default=None)
    parser.add_argument("--input", default=None, help="Optional JSONL input file for tests or replay.")
    parser.add_argument("--output", default=None, help="Optional JSONL output file for tests or replay.")
    args = parser.parse_args(argv)

    server = AiEfficiencyMcpServer(
        system_root=Path(args.system_root),
        vault_root=Path(args.vault_root) if args.vault_root else None,
        skills_dest_root=Path(args.skills_dest_root) if args.skills_dest_root else None,
    )
    input_lines = Path(args.input).read_text(encoding="utf-8").splitlines() if args.input else sys.stdin
    output_path = Path(args.output) if args.output else None
    write_jsonl_responses(server=server, lines=list(input_lines), stdout_path=output_path)
    return 0


def _success_response(*, request_id: Any, result: JsonDict) -> JsonDict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error_response(*, request_id: Any, code: int, message: str) -> JsonDict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _tool_result(payload: JsonDict) -> JsonDict:
    return {
        "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}],
        "structuredContent": payload,
        "isError": False,
    }


def _tool_error(message: str) -> JsonDict:
    return {
        "content": [{"type": "text", "text": message}],
        "structuredContent": {"error": message},
        "isError": True,
    }


def _as_dict(value: Any, label: str) -> JsonDict:
    if isinstance(value, dict):
        return value
    raise ValueError(f"{label} must be an object")


def _required_string(arguments: JsonDict, key: str) -> str:
    value = arguments.get(key)
    if isinstance(value, str) and value:
        return value
    raise ValueError(f"Missing required string argument: {key}")


def _optional_string(arguments: JsonDict, key: str) -> str | None:
    value = arguments.get(key)
    if value is None:
        return None
    if isinstance(value, str):
        return value
    raise ValueError(f"{key} must be a string")


def _optional_int(arguments: JsonDict, key: str, default: int) -> int:
    value = arguments.get(key, default)
    if isinstance(value, int):
        return max(1, value)
    raise ValueError(f"{key} must be an integer")


def _optional_path(arguments: JsonDict, key: str) -> Path | None:
    value = _optional_string(arguments, key)
    return Path(value).expanduser().resolve() if value else None


def _required_path(arguments: JsonDict, key: str) -> Path:
    return Path(_required_string(arguments, key)).expanduser().resolve()


if __name__ == "__main__":
    raise SystemExit(main())
