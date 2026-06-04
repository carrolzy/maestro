#!/usr/bin/env python3
"""Provider tool CLI — emit native tool declarations and dispatch tool calls.

The model-agnostic adapter surface for Phase 2. Two modes:

  --list
      Print the provider-native tool declarations (copy them into your model
      wiring: OpenAI/DeepSeek `tools`, Anthropic `tools`, Gemini
      `function_declarations`).

  --call NAME --arguments '<json>'
      Dispatch a tool through the same canonical path the MCP server uses
      (`AiEfficiencyMcpServer.invoke`) and print the raw structured payload.
      This demonstrates the full request -> dispatch -> response contract.

No network calls: adapters only build request payloads and parse response shapes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from adapters import KNOWN_PROVIDERS, get_adapter
from ai_efficiency_mcp_server import AiEfficiencyMcpServer


def main(argv: list[str] | None = None, system_root: Path | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Emit provider-native tool declarations or dispatch a tool call."
    )
    parser.add_argument("--provider", required=True, choices=KNOWN_PROVIDERS)
    parser.add_argument("--list", action="store_true", help="Print native tool declarations.")
    parser.add_argument("--call", default=None, help="Tool name to dispatch.")
    parser.add_argument("--arguments", default="{}", help="JSON object of tool arguments.")
    parser.add_argument("--system-root", default=None)
    parser.add_argument("--vault-root", default=None)
    parser.add_argument("--skills-dest-root", default=None)
    args = parser.parse_args(argv)

    adapter = get_adapter(args.provider)

    if args.list and not args.call:
        print(json.dumps(adapter.tool_declarations(), ensure_ascii=False, indent=2))
        return 0

    if args.call:
        resolved_root = (
            Path(args.system_root) if args.system_root
            else (system_root or Path(__file__).resolve().parent.parent)
        )
        server = AiEfficiencyMcpServer(
            system_root=resolved_root,
            vault_root=Path(args.vault_root) if args.vault_root else None,
            skills_dest_root=Path(args.skills_dest_root) if args.skills_dest_root else None,
        )
        arguments: Any = json.loads(args.arguments)
        if not isinstance(arguments, dict):
            parser.error("--arguments must be a JSON object")
        payload = server.invoke(args.call, arguments)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    parser.error("provide --list or --call NAME")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
