import tempfile
import unittest
from pathlib import Path

from adapters import KNOWN_PROVIDERS, get_adapter
from adapters.gemini import sanitize_schema
from ai_efficiency_mcp_server import AiEfficiencyMcpServer
from jsonschema_mini import validate
from tool_registry import TOOL_SPECS, get_spec, tool_names

EXPECTED_TOOLS = [
    "search_memory",
    "build_task_package",
    "register_project",
    "update_task_run_state",
    "writeback_and_sync_memory",
    "doctor_local_skills",
    "validate_project",
    "list_project_types",
    "run_workflow",
    "get_workflow_status",
    "resume_task",
    "handoff_task",
    "set_active_task",
]


def _seed_system(root: Path) -> None:
    proj = root / "projects" / "alpha"
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "business-context.md").write_text(
        "# Business Context\n\n## Project in One Sentence\n\nAlpha sample project used by the adapter suite.\n",
        encoding="utf-8",
    )
    (proj / "project-override.md").write_text("# Project Override\n\n## Project Terms\n\n- term\n", encoding="utf-8")
    (proj / "task-context.md").write_text("# Task Context\n\n## Current Task\n\n- task\n", encoding="utf-8")


def _declared_names(provider: str) -> list[str]:
    declarations = get_adapter(provider).tool_declarations()
    if provider == "gemini":
        funcs = declarations[0]["function_declarations"]
        return [f["name"] for f in funcs]
    if provider in ("openai", "deepseek"):
        return [d["function"]["name"] for d in declarations]
    return [d["name"] for d in declarations]  # anthropic / claude


def _native_tool_call(provider: str, name: str, arguments: dict) -> dict:
    import json

    if provider in ("openai", "deepseek"):
        return {"function": {"name": name, "arguments": json.dumps(arguments)}}
    if provider in ("anthropic", "claude"):
        return {"type": "tool_use", "name": name, "input": arguments}
    if provider == "gemini":
        return {"functionCall": {"name": name, "args": arguments}}
    raise AssertionError(provider)


class RegistrySingleSourceTests(unittest.TestCase):
    def test_registry_names_match_expected(self) -> None:
        self.assertEqual(tool_names(), EXPECTED_TOOLS)

    def test_get_spec_round_trips(self) -> None:
        self.assertEqual(get_spec("search_memory")["name"], "search_memory")
        with self.assertRaises(KeyError):
            get_spec("nope")


class DeclarationCoverageTests(unittest.TestCase):
    def test_every_provider_declares_all_tools(self) -> None:
        for provider in KNOWN_PROVIDERS:
            with self.subTest(provider=provider):
                self.assertEqual(_declared_names(provider), EXPECTED_TOOLS)

    def test_openai_declaration_shape(self) -> None:
        decl = get_adapter("openai").tool_declarations()[0]
        self.assertEqual(decl["type"], "function")
        self.assertIn("parameters", decl["function"])

    def test_anthropic_declaration_shape(self) -> None:
        decl = get_adapter("anthropic").tool_declarations()[0]
        self.assertIn("input_schema", decl)
        self.assertNotIn("inputSchema", decl)

    def test_gemini_declaration_shape(self) -> None:
        decl = get_adapter("gemini").tool_declarations()
        self.assertEqual(len(decl), 1)
        self.assertIn("function_declarations", decl[0])
        self.assertEqual(len(decl[0]["function_declarations"]), len(TOOL_SPECS))


class GeminiSanitizerTests(unittest.TestCase):
    def test_drops_additional_properties_recursively(self) -> None:
        for spec in TOOL_SPECS:
            sanitized = sanitize_schema(spec["inputSchema"])
            self.assertNotIn("additionalProperties", sanitized)
            for prop in sanitized.get("properties", {}).values():
                self.assertNotIn("additionalProperties", prop)

    def test_rewrites_nullable_union_to_nullable_flag(self) -> None:
        schema = {"type": ["string", "null"], "description": "x"}
        out = sanitize_schema(schema)
        self.assertEqual(out["type"], "STRING")
        self.assertTrue(out["nullable"])

    def test_uppercases_types(self) -> None:
        out = sanitize_schema({"type": "object", "properties": {"n": {"type": "integer"}}})
        self.assertEqual(out["type"], "OBJECT")
        self.assertEqual(out["properties"]["n"]["type"], "INTEGER")


class RoundTripDispatchTests(unittest.TestCase):
    """Provider-native tool call -> parse -> canonical invoke -> payload that
    validates against the tool's declared outputSchema."""

    def test_search_memory_round_trip_each_provider(self) -> None:
        out_schema = get_spec("search_memory")["outputSchema"]
        for provider in KNOWN_PROVIDERS:
            with self.subTest(provider=provider), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                _seed_system(root)
                server = AiEfficiencyMcpServer(system_root=root)
                adapter = get_adapter(provider)
                raw = _native_tool_call(provider, "search_memory", {"project": "alpha", "query": "alpha"})
                name, args = adapter.parse_tool_call(raw)
                self.assertEqual(name, "search_memory")
                payload = server.invoke(name, args)
                self.assertEqual(validate(payload, out_schema), [])

    def test_register_project_round_trip_write_tool(self) -> None:
        out_schema = get_spec("register_project")["outputSchema"]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_system(root)
            templates = root / "templates"
            templates.mkdir(parents=True, exist_ok=True)
            for n in ("business-context", "project-override", "task-context"):
                (templates / f"{n}.md").write_text(f"# {n}\n\n## Section\n", encoding="utf-8")
            server = AiEfficiencyMcpServer(system_root=root)
            raw = _native_tool_call("anthropic", "register_project", {"project": "beta", "summary": "Beta."})
            name, args = get_adapter("anthropic").parse_tool_call(raw)
            payload = server.invoke(name, args)
            self.assertEqual(validate(payload, out_schema), [])


class ParseErrorTests(unittest.TestCase):
    def test_openai_bad_arguments_string_raises(self) -> None:
        with self.assertRaises(ValueError):
            get_adapter("openai").parse_tool_call({"function": {"name": "x", "arguments": "not-json"}})

    def test_missing_name_raises(self) -> None:
        for provider in ("openai", "anthropic", "gemini"):
            with self.subTest(provider=provider), self.assertRaises(ValueError):
                get_adapter(provider).parse_tool_call(_strip_name(provider))

    def test_unknown_provider_raises(self) -> None:
        with self.assertRaises(ValueError):
            get_adapter("mystery")


def _strip_name(provider: str) -> dict:
    if provider in ("openai", "deepseek"):
        return {"function": {"arguments": "{}"}}
    if provider in ("anthropic", "claude"):
        return {"type": "tool_use", "input": {}}
    return {"functionCall": {"args": {}}}


if __name__ == "__main__":
    unittest.main()
