#!/usr/bin/env python3
"""Google Gemini adapter.

Gemini groups tools under `function_declarations`, and its `parameters` schema is
an OpenAPI 3.0 *subset* — not full JSON Schema. So this adapter sanitizes
Maestro's canonical `inputSchema`:

  - drop `additionalProperties` (unsupported)
  - rewrite a nullable union `type: ["string", "null"]` into the non-null type
    plus `nullable: true`
  - emit Gemini's uppercase `Type` enum (STRING, OBJECT, ...)

Tool calls arrive as `{"functionCall": {"name": ..., "args": {...}}}`.
"""
from __future__ import annotations

from typing import Any

from .base import Adapter, JsonDict, ToolCall

_TYPE_ENUM = {
    "string": "STRING",
    "number": "NUMBER",
    "integer": "INTEGER",
    "boolean": "BOOLEAN",
    "array": "ARRAY",
    "object": "OBJECT",
}

# OpenAPI-subset keys Gemini understands; everything else is dropped.
_KEEP_KEYS = {"description", "enum", "minimum", "maximum", "format"}


class GeminiAdapter(Adapter):
    provider = "gemini"

    def _declare(self, spec: JsonDict) -> JsonDict:
        return {
            "function_declarations": [
                {
                    "name": spec["name"],
                    "description": spec["description"],
                    "parameters": sanitize_schema(spec["inputSchema"]),
                }
            ]
        }

    def tool_declarations(self) -> list[JsonDict]:
        # Gemini accepts many function_declarations in one tool entry; merge them.
        declarations = [d["function_declarations"][0] for d in (self._declare(s) for s in self._specs())]
        return [{"function_declarations": declarations}]

    def _specs(self) -> list[JsonDict]:
        from tool_registry import TOOL_SPECS

        return TOOL_SPECS

    def parse_tool_call(self, raw: JsonDict) -> ToolCall:
        call = raw.get("functionCall", raw)
        name = call.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("gemini functionCall missing name")
        arguments = call.get("args", {})
        if not isinstance(arguments, dict):
            raise ValueError("gemini functionCall args must be an object")
        return name, arguments


def sanitize_schema(schema: Any) -> Any:
    """Convert a JSON Schema (our subset) into Gemini's OpenAPI subset."""
    if not isinstance(schema, dict):
        return schema

    out: JsonDict = {}

    # type: handle nullable unions and uppercase the enum value.
    if "type" in schema:
        type_value = schema["type"]
        types = type_value if isinstance(type_value, list) else [type_value]
        non_null = [t for t in types if t != "null"]
        if "null" in types:
            out["nullable"] = True
        if non_null:
            out["type"] = _TYPE_ENUM.get(non_null[0], non_null[0].upper())

    for key in _KEEP_KEYS:
        if key in schema:
            out[key] = schema[key]

    if "properties" in schema:
        out["properties"] = {k: sanitize_schema(v) for k, v in schema["properties"].items()}
    if "required" in schema:
        out["required"] = list(schema["required"])
    if "items" in schema:
        out["items"] = sanitize_schema(schema["items"])

    # `additionalProperties` is intentionally dropped (unsupported by Gemini).
    return out
