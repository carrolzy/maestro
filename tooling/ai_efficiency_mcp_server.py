#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

from checkpoint import Checkpoint, build_resume_context, save_checkpoint
from local_skills_doctor import assess_local_skills
from project_types import list_project_types
from register_project import register_project
from search_memory import search_memory
from task_package_builder import build_task_package
from tool_registry import TOOL_SPECS
from update_task_run_state import update_task_run_state
from validate_project import validate_project
from workflow_engine import WorkflowEngine
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
            "validate_project": self._call_validate_project,
            "list_project_types": self._call_list_project_types,
            "run_workflow": self._call_run_workflow,
            "get_workflow_status": self._call_get_workflow_status,
            "resume_task": self._call_resume_task,
            "handoff_task": self._call_handoff_task,
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

    def invoke(self, tool_name: str, arguments: JsonDict) -> JsonDict:
        """Run a tool and return its raw structured payload (no MCP wrapping).

        This is the canonical dispatch used by both the MCP surface and the
        per-provider adapters. Raises on unknown tool or handler error.
        """
        tool = self._tools.get(tool_name)
        if tool is None:
            raise ValueError(f"Unknown tool: {tool_name}")
        return tool(arguments)

    def call_tool(self, tool_name: str, arguments: JsonDict) -> JsonDict:
        try:
            payload = self.invoke(tool_name, arguments)
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

    def _call_validate_project(self, arguments: JsonDict) -> JsonDict:
        return validate_project(
            system_root=self.system_root,
            project=_required_string(arguments, "project"),
        )

    def _call_list_project_types(self, arguments: JsonDict) -> JsonDict:  # noqa: ARG002
        return {"project_types": list_project_types(self.system_root)}

    def _call_run_workflow(self, arguments: JsonDict) -> JsonDict:
        engine = WorkflowEngine(self)
        definition = _as_dict(arguments.get("definition", {}), "definition")
        return engine.run(definition)

    def _call_get_workflow_status(self, arguments: JsonDict) -> JsonDict:
        runtime_root = _optional_path(arguments, "runtime_root") or (self.system_root / "runtime")
        project = _required_string(arguments, "project")
        task_slug = _required_string(arguments, "task_slug")
        status_path = runtime_root / "task-runs" / project / task_slug / "status.json"
        if not status_path.exists():
            return {
                "project": project,
                "task_slug": task_slug,
                "state": "unknown",
                "updated_at": "",
                "history": [],
            }
        import json
        return json.loads(status_path.read_text(encoding="utf-8"))

    def _call_resume_task(self, arguments: JsonDict) -> JsonDict:
        runtime_root = _optional_path(arguments, "runtime_root") or (self.system_root / "runtime")
        project = _required_string(arguments, "project")
        task_slug = _required_string(arguments, "task_slug")
        agent = _optional_string(arguments, "agent")

        ctx = build_resume_context(
            runtime_root=runtime_root,
            project=project,
            task_slug=task_slug,
            system_root=self.system_root,
        )

        # Record that this agent is now resuming the task
        if agent and ctx["can_resume"]:
            update_task_run_state(
                runtime_root=runtime_root,
                project=project,
                task_slug=task_slug,
                state="in_progress",
                agent=agent,
            )
            save_checkpoint(
                runtime_root=runtime_root,
                project=project,
                task_slug=task_slug,
                checkpoint=Checkpoint(
                    agent=agent,
                    step="resume",
                    state="completed",
                    summary=f"Resumed task from {ctx['last_agent']} (last state: {ctx['last_state']})",
                    next_hint=ctx["next_step_hint"],
                ),
            )

        return ctx

    def _call_handoff_task(self, arguments: JsonDict) -> JsonDict:
        runtime_root = _optional_path(arguments, "runtime_root") or (self.system_root / "runtime")
        project = _required_string(arguments, "project")
        task_slug = _required_string(arguments, "task_slug")
        from_agent = _required_string(arguments, "from_agent")
        to_agent = _required_string(arguments, "to_agent")
        note = _optional_string(arguments, "note") or ""

        path = save_checkpoint(
            runtime_root=runtime_root,
            project=project,
            task_slug=task_slug,
            checkpoint=Checkpoint(
                agent=from_agent,
                step="handoff",
                state="completed",
                summary=f"Handed off to {to_agent}: {note}" if note else f"Handed off to {to_agent}",
                next_hint=f"Task handed to {to_agent}. Use resume_task to pick up.",
            ),
        )

        update_task_run_state(
            runtime_root=runtime_root,
            project=project,
            task_slug=task_slug,
            state="handed_off",
            agent=from_agent,
        )

        return {
            "project": project,
            "task_slug": task_slug,
            "from_agent": from_agent,
            "to_agent": to_agent,
            "state": "handed_off",
            "checkpoint_path": str(path),
        }


def _tool_definitions() -> list[JsonDict]:
    """MCP `tools/list` payload, sourced from the canonical registry."""
    return list(TOOL_SPECS)


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
