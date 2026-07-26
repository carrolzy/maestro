#!/usr/bin/env python3
"""Maestro Dashboard API server.

A lightweight HTTP JSON API that wraps `AiEfficiencyMcpServer`. Serves
`tooling/ui/dashboard.html` at `/` and a REST API under `/api/`.

Zero new dependencies — uses stdlib `http.server` only. Consistent with the
project's no-runtime-dependency guarantee for tooling.

Start: `bin/dashboard.sh` (or `python3 tooling/api_server.py --port 8420 --open`)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import traceback
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from ai_efficiency_mcp_server import AiEfficiencyMcpServer
from path_safety import resolve_relative_child
from workflow_engine import WorkflowEngine

JsonDict = dict[str, Any]


class DashboardHandler(SimpleHTTPRequestHandler):
    """HTTP handler that routes /api/* to JSON endpoints and serves static files."""

    server_wrapper: DashboardServer | None = None  # set by the server after init

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        """Log to stderr so test output stays clean."""
        sys.stderr.write(f"[dashboard] {format % args}\n")

    # ── routing ──────────────────────────────────────────────────────

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        params = parse_qs(parsed.query)

        try:
            if path == "/" or path == "/index.html":
                return self._serve_static("ui/dashboard.html", "text/html; charset=utf-8")
            if path.startswith("/api/"):
                return self._route_get(path, params)
            # Fallback: try static
            return self._serve_static(path.lstrip("/"), _guess_mime(path))
        except Exception:
            self._json({"error": traceback.format_exc()}, 500)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        body = self._read_body()
        try:
            if path.startswith("/api/"):
                return self._route_post(path, body)
            self._json({"error": "not found"}, 404)
        except Exception:
            self._json({"error": traceback.format_exc()}, 500)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    # ── GET routes ───────────────────────────────────────────────────

    def _route_get(self, path: str, params: dict[str, list[str]]) -> None:
        w = self._w()

        if path == "/api/health":
            return self._json({"status": "ok", "tools": 10})

        if path == "/api/projects":
            projects = []
            root = w.system_root
            proj_dir = root / "projects"
            if proj_dir.is_dir():
                for d in sorted(proj_dir.iterdir()):
                    if not d.is_dir() or d.name.startswith(".") or d.name == "README.md":
                        continue
                    try:
                        report = _try_validate(root, d.name)
                    except Exception as exc:
                        report = {"valid": False, "issues": [str(exc)]}
                    projects.append({
                        "slug": d.name,
                        "valid": report.get("valid", False),
                        "checks": report.get("checks", {}),
                    })
            return self._json({"projects": projects})

        if path.startswith("/api/projects/"):
            slug = path.split("/api/projects/")[1]
            if not slug:
                return self._json({"error": "missing project slug"}, 400)
            root = w.system_root
            proj_dir = root / "projects" / slug
            if not proj_dir.is_dir():
                return self._json({"error": f"project not found: {slug}"}, 404)
            detail: JsonDict = {"slug": slug, "files": []}
            for f in sorted(proj_dir.iterdir()):
                if f.name.endswith(".md"):
                    detail["files"].append({
                        "name": f.name,
                        "preview": f.read_text(encoding="utf-8")[:500],
                    })
                elif f.name.endswith(".json"):
                    try:
                        detail[f.name.replace(".json", "")] = json.loads(f.read_text(encoding="utf-8"))
                    except (json.JSONDecodeError, OSError):
                        pass
            try:
                detail["validation"] = _try_validate(root, slug)
            except Exception as exc:
                detail["validation"] = {"valid": False, "issues": [str(exc)]}
            return self._json(detail)

        if path == "/api/project-types":
            from project_types import list_project_types
            return self._json({"project_types": list_project_types(system_root=w.system_root)})

        if path == "/api/tools":
            from tool_registry import TOOL_SPECS
            return self._json({"tools": TOOL_SPECS})

        if path == "/api/memory":
            project = params.get("project", [None])[0]
            query = params.get("query", [None])[0]
            try:
                result = w.invoke("search_memory", {
                    "project": project,
                    "query": query or "",
                })
                return self._json(result)
            except Exception as exc:
                return self._json({"error": str(exc)}, 400)

        if path == "/api/memory/patterns":
            patterns = _list_md_files(w.system_root / "memory" / "patterns")
            return self._json({"patterns": patterns})

        if path == "/api/memory/rules":
            rules = _list_md_files(w.system_root / "memory" / "rules")
            return self._json({"rules": rules})

        if path == "/api/workflows/runs":
            runs_dir = w.system_root / "runtime" / "task-runs"
            runs: list[JsonDict] = []
            if runs_dir.is_dir():
                for proj_dir in sorted(runs_dir.iterdir()):
                    if not proj_dir.is_dir():
                        continue
                    for task_dir in sorted(proj_dir.iterdir()):
                        status_path = task_dir / "status.json"
                        if status_path.exists():
                            try:
                                runs.append(json.loads(status_path.read_text(encoding="utf-8")))
                            except (json.JSONDecodeError, OSError):
                                pass
            return self._json({"runs": runs})

        return self._json({"error": f"not found: {path}"}, 404)

    # ── POST routes ──────────────────────────────────────────────────

    def _route_post(self, path: str, body: JsonDict) -> None:
        w = self._w()

        if path == "/api/projects":
            try:
                from onboard_project import onboard_project
                report = onboard_project(
                    system_root=w.system_root,
                    project=body.get("project", ""),
                    summary=body.get("summary", ""),
                    project_type=body.get("project_type"),
                    force=body.get("force", False),
                )
                return self._json(report, 201 if report["valid"] else 200)
            except Exception as exc:
                return self._json({"error": str(exc)}, 400)

        if path.startswith("/api/tools/") and path.endswith("/call"):
            tool_name = path.split("/api/tools/")[1].rsplit("/call", 1)[0]
            if not tool_name:
                return self._json({"error": "missing tool name"}, 400)
            try:
                result = w.invoke(tool_name, body)
                return self._json(result)
            except Exception as exc:
                return self._json({"error": str(exc)}, 400)

        if path == "/api/workflows/run":
            try:
                engine = WorkflowEngine(w)
                result = engine.run(body)
                return self._json(result)
            except Exception as exc:
                return self._json({"error": str(exc)}, 400)

        return self._json({"error": f"not found: {path}"}, 404)

    # ── helpers ──────────────────────────────────────────────────────

    def _w(self) -> AiEfficiencyMcpServer:
        """Return the singleton server wrapper instance."""
        assert self.server_wrapper is not None
        return self.server_wrapper.server

    def _read_body(self) -> JsonDict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, rel_path: str, mime: str) -> None:
        tooling_dir = Path(__file__).resolve().parent
        file_path = resolve_relative_child(tooling_dir, rel_path)
        if not file_path.is_file():
            self._json({"error": "not found"}, 404)
            return
        body = file_path.read_bytes()
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _cors(self) -> None:
        return


def _guess_mime(path: str) -> str:
    if path.endswith(".html"):
        return "text/html; charset=utf-8"
    if path.endswith(".css"):
        return "text/css; charset=utf-8"
    if path.endswith(".js"):
        return "application/javascript; charset=utf-8"
    if path.endswith(".json"):
        return "application/json; charset=utf-8"
    if path.endswith(".png"):
        return "image/png"
    if path.endswith(".svg"):
        return "image/svg+xml"
    return "application/octet-stream"


def _list_md_files(directory: Path) -> list[JsonDict]:
    if not directory.is_dir():
        return []
    results: list[JsonDict] = []
    for f in sorted(directory.glob("*.md")):
        text = f.read_text(encoding="utf-8")
        first_line = text.split("\n", 1)[0].lstrip("#").strip()
        results.append({"name": f.stem, "title": first_line or f.stem, "path": str(f)})
    return results


def _try_validate(root: Path, slug: str) -> JsonDict:
    from validate_project import validate_project
    return validate_project(system_root=root, project=slug)


# ── server wrapper ───────────────────────────────────────────────────


class DashboardServer:
    """Holds the AiEfficiencyMcpServer instance shared across requests."""

    def __init__(self, server: AiEfficiencyMcpServer) -> None:
        self.server = server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start the Maestro dashboard API server.")
    parser.add_argument("--port", type=int, default=8420, help="Port to listen on (default: 8420).")
    parser.add_argument("--system-root", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--open", action="store_true", default=True, help="Open browser on start.")
    parser.add_argument("--no-open", action="store_false", dest="open", help="Don't open browser.")
    args = parser.parse_args(argv)

    system_root = Path(args.system_root)
    mcp_server = AiEfficiencyMcpServer(system_root=system_root)
    wrapper = DashboardServer(mcp_server)

    DashboardHandler.server_wrapper = wrapper

    httpd = HTTPServer(("127.0.0.1", args.port), DashboardHandler)
    url = f"http://localhost:{args.port}"

    print(f"\n🖥   Maestro Dashboard → {url}\n")
    print("   Press Ctrl+C to stop.\n")

    if args.open:
        _open_browser(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.\n")
        httpd.server_close()
    return 0


def _open_browser(url: str) -> None:
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", url], check=False)
        elif sys.platform == "win32":
            subprocess.run(["start", url], shell=True, check=False)
        else:
            subprocess.run(["xdg-open", url], check=False)
    except Exception:
        print(f"   Open {url} in your browser.\n")


if __name__ == "__main__":
    raise SystemExit(main())
