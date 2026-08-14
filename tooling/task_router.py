"""Deterministic task routing policy loader and tier helpers."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


TIER_ORDER = ("L0", "L1", "L2", "L3")
CONFIDENCE_LEVELS = ("low", "medium", "high")
_REQUIRED_POLICY_FIELDS = (
    "schema_version",
    "tier_order",
    "tiers",
    "defaults",
    "confidence_rules",
    "routing_constraints",
    "global_risks",
)


def tier_rank(tier: str) -> int:
    """Return the stable governance rank for a supported tier."""
    try:
        return TIER_ORDER.index(tier)
    except ValueError as exc:
        raise ValueError(f"Unsupported routing tier: {tier}") from exc


def load_routing_policy(path: Path) -> dict[str, Any]:
    """Load a task-routing policy JSON document."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read routing policy: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Routing policy root must be an object")
    missing = [field for field in _REQUIRED_POLICY_FIELDS if field not in payload]
    if missing:
        raise ValueError(f"Routing policy missing required field: {', '.join(missing)}")
    _validate_policy(payload)
    return payload


def _validate_policy(policy: dict[str, Any]) -> None:
    if policy["schema_version"] != 1:
        raise ValueError("Unsupported routing policy schema_version")
    if policy["tier_order"] != list(TIER_ORDER):
        raise ValueError(f"tier_order must be exactly {list(TIER_ORDER)}")

    tiers = _require_object(policy, "tiers")
    if set(tiers) != set(TIER_ORDER):
        raise ValueError("tiers must define exactly L0, L1, L2, and L3")
    for tier in TIER_ORDER:
        definition = _require_object(tiers, tier, label=f"tiers.{tier}")
        if not isinstance(definition.get("label"), str) or not definition["label"].strip():
            raise ValueError(f"tiers.{tier}.label must be a non-empty string")
        _require_string_list(definition, "required_steps", label=f"tiers.{tier}.required_steps")
        _require_string_list(definition, "skipped_steps", label=f"tiers.{tier}.skipped_steps")

    defaults = _require_object(policy, "defaults")
    required_defaults = (
        "unconfigured_project_min_tier",
        "uncertainty_min_tier",
        "missing_verification_min_tier",
        "target_overlap_min_tier",
    )
    for key in required_defaults:
        _require_tier(defaults.get(key), f"defaults.{key}")

    confidence_rules = _require_object(policy, "confidence_rules")
    automatic = confidence_rules.get("automatic_fast_path")
    if automatic not in CONFIDENCE_LEVELS:
        raise ValueError(f"confidence_rules.automatic_fast_path must be one of {list(CONFIDENCE_LEVELS)}")
    confirmation = _require_string_list(
        confidence_rules,
        "confirmation_required",
        label="confidence_rules.confirmation_required",
    )
    invalid_confidence = [value for value in confirmation if value not in CONFIDENCE_LEVELS]
    if invalid_confidence:
        raise ValueError(f"confidence_rules.confirmation_required contains unsupported values: {invalid_confidence}")

    constraints = _require_object(policy, "routing_constraints")
    for key in ("monotonic_upgrade_only", "policy_layers_can_only_raise"):
        if not isinstance(constraints.get(key), bool):
            raise ValueError(f"routing_constraints.{key} must be a boolean")

    risks = _require_object(policy, "global_risks")
    if not risks:
        raise ValueError("global_risks must not be empty")
    for name, raw_definition in risks.items():
        definition = raw_definition if isinstance(raw_definition, dict) else None
        if definition is None:
            raise ValueError(f"global_risks.{name} must be an object")
        _require_tier(definition.get("min_tier"), f"global_risks.{name}.min_tier")
        if not isinstance(definition.get("hard_veto_l0"), bool):
            raise ValueError(f"global_risks.{name}.hard_veto_l0 must be a boolean")


def _require_object(container: dict[str, Any], key: str, *, label: str | None = None) -> dict[str, Any]:
    value = container.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{label or key} must be an object")
    return value


def _require_string_list(container: dict[str, Any], key: str, *, label: str) -> list[str]:
    value = container.get(key)
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{label} must be an array of non-empty strings")
    return value


def _require_tier(value: Any, label: str) -> str:
    if value not in TIER_ORDER:
        raise ValueError(f"{label} must be one of {list(TIER_ORDER)}")
    return value
