"""Tests for the dashboard API server.

Starts the server on a random port in a background thread, then drives it
via http.client (stdlib). Each test class seeds its own temp directory so
project state is isolated.
"""
from __future__ import annotations

import json
import socket
import tempfile
import threading
import time
import unittest
from http.client import HTTPConnection
from http.server import HTTPServer
from pathlib import Path

from ai_efficiency_mcp_server import AiEfficiencyMcpServer
from api_server import DashboardHandler, DashboardServer


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _seed_system(root: Path) -> None:
    proj = root / "projects" / "alpha"
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "business-context.md").write_text(
        "# Business Context\n\n## Project in One Sentence\n\nAlpha project for API tests.\n",
        encoding="utf-8",
    )
    (proj / "project-override.md").write_text("# Project Override\n\n## Project Terms\n\n- test\n", encoding="utf-8")
    (proj / "task-context.md").write_text("# Task Context\n\n## Current Task\n\n- test\n", encoding="utf-8")
    templates = root / "templates"
    templates.mkdir(parents=True, exist_ok=True)
    for n in ("business-context", "project-override", "task-context", "project-baseline"):
        (templates / f"{n}.md").write_text(f"# {n}\n\n## Section\n\nplaceholder\n", encoding="utf-8")


class ApiServerTestBase(unittest.TestCase):
    """Base class that starts a dashboard server on a temp directory."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        _seed_system(cls.root)

        mcp = AiEfficiencyMcpServer(system_root=cls.root)
        cls.wrapper = DashboardServer(mcp)
        DashboardHandler.server_wrapper = cls.wrapper

        cls.port = _free_port()
        cls.httpd = HTTPServer(("127.0.0.1", cls.port), DashboardHandler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.05)  # let it bind

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        cls.thread.join(timeout=2)
        cls.tmp.cleanup()

    def _get(self, path: str) -> tuple[int, dict]:
        conn = HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request("GET", path)
            resp = conn.getresponse()
            body = json.loads(resp.read().decode("utf-8"))
            return resp.status, body
        finally:
            conn.close()

    def _post(self, path: str, data: dict | None = None) -> tuple[int, dict]:
        body_bytes = json.dumps(data or {}).encode("utf-8")
        conn = HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request("POST", path, body=body_bytes, headers={"Content-Type": "application/json"})
            resp = conn.getresponse()
            body = json.loads(resp.read().decode("utf-8"))
            return resp.status, body
        finally:
            conn.close()


class HealthTests(ApiServerTestBase):
    def test_health(self) -> None:
        status, body = self._get("/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "ok")


class ProjectsTests(ApiServerTestBase):
    def test_list_projects(self) -> None:
        status, body = self._get("/api/projects")
        self.assertEqual(status, 200)
        slugs = [p["slug"] for p in body["projects"]]
        self.assertIn("alpha", slugs)

    def test_project_detail(self) -> None:
        status, body = self._get("/api/projects/alpha")
        self.assertEqual(status, 200)
        self.assertIn("files", body)
        self.assertIn("validation", body)

    def test_project_not_found(self) -> None:
        status, body = self._get("/api/projects/ghost")
        self.assertEqual(status, 404)

    def test_onboard_new_project(self) -> None:
        status, body = self._post("/api/projects", {
            "project": "beta",
            "summary": "Beta project.",
            "project_type": None,
        })
        self.assertIn(status, (200, 201))
        self.assertEqual(body["project"], "beta")
        self.assertTrue(body["valid"])
        self.assertTrue((self.root / "projects" / "beta" / "spec" / "project-baseline.md").exists())


class ToolsTests(ApiServerTestBase):
    def test_list_tools(self) -> None:
        status, body = self._get("/api/tools")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(body["tools"]), 8)

    def test_invoke_tool(self) -> None:
        status, body = self._post("/api/tools/search_memory/call", {
            "project": "alpha",
            "query": "alpha",
        })
        self.assertEqual(status, 200)
        self.assertIn("project_cards", body)

    def test_invoke_bad_tool(self) -> None:
        status, body = self._post("/api/tools/nosuchtool/call", {})
        self.assertEqual(status, 400)
        self.assertIn("error", body)


class WorkflowTests(ApiServerTestBase):
    def test_run_workflow(self) -> None:
        status, body = self._post("/api/workflows/run", {
            "project": "alpha",
            "task_slug": "api-test-wf",
            "steps": [
                {"id": "s1", "tool": "search_memory", "args": {"project": "alpha", "query": "alpha"}},
                {"id": "s2", "tool": "validate_project", "args": {"project": "alpha"}},
            ],
        })
        self.assertEqual(status, 200)
        self.assertEqual(body["aggregate_state"], "completed")
        self.assertEqual(len(body["steps"]), 2)

    def test_bad_workflow_returns_error(self) -> None:
        status, body = self._post("/api/workflows/run", {
            "steps": [{"id": "a"}, {"id": "a"}],  # duplicate ids
        })
        self.assertEqual(status, 400)
        self.assertIn("error", body)


class ProjectTypeTests(ApiServerTestBase):
    def test_list_project_types(self) -> None:
        status, body = self._get("/api/project-types")
        self.assertEqual(status, 200)
        self.assertIn("project_types", body)


class MemoryTests(ApiServerTestBase):
    def test_search_memory(self) -> None:
        status, body = self._get("/api/memory?project=alpha&query=alpha")
        self.assertEqual(status, 200)
        self.assertIn("project_cards", body)

    def test_list_patterns(self) -> None:
        status, body = self._get("/api/memory/patterns")
        self.assertEqual(status, 200)
        self.assertIn("patterns", body)

    def test_list_rules(self) -> None:
        status, body = self._get("/api/memory/rules")
        self.assertEqual(status, 200)
        self.assertIn("rules", body)


class StaticFileTests(ApiServerTestBase):
    def test_dashboard_html_served(self) -> None:
        conn = HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request("GET", "/")
            resp = conn.getresponse()
            body = resp.read().decode("utf-8")
            self.assertEqual(resp.status, 200)
            self.assertIn("Maestro Dashboard", body)
        finally:
            conn.close()

    def test_options_does_not_grant_cross_origin_access(self) -> None:
        conn = HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request("OPTIONS", "/api/health", headers={"Origin": "https://evil.example"})
            resp = conn.getresponse()
            self.assertEqual(resp.status, 204)
            self.assertIsNone(resp.getheader("Access-Control-Allow-Origin"))
        finally:
            conn.close()


class UnknownRouteTests(ApiServerTestBase):
    def test_unknown_api_route(self) -> None:
        status, body = self._get("/api/nope")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
