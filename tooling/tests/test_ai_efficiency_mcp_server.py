import json
import tempfile
import unittest
from pathlib import Path

from ai_efficiency_mcp_server import AiEfficiencyMcpServer, main, write_jsonl_responses


def _write_project(system_root: Path, project: str, summary: str = "Project summary.") -> None:
    project_dir = system_root / "projects" / project
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "business-context.md").write_text(
        f"# Business Context\n\n## Project in One Sentence\n\n{summary}\n",
        encoding="utf-8",
    )
    (project_dir / "project-override.md").write_text(
        "# Project Override\n\n## Project Terms\n\n- sample-term\n",
        encoding="utf-8",
    )
    (project_dir / "task-context.md").write_text(
        "# Task Context\n\n## Current Task\n\n- sample task\n",
        encoding="utf-8",
    )


def _write_templates(system_root: Path) -> None:
    templates_root = system_root / "templates"
    templates_root.mkdir(parents=True, exist_ok=True)
    (templates_root / "business-context.md").write_text(
        "# Business Context\n\n## Project in One Sentence\n\n## Business Goals\n\n## User Roles\n\n## Core Business Objects\n\n## Key Business Flows\n\n## Page or Module Mapping\n\n## Critical Rules and Boundaries\n\n## Interface Semantics\n\n## Historical Pitfalls\n",
        encoding="utf-8",
    )
    (templates_root / "project-override.md").write_text(
        "# Project Override\n\n## Project Terms\n\n## Module Responsibilities\n\n## Interface or Domain Notes\n\n## Special Components or Utilities\n\n## Release Flow\n\n## Known Incidents and Forbidden Zones\n",
        encoding="utf-8",
    )
    (templates_root / "task-context.md").write_text(
        "# Task Context\n\n## Current Task\n\n## Why This Task Exists\n\n## Business Delta for This Task\n\n## Constraints for This Task\n\n## Verification Focus\n",
        encoding="utf-8",
    )


