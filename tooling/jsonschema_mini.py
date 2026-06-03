#!/usr/bin/env python3
"""A tiny, zero-dependency JSON Schema validator (subset).

Supports the subset Maestro uses to declare MCP tool input/output contracts:
`type` (object/array/string/integer/number/boolean/null, or a list of those),
`required`, `properties`, `items`, `enum`, and `additionalProperties: false`.

`validate(instance, schema)` returns a list of human-readable error strings
(empty list == valid). It is deliberately small and pure-Python so the project
keeps its no-runtime-dependency guarantee.
"""
from __future__ import annotations

from typing import Any

_TYPE_CHECKS = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


def validate(instance: Any, schema: dict, *, path: str = "$") -> list[str]:
    errors: list[str] = []

    expected_type = schema.get("type")
    if expected_type is not None:
        types = expected_type if isinstance(expected_type, list) else [expected_type]
        if not any(_TYPE_CHECKS.get(t, lambda _v: False)(instance) for t in types):
            errors.append(f"{path}: expected type {types}, got {type(instance).__name__}")
            # If the base type is wrong, deeper checks are not meaningful.
            return errors

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} not in enum {schema['enum']}")

    if isinstance(instance, dict):
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: missing required property '{key}'")
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in properties:
                    errors.append(f"{path}: additional property '{key}' is not allowed")
        for key, subschema in properties.items():
            if key in instance:
                errors.extend(validate(instance[key], subschema, path=f"{path}.{key}"))

    if isinstance(instance, list) and "items" in schema:
        for index, item in enumerate(instance):
            errors.extend(validate(item, schema["items"], path=f"{path}[{index}]"))

    return errors


def is_valid(instance: Any, schema: dict) -> bool:
    return not validate(instance, schema)
