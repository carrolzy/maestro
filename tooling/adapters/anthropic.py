#!/usr/bin/env python3
"""Anthropic (Claude API) adapter.

Tool declarations use `{name, description, input_schema}`. Tool calls arrive as
`tool_use` content blocks: `{"type": "tool_use", "name": ..., "input": {...}}`.
"""
from __future__ import annotations

from .base import Adapter, JsonDict, ToolCall


class AnthropicAdapter(Adapter):
    provider = "anthropic"

    def _declare(self, spec: JsonDict) -> JsonDict:
        return {
            "name": spec["name"],
            "description": spec["description"],
            "input_schema": spec["inputSchema"],
        }

    def parse_tool_call(self, raw: JsonDict) -> ToolCall:
        if raw.get("type") not in (None, "tool_use"):
            raise ValueError(f"anthropic tool call has unexpected type: {raw.get('type')!r}")
        name = raw.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("anthropic tool_use block missing name")
        arguments = raw.get("input", {})
        if not isinstance(arguments, dict):
            raise ValueError("anthropic tool_use input must be an object")
        return name, arguments
