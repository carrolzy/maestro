#!/usr/bin/env python3
"""Structured business card — the machine-readable project descriptor.

Each project lives under `projects/<slug>/`. Its human-friendly markdown twin
is `business-context.md`. The business card (`business-card.json`) sits
alongside it as a validated, machine-consumable descriptor.

This module defines the card's JSON Schema, validates instances, and provides
render/card helpers so onboarding is a single machine-checkable step.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema_mini import validate

JsonDict = dict[str, Any]

# Fields mirror the sections of the canonical `business-context.md` template.
BUSINESS_CARD_SCHEMA: JsonDict = {
    "type": "object",
    "properties": {
        "project": {"type": "string", "description": "kebab-case project slug"},
        "project_type": {"type": "string", "description": "project-type key, e.g. uniapp-mini-program"},
        "one_liner": {"type": "string", "description": "one-sentence project summary"},
        "business_goals": {
            "type": "array",
            "items": {"type": "string"},
            "description": "primary business goals",
        },
        "user_roles": {
            "type": "array",
            "items": {"type": "string"},
            "description": "main user roles",
        },
        "core_business_objects": {
            "type": "array",
            "items": {"type": "string"},
            "description": "main business objects/entities",
        },
        "key_business_flows": {
            "type": "array",
            "items": {"type": "string"},
            "description": "key user or system flows",
        },
        "page_or_module_mapping": {
            "type": "array",
            "items": {"type": "string"},
            "description": "main pages, modules, or surfaces",
        },
        "critical_rules": {
            "type": "array",
            "items": {"type": "string"},
            "description": "most important constraints and boundaries",
        },
        "interface_semantics": {
            "type": "array",
            "items": {"type": "string"},
            "description": "API, payload, or domain semantics",
        },
        "historical_pitfalls": {
            "type": "array",
            "items": {"type": "string"},
            "description": "known failure modes or regressions",
        },
    },
    "required": ["project", "one_liner"],
    "additionalProperties": False,
}

# Mapping from card field keys to `business-context.md` section headings.
_SECTION_HEADINGS: dict[str, str] = {
    "one_liner": "Project in One Sentence",
    "business_goals": "Business Goals",
    "user_roles": "User Roles",
    "core_business_objects": "Core Business Objects",
    "key_business_flows": "Key Business Flows",
    "page_or_module_mapping": "Page or Module Mapping",
    "critical_rules": "Critical Rules and Boundaries",
    "interface_semantics": "Interface Semantics",
    "historical_pitfalls": "Historical Pitfalls",
}


def validate_business_card(card: dict) -> list[str]:
    """Validate a business card dict against BUSINESS_CARD_SCHEMA."""
    return validate(card, BUSINESS_CARD_SCHEMA)


def load_and_validate_card(path: Path) -> tuple[dict, list[str]]:
    """Load a business-card.json and validate it. Returns (dict, errors)."""
    try:
        card = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        return {}, [f"Cannot read business card: {exc}"]
    if not isinstance(card, dict):
        return {}, ["business card root must be an object"]
    return card, validate_business_card(card)


def generate_empty_card(project: str, project_type: str | None = None) -> JsonDict:
    """Return a starter business card with empty arrays."""
    card: JsonDict = {
        "project": project,
        "one_liner": "",
        "business_goals": [],
        "user_roles": [],
        "core_business_objects": [],
        "key_business_flows": [],
        "page_or_module_mapping": [],
        "critical_rules": [],
        "interface_semantics": [],
        "historical_pitfalls": [],
    }
    if project_type:
        card["project_type"] = project_type
    return card


def card_to_markdown(card: JsonDict) -> str:
    """Render a business card dict as `business-context.md` markdown."""
    lines = ["# Business Context", ""]
    for field, heading in _SECTION_HEADINGS.items():
        lines.append(f"## {heading}")
        lines.append("")
        if field == "one_liner":
            lines.append(card.get("one_liner", ""))
        else:
            items = card.get(field, [])
            if not isinstance(items, list):
                items = []
            if items:
                for item in items:
                    lines.append(f"- {item}")
            else:
                lines.append(f"- Fill in the {heading.lower()} for this project.")
        lines.append("")
    return "\n".join(lines)
