#!/usr/bin/env python3
"""Playbook schema and validator.

A `playbook.json` lets a project inject domain-specific module hints, risk
flags, and verification checks without hard-coding business logic. This module
defines its formal JSON Schema and validates instances against it using the
zero-dependency `jsonschema_mini` validator.

The schema mirrors the shape already established by
`projects/example-wxapp/playbook.json`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema_mini import validate

JsonDict = dict[str, Any]

PLAYBOOK_SCHEMA: JsonDict = {
    "type": "object",
    "properties": {
        "project_type": {"type": "string"},
        "guidance": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "suspected_modules": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "module_label": {"type": "string"},
                                "project_files": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "evidence": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                            "required": ["module_label", "project_files", "evidence"],
                            "additionalProperties": False,
                        },
                    },
                    "risk_flags": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "reason": {"type": "string"},
                            },
                            "required": ["name", "reason"],
                            "additionalProperties": False,
                        },
                    },
                    "recommended_checks": {
                        "type": "object",
                        "properties": {
                            "verification_focus": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "manual_checks": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "code_checks": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "additionalProperties": False,
                    },
                },
                "required": ["keywords"],
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}


def validate_playbook(playbook: dict) -> list[str]:
    """Validate a playbook dict against PLAYBOOK_SCHEMA. Returns errors (empty=ok)."""
    return validate(playbook, PLAYBOOK_SCHEMA)


def load_and_validate_playbook(path: Path) -> tuple[dict, list[str]]:
    """Load a playbook.json and validate it. Returns (dict, errors)."""
    try:
        playbook = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        return {}, [f"Cannot read playbook: {exc}"]
    if not isinstance(playbook, dict):
        return {}, ["playbook root must be an object"]
    return playbook, validate_playbook(playbook)
