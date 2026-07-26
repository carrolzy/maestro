#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

from active_task import get_active_task, set_active_task
from artifact_gc import archive as gc_archive, clean as gc_clean, restore as gc_restore, scan as gc_scan
from checkpoint import Checkpoint, append_to_session_checkpoint, build_resume_context, save_checkpoint
from code_search import glob_files, grep_code, read_file_slice, repo_outline
from git_snapshot import git_changed_files
from jsonschema_mini import validate
from local_skills_doctor import assess_local_skills
from project_types import list_project_types
from register_project import register_project
from search_memory import search_memory
from task_package_builder import build_task_package
from temp_registry import refresh_task_temp_files, register_temp_file
from test_doctor import audit_tests
from tool_registry import TOOL_SPECS, get_spec
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
            "set_active_task": self._call_set_active_task,
            "snapshot_task": self._call_snapshot_task,
            "gc_artifacts": self._call_gc_artifacts,
            "register_temp_file": self._call_register_temp_file,
            "grep_code": self._call_grep_code,
            "glob_files": self._call_glob_files,
            "read_file_slice": self._call_read_file_slice,
            "repo_outline": self._call_repo_outline,
            "audit_tests": self._call_audit_tests,
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
        spec = get_spec(tool_name)
        input_errors = validate(arguments, spec["inputSchema"])
        if input_errors:
            raise ValueError("Invalid tool input: " + "; ".join(input_errors))
        payload = tool(arguments)
        output_errors = validate(payload, spec["outputSchema"])
        if output_errors:
            raise ValueError("Tool output violates schema: " + "; ".join(output_errors))
        return payload

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
            include_archived=bool(arguments.get("include_archived")),
            target=_optional_string(arguments, "target") or "knowledge",
            repo_root=_optional_string(arguments, "repo_root"),
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
        project = _required_string(arguments, "project")
        task_slug = _required_string(arguments, "task_slug")
        state = _required_string(arguments, "state")
        output_path = update_task_run_state(
            runtime_root=runtime_root,
            project=project,
            task_slug=task_slug,
            state=state,
        )
        # Closing a task restarts the TTL clock on its registered temp files —
        # the post-release verification window runs from the close date.
        if state == "closed":
            refresh_task_temp_files(runtime_root, project=project, task_slug=task_slug)
        return {
            "path": str(output_path),
            "project": project,
            "task_slug": task_slug,
            "state": state,
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
            status: JsonDict = {
                "project": project,
                "task_slug": task_slug,
                "state": "unknown",
                "updated_at": "",
                "history": [],
            }
        else:
            status = json.loads(status_path.read_text(encoding="utf-8"))
        workflow_path = status_path.with_name("workflow.json")
        if workflow_path.exists():
            status["workflow"] = json.loads(workflow_path.read_text(encoding="utf-8"))
        return status

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

        # Snapshot all changed files before sealing the handoff.
        self._snapshot_now(runtime_root, project, task_slug, from_agent, summary=f"Auto-snapshot before handoff to {to_agent}")

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

    def _call_set_active_task(self, arguments: JsonDict) -> JsonDict:
        runtime_root = _optional_path(arguments, "runtime_root") or (self.system_root / "runtime")
        project = _required_string(arguments, "project")
        task_slug = _required_string(arguments, "task_slug")
        agent = _required_string(arguments, "agent")

        # Snapshot the previous task (if any) before switching — captures its
        # changes even if the agent forgot to hand off.
        prev = get_active_task(runtime_root)
        if prev and (prev["project"] != project or prev["task_slug"] != task_slug):
            self._snapshot_now(
                runtime_root, prev["project"], prev["task_slug"],
                prev.get("agent", "unknown"),
                summary=f"Auto-snapshot before switching to {project}/{task_slug}",
            )

        pointer_path = set_active_task(runtime_root, project, task_slug, agent)
        # Provision the task's scratch area — throwaway scripts/probes belong
        # here, not in the business repo.
        scratch_dir = runtime_root / "scratch" / project / task_slug
        scratch_dir.mkdir(parents=True, exist_ok=True)
        return {
            "project": project,
            "task_slug": task_slug,
            "agent": agent,
            "pointer_path": str(pointer_path),
            "scratch_dir": str(scratch_dir),
            "previous_task_snapshotted": bool(prev and (prev["project"] != project or prev["task_slug"] != task_slug)),
        }

    def _snapshot_now(
        self, runtime_root: Path, project: str, task_slug: str, agent: str,
        *, summary: str = "",
    ) -> list[str]:
        """Run git-changed-files on the system root and record an auto-edit checkpoint.

        Returns the list of changed file paths. A no-op if system_root is not a
        git repo (returns empty list, nothing recorded).
        """
        files = git_changed_files(self.system_root)
        if not files:
            return []
        import os as _os
        session_id = _os.environ.get("CODEX_SESSION_ID", "auto")
        for f in files:
            append_to_session_checkpoint(
                runtime_root, project, task_slug,
                agent=agent, session_id=session_id, file_modified=f,
            )
        return files

    def _call_snapshot_task(self, arguments: JsonDict) -> JsonDict:
        runtime_root = _optional_path(arguments, "runtime_root") or (self.system_root / "runtime")
        project = _optional_string(arguments, "project")
        task_slug = _optional_string(arguments, "task_slug")
        agent = _optional_string(arguments, "agent")

        # Resolve from active-task pointer when omitted.
        if not project or not task_slug:
            active = get_active_task(runtime_root)
            if active:
                project = project or active["project"]
                task_slug = task_slug or active["task_slug"]
                agent = agent or active.get("agent", "unknown")
            else:
                raise ValueError(
                    "No project/task_slug given and no active-task pointer is set. "
                    "Call set_active_task first, or pass project & task_slug explicitly."
                )
        if not agent:
            agent = "unknown"

        repo_root = _optional_path(arguments, "repo_root") or self.system_root
        summary = _optional_string(arguments, "summary") or ""

        # Use _snapshot_now for the fast path when repo_root == system_root.
        if repo_root == self.system_root:
            files = self._snapshot_now(runtime_root, project, task_slug, agent, summary=summary)
        else:
            files = git_changed_files(repo_root)
            if files:
                import os as _os2
                sid = _os2.environ.get("CODEX_SESSION_ID", "snapshot")
                for f in files:
                    append_to_session_checkpoint(
                        runtime_root, project, task_slug,
                        agent=agent, session_id=sid, file_modified=f,
                    )

        checkpoint_path: Path | None = None
        if not files:
            checkpoint_path = save_checkpoint(
                runtime_root, project, task_slug,
                checkpoint=Checkpoint(
                    agent=agent, step="snapshot", state="completed",
                    summary=summary or "snapshot: no changes",
                    files_modified=[],
                ),
            )

        return {
            "project": project,
            "task_slug": task_slug,
            "files_modified": files,
            "recorded": True,
            "checkpoint_path": str(checkpoint_path) if checkpoint_path else None,
        }

    def _call_gc_artifacts(self, arguments: JsonDict) -> JsonDict:
        command = _optional_string(arguments, "command") or "scan"
        if command == "scan":
            result = gc_scan(self.system_root)
        elif command == "archive":
            result = gc_archive(self.system_root)
        elif command == "clean":
            result = gc_clean(self.system_root, apply=bool(arguments.get("apply")))
        elif command == "restore":
            archive_path = _required_string(arguments, "archive_path")
            result = gc_restore(self.system_root, archive_path=archive_path)
        else:
            raise ValueError(f"Unknown gc command: {command}")
        return {"command": command, "result": result}

    def _call_register_temp_file(self, arguments: JsonDict) -> JsonDict:
        runtime_root = self.system_root / "runtime"
        ttl = arguments.get("ttl_days")
        return register_temp_file(
            runtime_root,
            file_path=_required_string(arguments, "file_path"),
            project=_required_string(arguments, "project"),
            task_slug=_required_string(arguments, "task_slug"),
            ttl_days=int(ttl) if ttl else 30,
            reason=_optional_string(arguments, "reason") or "",
        )

    def _call_grep_code(self, arguments: JsonDict) -> JsonDict:
        return grep_code(
            repo_root=_required_string(arguments, "repo_root"),
            pattern=_required_string(arguments, "pattern"),
            glob=_optional_string(arguments, "glob"),
            case_insensitive=bool(arguments.get("case_insensitive")),
            fixed_string=bool(arguments.get("fixed_string")),
            max_matches=_optional_int(arguments, "max_matches", 50),
            context_lines=_optional_int(arguments, "context_lines", 2),
        )

    def _call_glob_files(self, arguments: JsonDict) -> JsonDict:
        return glob_files(
            repo_root=_required_string(arguments, "repo_root"),
            pattern=_required_string(arguments, "pattern"),
            max_results=_optional_int(arguments, "max_results", 100),
        )

    def _call_read_file_slice(self, arguments: JsonDict) -> JsonDict:
        return read_file_slice(
            repo_root=_required_string(arguments, "repo_root"),
            file_path=_required_string(arguments, "file_path"),
            start_line=_optional_int(arguments, "start_line", 1),
            max_lines=_optional_int(arguments, "max_lines", 200),
        )

    def _call_repo_outline(self, arguments: JsonDict) -> JsonDict:
        return repo_outline(
            repo_root=_required_string(arguments, "repo_root"),
            path=_optional_string(arguments, "path"),
            max_depth=_optional_int(arguments, "max_depth", 3),
            max_entries=_optional_int(arguments, "max_entries", 200),
        )

    def _call_audit_tests(self, arguments: JsonDict) -> JsonDict:
        return audit_tests(
            repo_root=_required_string(arguments, "repo_root"),
            stale_threshold=_optional_int(arguments, "stale_threshold", 5),
        )


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


def _serve_stdio(server: "AiEfficiencyMcpServer") -> None:
    """Live MCP stdio loop: answer each JSON-RPC request as it arrives.

    Reads one line at a time and flushes each response immediately. A long-lived
    stdio connection never sends EOF, so the batch path (which blocks until EOF)
    would hang and the client's startup handshake would time out.
    """
    while True:
        line = sys.stdin.readline()
        if not line:  # EOF — client closed the connection
            break
        stripped = line.strip()
        if not stripped:
            continue
        try:
            request = json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            continue
        response = server.handle_request(request)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


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

    # File replay (tests): batch-read the whole input, then write all responses.
    if args.input:
        input_lines = Path(args.input).read_text(encoding="utf-8").splitlines()
        output_path = Path(args.output) if args.output else None
        write_jsonl_responses(server=server, lines=input_lines, stdout_path=output_path)
        return 0

    # Live MCP stdio connection (Codex/Claude): stream request-by-request.
    _serve_stdio(server)
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