class AiEfficiencyMcpServerTests(unittest.TestCase):
    def test_initialize_returns_server_info_and_tool_capabilities(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            server = AiEfficiencyMcpServer(system_root=Path(tmp_dir))

            response = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})

            self.assertEqual(response["jsonrpc"], "2.0")
            self.assertEqual(response["id"], 1)
            self.assertEqual(response["result"]["serverInfo"]["name"], "maestro")
            self.assertIn("tools", response["result"]["capabilities"])

    def test_tools_list_exposes_core_system_tools(self) -> None:
        from tool_registry import tool_names

        with tempfile.TemporaryDirectory() as tmp_dir:
            server = AiEfficiencyMcpServer(system_root=Path(tmp_dir))

            response = server.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})

            names = [tool["name"] for tool in response["result"]["tools"]]
            self.assertEqual(names, tool_names())

    def test_tools_call_search_memory_returns_structured_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir)
            _write_project(system_root, "alpha", summary="Alpha project.")
            server = AiEfficiencyMcpServer(system_root=system_root)

            response = server.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "search_memory",
                        "arguments": {"project": "alpha", "query": "alpha"},
                    },
                }
            )

            result = response["result"]
            self.assertEqual(result["structuredContent"]["project_cards"][0]["slug"], "alpha")
            self.assertEqual(result["content"][0]["type"], "text")
            self.assertIn("alpha", result["content"][0]["text"])

    def test_tools_call_update_task_run_state_writes_status_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir)
            runtime_root = system_root / "runtime"
            server = AiEfficiencyMcpServer(system_root=system_root)

            response = server.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {
                        "name": "update_task_run_state",
                        "arguments": {
                            "runtime_root": str(runtime_root),
                            "project": "alpha",
                            "task_slug": "2026-06-02-sample",
                            "state": "packaged",
                        },
                    },
                }
            )

            status_path = runtime_root / "task-runs" / "alpha" / "2026-06-02-sample" / "status.json"
            self.assertTrue(status_path.exists())
            self.assertEqual(response["result"]["structuredContent"]["state"], "packaged")
            self.assertEqual(
                Path(response["result"]["structuredContent"]["path"]).resolve(),
                status_path.resolve(),
            )

    def test_tools_call_register_project_uses_existing_templates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir)
            _write_templates(system_root)
            server = AiEfficiencyMcpServer(system_root=system_root)

            response = server.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 5,
                    "method": "tools/call",
                    "params": {
                        "name": "register_project",
                        "arguments": {
                            "project": "sample-project",
                            "summary": "Sample summary.",
                            "project_type": "node-automation",
                        },
                    },
                }
            )

            self.assertTrue((system_root / "projects" / "sample-project" / "business-context.md").exists())
            self.assertEqual(
                Path(response["result"]["structuredContent"]["project_dir"]).resolve(),
                (system_root / "projects" / "sample-project").resolve(),
            )

    def test_tools_call_build_task_package_creates_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir)
            _write_project(system_root, "alpha", summary="Alpha project.")
            output_root = system_root / "packages"
            server = AiEfficiencyMcpServer(system_root=system_root)

            response = server.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 9,
                    "method": "tools/call",
                    "params": {
                        "name": "build_task_package",
                        "arguments": {
                            "project": "alpha",
                            "requirement": "Build a local MCP layer.",
                            "slug": "mcp-layer",
                            "output_root": str(output_root),
                        },
                    },
                }
            )

            output_dir = Path(response["result"]["structuredContent"]["output_dir"])
            self.assertTrue((output_dir / "package.json").exists())
            self.assertEqual(response["result"]["structuredContent"]["package"]["project"], "alpha")

    def test_tools_call_writeback_and_sync_memory_writes_note_and_case(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            system_root = tmp_root / "system"
            vault_root = tmp_root / "vault"
            _write_project(system_root, "alpha", summary="Alpha project.")
            source_file = tmp_root / "source.md"
            source_file.write_text(
                (
                    "# Request\n\n"
                    "MCP writeback.\n\n"
                    "## Context Used\n\n- test\n\n"
                    "## Implementation\n\n- test\n\n"
                    "## Verification\n\n- test\n\n"
                    "## Risks / Follow-up\n\n- test\n\n"
                    "## File References\n\n- test.md\n"
                ),
                encoding="utf-8",
            )
            server = AiEfficiencyMcpServer(system_root=system_root, vault_root=vault_root)

            response = server.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 10,
                    "method": "tools/call",
                    "params": {
                        "name": "writeback_and_sync_memory",
                        "arguments": {
                            "project": "alpha",
                            "note_path": "project-notes/codex-auto/alpha/2026-06-02-mcp.md",
                            "source_file": str(source_file),
                            "memory_root": str(system_root),
                        },
                    },
                }
            )

            self.assertTrue((vault_root / "project-notes/codex-auto/alpha/2026-06-02-mcp.md").exists())
            self.assertTrue(Path(response["result"]["structuredContent"]["case_path"]).exists())
            self.assertTrue(Path(response["result"]["structuredContent"]["index_path"]).exists())

    def test_tools_call_doctor_local_skills_returns_statuses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir) / "system"
            dest_root = Path(tmp_dir) / "dest"
            skill_dir = system_root / "skills" / "project-intake"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("# intake", encoding="utf-8")
            server = AiEfficiencyMcpServer(system_root=system_root, skills_dest_root=dest_root)

            response = server.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 11,
                    "method": "tools/call",
                    "params": {"name": "doctor_local_skills", "arguments": {}},
                }
            )

            self.assertEqual(response["result"]["structuredContent"]["skills"]["project-intake"]["status"], "missing")

    def test_tools_call_errors_are_reported_as_tool_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            server = AiEfficiencyMcpServer(system_root=Path(tmp_dir))

            response = server.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 6,
                    "method": "tools/call",
                    "params": {"name": "search_memory", "arguments": {"project": "missing"}},
                }
            )

            self.assertTrue(response["result"]["isError"])
            self.assertIn("Unknown project", response["result"]["content"][0]["text"])

    def test_jsonl_stdio_helper_skips_notifications_and_writes_responses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir)
            server = AiEfficiencyMcpServer(system_root=system_root)
            output_path = system_root / "responses.jsonl"

            write_jsonl_responses(
                server=server,
                lines=[
                    json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
                    json.dumps({"jsonrpc": "2.0", "id": 7, "method": "tools/list"}),
                ],
                stdout_path=output_path,
            )

            responses = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(responses), 1)
            self.assertEqual(responses[0]["id"], 7)

    def test_cli_can_process_jsonl_input_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            system_root = Path(tmp_dir)
            input_path = system_root / "input.jsonl"
            output_path = system_root / "output.jsonl"
            input_path.write_text(
                json.dumps({"jsonrpc": "2.0", "id": 8, "method": "tools/list"}) + "\n",
                encoding="utf-8",
            )

            exit_code = main(
                argv=["--system-root", str(system_root), "--input", str(input_path), "--output", str(output_path)]
            )

            self.assertEqual(exit_code, 0)
            response = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(response["id"], 8)
