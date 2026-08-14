"""Deterministic task routing policy loader and tier helpers."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
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


def route_task(
    *,
    system_root: Path,
    project: str,
    requirement: str,
    repo_root: Path,
    candidate_files: list[str],
    observed_signals: list[str],
    uncertainties: list[str],
    requested_actions: list[str],
    current_tier: str | None = None,
) -> dict[str, Any]:
    """Return a deterministic minimum governance tier for a task."""
    root = Path(system_root).resolve()
    policy = load_routing_policy(root / "base" / "task-routing-policy.json")
    project_dir = root / "projects" / _require_text(project, "project")
    routing = _load_project_routing(project_dir / "playbook.json")
    files = _normalise_strings(candidate_files, "candidate_files")
    signals = _normalise_strings(observed_signals, "observed_signals")
    unknowns = _normalise_strings(uncertainties, "uncertainties")
    actions = _normalise_strings(requested_actions, "requested_actions")
    _require_text(requirement, "requirement")

    overlapping_files = _overlapping_files(Path(repo_root), files)
    fast_path_signals = set(routing.get("fast_path_signals", [])) if routing else set()
    risk_hits = _risk_hits(policy, signals, actions)
    if routing is None:
        _append_unique(risk_hits, "unconfigured_project")
    if unknowns:
        _append_unique(risk_hits, "ambiguous_requirement")
    if overlapping_files:
        _append_unique(risk_hits, "target_file_overlap")
    if any(_is_global_or_common_file(path) for path in files):
        _append_unique(risk_hits, "global_or_common_file")
    if len(files) > 2:
        _append_unique(risk_hits, "scope_exceeds_fast_path")
    hard_vetoes = [
        name
        for name in risk_hits
        if name in {"unconfigured_project", "scope_exceeds_fast_path"}
        or policy["global_risks"].get(name, {}).get("hard_veto_l0", False)
    ]
    qualifies_for_l0 = bool(
        routing
        and files
        and len(files) <= 2
        and signals
        and set(signals).issubset(fast_path_signals)
        and not unknowns
        and not actions
        and not overlapping_files
        and not risk_hits
    )
    tier = "L0" if qualifies_for_l0 else "L1"
    for risk_name in risk_hits:
        if risk_name in policy["global_risks"]:
            tier = _max_tier(tier, policy["global_risks"][risk_name]["min_tier"])
    if current_tier is not None and tier_rank(current_tier) > tier_rank(tier):
        tier = current_tier

    definition = policy["tiers"][tier]
    confidence = "low" if unknowns else "medium" if overlapping_files or routing is None else "high"
    return {
        "tier": tier,
        "confidence": confidence,
        "risk_hits": risk_hits,
        "hard_vetoes": hard_vetoes,
        "required_steps": list(definition["required_steps"]),
        "skipped_steps": list(definition["skipped_steps"]),
        "escalation_triggers": [
            "candidate_scope_expanded",
            "shared_or_public_boundary_discovered",
            "business_rule_or_api_changed",
            "verification_failed_without_clear_cause",
        ],
        "requires_user_confirmation": confidence != "high" or tier_rank(tier) >= tier_rank("L2"),
        "reasons": _routing_reasons(
            qualifies_for_l0=qualifies_for_l0,
            risk_hits=risk_hits,
            configured=routing is not None,
        ),
    }


def _risk_hits(policy: dict[str, Any], signals: list[str], actions: list[str]) -> list[str]:
    known_risks = policy["global_risks"]
    hits: list[str] = []
    for value in [*signals, *actions]:
        if value in known_risks and value not in hits:
            hits.append(value)
    return hits


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _is_global_or_common_file(path: str) -> bool:
    normalised = path.replace("\\", "/").lower().removeprefix("./")
    common_prefixes = (
        "common/",
        "components/",
        "src/components/common/",
        "styles/",
        "src/styles/",
        "theme/",
        "src/theme/",
    )
    global_names = {
        "app.vue",
        "main.js",
        "main.ts",
        "manifest.json",
        "pages.json",
        "package.json",
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
    }
    return normalised.startswith(common_prefixes) or normalised.rsplit("/", 1)[-1] in global_names


def _max_tier(left: str, right: str) -> str:
    return left if tier_rank(left) >= tier_rank(right) else right


def _routing_reasons(*, qualifies_for_l0: bool, risk_hits: list[str], configured: bool) -> list[str]:
    if qualifies_for_l0:
        return ["configured local fast-path signal"]
    reasons = []
    if not configured:
        reasons.append("project routing is not configured")
    if risk_hits:
        reasons.append("risk floor applied: " + ", ".join(risk_hits))
    return reasons or ["fast-path conditions not satisfied"]


def _load_project_routing(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("routing"), dict):
        return None
    return payload["routing"]


def _overlapping_files(repo_root: Path, candidate_files: list[str]) -> list[str]:
    if not candidate_files:
        return []
    try:
        completed = subprocess.run(
            ["git", "status", "--porcelain=v1", "--", *candidate_files],
            cwd=Path(repo_root),
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return list(candidate_files)
    return [line[3:].strip() for line in completed.stdout.splitlines() if line.strip()]


def _normalise_strings(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{label} must be an array of non-empty strings")
    return [item.strip() for item in value]


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


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
