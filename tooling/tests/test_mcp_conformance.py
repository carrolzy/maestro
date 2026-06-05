import tempfile
import unittest
from pathlib import Path

from ai_efficiency_mcp_server import (
    AiEfficiencyMcpServer,
    SUPPORTED_PROTOCOL_VERSIONS,
    _tool_definitions,
)
from jsonschema_mini import validate

NOTE_BODY = (
    "# Request\n\nConformance note.\n\n"
    "## Context Used\n\n- test\n\n"
    "## Implementation\n\n- test\n\n"
    "## Verification\n\n- test\n\n"
    "## Risks / Follow-up\n\n- test\n\n"
    "## File References\n\n- test.md\n"
)


def _seed_system(root: Path) -> None:
    proj = root / "projects" / "alpha"
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "business-context.md").write_text(
        "# Business Context\n\n## Project in One Sentence\n\nAlpha sample project used by the conformance suite.\n",
        encoding="utf-8",
    )
    (proj / "project-override.md").write_text("# Project Override\n\n## Project Terms\n\n- term\n", encoding="utf-8")
    (proj / "task-context.md").write_text("# Task Context\n\n## Current Task\n\n- task\n", encoding="utf-8")
    templates = root / "templates"
    templates.mkdir(parents=True, exist_ok=True)
    for name in ("business-context", "project-override", "task-context"):
        (templates / f"{name}.md").write_text(f"# {name}\n\n## Section\n", encoding="utf-8")


def _rpc(method: str, request_id: int = 1, params: dict | None = None) -> dict:
    req = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        req["params"] = params
    return req


class McpHandshakeConformanceTests(unittest.TestCase):
    def test_initialize_negotiates_supported_protocol_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            server = AiEfficiencyMcpServer(system_root=Path(tmp))
            requested = SUPPORTED_PROTOCOL_VERSIONS[-1]
            resp = server.handle_request(_rpc("initialize", params={"protocolVersion": requested}))
            self.assertEqual(resp["result"]["protocolVersion"], requested)
            self.assertEqual(resp["result"]["serverInfo"]["name"], "maestro")
            self.assertIn("tools", resp["result"]["capabilities"])

    def test_initialize_falls_back_for_unknown_protocol_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            server = AiEfficiencyMcpServer(system_root=Path(tmp))
            resp = server.handle_request(_rpc("initialize", params={"protocolVersion": "1999-01-01"}))
            self.assertIn(resp["result"]["protocolVersion"], SUPPORTED_PROTOCOL_VERSIONS)

    def test_ping_returns_empty_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            server = AiEfficiencyMcpServer(system_root=Path(tmp))
            resp = server.handle_request(_rpc("ping", request_id=2))
            self.assertEqual(resp["result"], {})

    def test_unknown_method_returns_method_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            server = AiEfficiencyMcpServer(system_root=Path(tmp))
            resp = server.handle_request(_rpc("does/not/exist", request_id=3))
            self.assertEqual(resp["error"]["code"], -32601)

    def test_notifications_without_id_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            server = AiEfficiencyMcpServer(system_root=Path(tmp))
            self.assertIsNone(server.handle_request({"jsonrpc": "2.0", "method": "notifications/initialized"}))


class McpToolDiscoveryConformanceTests(unittest.TestCase):
    def test_tools_list_names_match_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            server = AiEfficiencyMcpServer(system_root=Path(tmp))
            resp = server.handle_request(_rpc("tools/list"))
            from tool_registry import tool_names
            names = [tool["name"] for tool in resp["result"]["tools"]]
            self.assertEqual(names, tool_names())

    def test_every_tool_declares_well_formed_input_and_output_schema(self) -> None:
        for tool in _tool_definitions():
            with self.subTest(tool=tool["name"]):
                self.assertTrue(tool.get("title"))
                self.assertTrue(tool.get("description"))
                input_schema = tool["inputSchema"]
                self.assertEqual(input_schema["type"], "object")
                self.assertFalse(input_schema["additionalProperties"])
                self.assertIn("properties", input_schema)
                output_schema = tool["outputSchema"]
                self.assertEqual(output_schema["type"], "object")


class McpToolContractConformanceTests(unittest.TestCase):
    """Call each tool with valid args and validate its structuredContent
    against the outputSchema it advertises — the cross-client contract."""

    def test_each_tool_output_matches_declared_output_schema(self) -> None:
        schemas = {tool["name"]: tool["outputSchema"] for tool in _tool_definitions()}
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            system_root = root / "system"
            system_root.mkdir()
            _seed_system(system_root)
            vault_root = root / "vault"
            source_file = root / "note.md"
            source_file.write_text(NOTE_BODY, encoding="utf-8")

            server = AiEfficiencyMcpServer(system_root=system_root, vault_root=vault_root)

            valid_args = {
                "search_memory": {"project": "alpha", "query": "alpha"},
                "build_task_package": {
                    "project": "alpha",
                    "requirement": "alpha consistency requirement",
                    "output_root": str(root / "packages"),
                },
                "register_project": {"project": "beta", "summary": "Beta summary."},
                "update_task_run_state": {
                    "runtime_root": str(root / "runtime"),
                    "project": "alpha",
                    "task_slug": "2026-01-01-conformance",
                    "state": "packaged",
                },
                "writeback_and_sync_memory": {
                    "note_path": "project-notes/alpha/2026-01-01-conformance.md",
                    "project": "alpha",
                    "source_file": str(source_file),
                    "memory_root": str(root / "memory-root"),
                },
                "doctor_local_skills": {"dest_root": str(root / "skills-dest")},
                "validate_project": {"project": "alpha"},
                "list_project_types": {},
                "run_workflow": {
                    "definition": {
                        "project": "alpha",
                        "task_slug": "conformance-test",
                        "steps": [
                            {"id": "s1", "tool": "search_memory", "args": {"project": "alpha", "query": "alpha"}},
                            {"id": "s2", "tool": "validate_project", "args": {"project": "alpha"}},
                        ],
                    }
                },
                "get_workflow_status": {"project": "alpha", "task_slug": "conformance-test"},
                "resume_task": {"project": "alpha", "task_slug": "conformance-test", "agent": "test-runner"},
                "handoff_task": {"project": "alpha", "task_slug": "conformance-test", "from_agent": "codex", "to_agent": "claude", "note": "Network failure — please continue."},
                "set_active_task": {"project": "alpha", "task_slug": "conformance-test", "agent": "test-runner"},
                "snapshot_task": {
                    "project": "alpha", "task_slug": "conformance-test", "agent": "test-runner",
                    "repo_root": str(root),
                },
            }

            from tool_registry import tool_names
            for name in tool_names():
                with self.subTest(tool=name):
                    result = server.call_tool(name, valid_args[name])
                    self.assertFalse(result["isError"], msg=result["content"])
                    errors = validate(result["structuredContent"], schemas[name])
                    self.assertEqual(errors, [], msg=f"{name} output violates its schema: {errors}")

    def test_unknown_tool_is_reported_as_tool_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            server = AiEfficiencyMcpServer(system_root=Path(tmp))
            result = server.call_tool("no_such_tool", {})
            self.assertTrue(result["isError"])
            self.assertIn("Unknown tool", result["content"][0]["text"])

    def test_tool_exception_is_reported_as_tool_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            server = AiEfficiencyMcpServer(system_root=Path(tmp))
            result = server.call_tool("search_memory", {"project": "missing-project"})
            self.assertTrue(result["isError"])
            self.assertIn("Unknown project", result["content"][0]["text"])
