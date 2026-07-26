from __future__ import annotations

import unittest
import os
from pathlib import Path
from subprocess import run
from tempfile import TemporaryDirectory

from tool_registry import tool_names


ROOT = Path(__file__).resolve().parents[2]


class ReleaseConsistencyTests(unittest.TestCase):
    def test_readmes_advertise_registered_tool_count(self) -> None:
        count = len(tool_names())
        self.assertIn(f"{count} MCP tools", (ROOT / "README.md").read_text(encoding="utf-8"))
        self.assertIn(f"{count} 个 MCP 工具", (ROOT / "README.zh-CN.md").read_text(encoding="utf-8"))

    def test_codex_setup_approves_every_registered_tool(self) -> None:
        script = (ROOT / "bin/setup-codex.sh").read_text(encoding="utf-8")
        for tool_name in tool_names():
            self.assertIn(f"[mcp_servers.maestro.tools.{tool_name}]", script)

    def test_codex_setup_upgrades_existing_mcp_configuration(self) -> None:
        with TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            config_dir = home / ".codex"
            config_dir.mkdir()
            config_path = config_dir / "config.toml"
            config_path.write_text(
                '[mcp_servers.maestro]\ncommand = "python3"\n', encoding="utf-8"
            )

            result = run(
                ["bash", ROOT / "bin/setup-codex.sh"],
                cwd=ROOT,
                env={**os.environ, "HOME": str(home)},
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            config = config_path.read_text(encoding="utf-8")
            for tool_name in tool_names():
                self.assertIn(f"[mcp_servers.maestro.tools.{tool_name}]", config)

    def test_python_launcher_honors_configured_interpreter(self) -> None:
        with TemporaryDirectory() as temp_dir:
            interpreter = Path(temp_dir) / "python-override"
            interpreter.write_text(
                "#!/usr/bin/env bash\n"
                "if [[ \"$1\" == \"-c\" && \"$2\" == *version_info* ]]; then exit 0; fi\n"
                "printf 'override-used\\n'\n",
                encoding="utf-8",
            )
            interpreter.chmod(0o755)
            result = run(
                [ROOT / "bin/python.sh", "-c", "print('launcher-ok')"],
                cwd=ROOT,
                env={**os.environ, "AI_EFF_PYTHON": str(interpreter)},
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "override-used")

    def test_manual_mcp_configuration_uses_the_python_launcher(self) -> None:
        self.assertIn(
            '"command": "<path-to-maestro>/bin/python.sh"',
            (ROOT / "README.md").read_text(encoding="utf-8"),
        )
        self.assertIn(
            '"command": "<maestro目录>/bin/python.sh"',
            (ROOT / "README.zh-CN.md").read_text(encoding="utf-8"),
        )

    def test_python_cli_wrappers_use_the_shared_launcher(self) -> None:
        wrappers = (
            "bootstrap-skills.sh",
            "context-pack.sh",
            "dashboard.sh",
            "doctor-local-skills.sh",
            "gc.sh",
            "install-local-skills.sh",
            "onboard-project.sh",
            "perf-case",
            "provider-tools.sh",
            "register-project.sh",
            "search-memory.sh",
        )
        for wrapper in wrappers:
            script = (ROOT / "bin" / wrapper).read_text(encoding="utf-8")
            self.assertIn('"$ROOT_DIR/bin/python.sh"', script, wrapper)


if __name__ == "__main__":
    unittest.main()
