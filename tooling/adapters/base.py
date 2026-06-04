#!/usr/bin/env python3
"""Adapter base contract.

An adapter is a *pure format translator* between Maestro's canonical tool specs
(`tooling/tool_registry.py`) and one model provider's native function-calling
format. It does two things and nothing else:

  - `tool_declarations()` — build the provider-native tool/function list a caller
    sends to that provider's API.
  - `parse_tool_call(raw)` — turn one provider-native tool-call (as it appears in
    that provider's response) into a canonical `(name, arguments)` pair that can
    be dispatched through `AiEfficiencyMcpServer.invoke`.

No business logic, no network calls, no SDK imports. This keeps "business stays
out of core" and the zero-runtime-dependency guarantee intact.
"""
from __future__ import annotations

from typing import Any

from tool_registry import TOOL_SPECS

JsonDict = dict[str, Any]
ToolCall = tuple[str, JsonDict]


class Adapter:
    """Base adapter. Subclasses override the two translation methods."""

    #: short provider id, e.g. "openai"
    provider: str = ""

    def tool_declarations(self) -> list[JsonDict]:
        """Provider-native tool declarations for every registered tool."""
        return [self._declare(spec) for spec in TOOL_SPECS]

    def _declare(self, spec: JsonDict) -> JsonDict:  # pragma: no cover - abstract
        raise NotImplementedError

    def parse_tool_call(self, raw: JsonDict) -> ToolCall:  # pragma: no cover - abstract
        """Provider-native tool-call -> canonical (name, arguments)."""
        raise NotImplementedError
