#!/usr/bin/env python3
"""Per-provider tool adapters.

Each adapter is a thin translator between Maestro's canonical tool registry and
one provider's native function-calling format. The MCP surface (Phase 1) plus
these adapters (Phase 2) let the same six tools be exposed to any model without
business logic leaking into the core.

`get_adapter("deepseek")` returns the OpenAI adapter (DeepSeek is
OpenAI-compatible).
"""
from __future__ import annotations

from .anthropic import AnthropicAdapter
from .base import Adapter
from .gemini import GeminiAdapter
from .openai import OpenAIAdapter

# Provider id -> adapter class. Aliases share an implementation.
_ADAPTERS: dict[str, type[Adapter]] = {
    "openai": OpenAIAdapter,
    "deepseek": OpenAIAdapter,
    "anthropic": AnthropicAdapter,
    "claude": AnthropicAdapter,
    "gemini": GeminiAdapter,
}

KNOWN_PROVIDERS = sorted(_ADAPTERS)


def get_adapter(provider: str) -> Adapter:
    """Return an adapter instance for a provider id, or raise ValueError."""
    try:
        return _ADAPTERS[provider]()
    except KeyError:
        raise ValueError(
            f"Unknown provider: {provider!r}. Known: {', '.join(KNOWN_PROVIDERS)}"
        ) from None


__all__ = ["Adapter", "get_adapter", "KNOWN_PROVIDERS"]
