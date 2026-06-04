#!/usr/bin/env python3
"""OpenAI / DeepSeek adapter.

DeepSeek's API is OpenAI-compatible, so the same adapter serves both. Tool
declarations follow the Chat Completions `tools` shape; tool calls come back in
`message.tool_calls[]` with `function.arguments` as a JSON *string*.
"""
from __future__ import annotations

import json
from typing import Any

from .base import Adapter, JsonDict, ToolCall


class OpenAIAdapter(Adapter):
    provider = "openai"

    def _declare(self, spec: JsonDict) -> JsonDict:
        return {
            "type": "function",
            "function": {
                "name": spec["name"],
                "description": spec["description"],
                "parameters": spec["inputSchema"],
            },
        }

    def parse_tool_call(self, raw: JsonDict) -> ToolCall:
        # Accept either a full tool_call object {"function": {...}} or the inner
        # function object {"name": ..., "arguments": ...} directly.
        function = raw.get("function", raw)
        name = function.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("openai tool call missing function.name")
        arguments = _coerce_arguments(function.get("arguments", {}))
        return name, arguments


def _coerce_arguments(value: Any) -> JsonDict:
    if isinstance(value, dict):
        return value
    if value in (None, ""):
        return {}
    if isinstance(value, str):
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            raise ValueError("openai tool call arguments must decode to an object")
        return parsed
    raise ValueError("openai tool call arguments must be an object or JSON string")
