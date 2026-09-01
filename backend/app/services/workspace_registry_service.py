from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any


def resolve_repo_root() -> Path:
    current = Path(__file__).resolve()
    candidates = (current.parents[3], current.parents[2], Path.cwd())
    for candidate in candidates:
        if (candidate / "workspaces").exists() or (candidate / "knowledge").exists():
            return candidate
    return current.parents[3]


REPO_ROOT = resolve_repo_root()
WORKSPACES_ROOT = REPO_ROOT / "workspaces"

WORKSPACE_STATUS_VALUES = ("live", "standing_up", "planned")
ACTIVE_PORTFOLIO_WORKSPACE_STATUSES = frozenset({"live", "standing_up"})
WORKSPACE_KIND_VALUES = ("executive", "workspace")

BASE_WORKSPACE_CAPABILITY_KEYS = ("system_health", "pm_work", "standups")

WORKSPACE_GOAL_CONTRACT_SCHEMA_VERSION = "workspace_goal_contract/v1"
WORKSPACE_GOAL_CONTRACT_AUTHORITY_SCHEMA_VERSION = "workspace_goal_contract_authority/v1"
WORKSPACE_GOAL_CONTRACT_AUTHORITY_PATH = WORKSPACES_ROOT / "shared-ops" / "workspace_goal_contracts.json"
WORKSPACE_GOAL_CONTRACT_AUTHORITY_MAX_BYTES = 256 * 1024
WORKSPACE_GOAL_CONTRACT_REQUIRED_FIELDS = (
    "goal",
    "progress_signals",
    "phase_gate",
    "no_action_trigger",
    "safe_internal_boundary",
    "owner_required_boundary",
    "authority_refs",
)

WORKSPACE_CAPABILITY_CATALOG: dict[str, dict[str, Any]] = {
    "system_health": {
        "label": "System health",
        "description": "Health, freshness, blockers, and execution-state visibility.",
        "remote_data_policy": "status_and_counts",
    },
    "pm_work": {
        "label": "PM work",
        "description": "Prioritized work cards, review gates, and operator handoffs.",
        "remote_data_policy": "safe_priority_metadata",
    },
    "standups": {
        "label": "Standups",
        "description": "Standup freshness, status, and blocker counts.",
        "remote_data_policy": "status_and_counts",
    },
    "portfolio_operations": {
        "label": "Portfolio operations",
        "description": "Cross-workspace health, prioritization, and escalation.",
        "remote_data_policy": "status_and_counts",
    },
    "source_ingestion": {
        "label": "Source ingestion",
        "description": "Capture, normalization, classification, and routing of source material.",
        "remote_data_policy": "counts_and_stable_ids",
    },
    "persona_curation": {
        "label": "Persona curation",
        "description": "Human-reviewed beliefs, voice patterns, examples, and lived stories.",
        "remote_data_policy": "coverage_and_review_counts",
    },
    "content_pipeline": {
        "label": "Content pipeline",
        "description": "Content candidates, generation stages, review, and publication readiness.",
        "remote_data_policy": "counts_and_approved_recommendations",
    },
    "education_operations": {
        "label": "Education operations",
        "description": "Admissions, enrollment, referral, and school-operations workflows.",
        "remote_data_policy": "status_and_approved_recommendations",
    },
    "product_delivery": {
        "label": "Product delivery",
        "description": "Product planning, implementation, validation, and release workflows.",
        "remote_data_policy": "status_and_approved_recommendations",
    },
    "recommendation_logic": {
        "label": "Recommendation logic",
        "description": "Multi-variable decision logic and recommendation-quality validation.",
        "remote_data_policy": "status_and_aggregate_metrics",
    },
    "commerce_operations": {
        "label": "Commerce operations",
        "description": "Demand validation, catalog, storefront, and fulfillment workflows.",
        "remote_data_policy": "status_and_aggregate_metrics",
    },
    "government_contracting": {
        "label": "Government contracting",
        "description": "Capability positioning, opportunity qualification, and buyer workflows.",
        "remote_data_policy": "status_and_approved_recommendations",
    },
    "career_tools": {
        "label": "Career tools",
        "description": "Utility-product, audience, acquisition, and monetization workflows.",
        "remote_data_policy": "status_and_aggregate_metrics",
    },
}

_WORKSPACE_REGISTRY: tuple[dict[str, Any], ...] = (
    {
        "key": "shared_ops",
        "kind": "executive",
        "display_name": "Executive Standup",
        "short_label": "Exec Standup",
        "brief_heading": "Executive Interpretation Rule",
        "workspace_root": "shared-ops",
        "status": "live",
        "priority_order": 0,
        "operator_name": "Jean-Claude",
        "manager_agent": "Jean-Claude",
        "target_agent": "Jean-Claude",
        "workspace_agent": None,
        "execution_mode": "direct",
        "default_standup_kind": "executive_ops",
        "workspace_sync_participants": ["Jean-Claude", "Neo", "Yoda"],
        "description": "Portfolio executive standup for operating review, cross-workspace decisions, and system-level follow-through.",
        "operating_principles": [
            "Keep the portfolio legible before expanding it",
            "Let cross-workspace signals route through one executive lane",
            "Promote only what should become real work",
        ],
        "goal_contract_authority": "private_shared_ops",
        "aliases": ["shared_ops", "shared-ops", "shared ops"],
        "route": None,
        "accent": "#f59e0b",
        "snapshot_mode": "scaffold",
        "portfolio_visible": False,
        "capability_keys": ["portfolio_operations"],
    },
    {
        "key": "feezie-os",
        "kind": "workspace",
        "display_name": "FEEZIE OS",
        "portfolio_label": "FEEZIE OS — Visibility & Distribution",
        "short_label": "FEEZIE",
        "brief_heading": "FEEZIE OS",
        "workspace_root": "linkedin-content-os",
        "status": "live",
        "priority_order": 1,
        "operator_name": "FEEZIE Operator",
        "manager_agent": "Jean-Claude",
        "target_agent": "Jean-Claude",
        "workspace_agent": None,
        "execution_mode": "direct",
        "default_standup_kind": "workspace_sync",
        "workspace_sync_participants": [],
        "standup_relevance_required": True,
        "description": "Turns Feeze's knowledge, experience, and aspirations into public value, credibility, relationships, audience, and durable distribution.",
        "operating_principles": [
            "Persona truth first, posting second",
            "Use live source signals before generic ideation",
            "Turn reactions into reusable visibility assets",
        ],
        "goal_contract_authority": "private_shared_ops",
        "aliases": [
            "feezie-os",
            "feezie os",
            "feezie",
            "feezie content",
            "feezie content os",
            "linkedin-os",
            "linkedin os",
            "linkedin",
            "linkedin-content-os",
            "linkedin content os",
        ],
        "route": "/workspace",
        "accent": "#38bdf8",
        "snapshot_mode": "live",
        "portfolio_visible": True,
        "capability_keys": ["source_ingestion", "persona_curation", "content_pipeline"],
    },
    {
        "key": "fusion-os",
        "kind": "workspace",
        "display_name": "Fusion OS",
        "short_label": "Fusion",
        "brief_heading": "Fusion OS",
        "workspace_root": "fusion-os",
        "status": "standing_up",
        "priority_order": 2,
        "operator_name": "Fusion Systems Operator",
        "manager_agent": "Jean-Claude",
        "target_agent": "Fusion Systems Operator",
        "workspace_agent": "Fusion Systems Operator",
        "execution_mode": "delegated",
        "default_standup_kind": "workspace_sync",
        "workspace_sync_participants": ["Jean-Claude", "Fusion Systems Operator"],
        "description": "Admissions, enrollment, school operations, referral systems, and leadership execution for Fusion-adjacent work.",
        "operating_principles": [
            "Protect trust with families and partners",
            "Let frontline signals drive process changes",
            "Make execution clearer before scaling it",
        ],
        "goal_contract_authority": "private_shared_ops",
        "aliases": ["fusion-os", "fusion os", "fusion"],
        "route": None,
        "accent": "#22c55e",
        "snapshot_mode": "scaffold",
        "portfolio_visible": True,
        "capability_keys": ["education_operations"],
    },
    {
        "key": "easyoutfitapp",
        "kind": "workspace",
        "display_name": "Easy Outfit App",
        "short_label": "Easy Outfit",
        "brief_heading": "Easy Outfit App",
        "workspace_root": "easyoutfitapp",
        "status": "live",
        "priority_order": 3,
        "operator_name": "Easy Outfit App Operator Agent",
        "manager_agent": "Jean-Claude",
        "target_agent": "Easy Outfit App Operator Agent",
        "workspace_agent": "Easy Outfit App Operator Agent",
        "execution_mode": "delegated",
        "default_standup_kind": "workspace_sync",
        "workspace_sync_participants": ["Jean-Claude", "Easy Outfit App Operator Agent"],
        "description": "Context-aware wardrobe decision engine focused on restoring, improving, and growing Easy Outfit App without drifting into generic fashion content.",
        "operating_principles": [
            "Reduce decision fatigue with context-aware outfit help",
            "Prioritize owned-wardrobe trust over shopping pressure",
            "Make recommendation quality and reasoning legible",
        ],
        "goal_contract_authority": "private_shared_ops",
        "aliases": ["easyoutfitapp", "easy outfit app", "easy outfit"],
        "route": None,
        "accent": "#f472b6",
        "snapshot_mode": "live",
        "portfolio_visible": True,
        "capability_keys": ["product_delivery", "recommendation_logic"],
    },
    {
        "key": "ai-swag-store",
        "kind": "workspace",
        "display_name": "AI Swag Store",
        "short_label": "Swag Store",
        "brief_heading": "AI Swag Store",
        "workspace_root": "ai-swag-store",
        "status": "standing_up",
        "priority_order": 4,
        "operator_name": "AI Swag Store Operator Agent",
        "manager_agent": "Jean-Claude",
        "target_agent": "AI Swag Store Operator Agent",
        "workspace_agent": "AI Swag Store Operator Agent",
        "execution_mode": "delegated",
        "default_standup_kind": "workspace_sync",
        "workspace_sync_participants": ["Jean-Claude", "AI Swag Store Operator Agent"],
        "description": "Differentiated merch and storefront operating system for AI swag that learns from traffic and demand before scaling the catalog.",
        "operating_principles": [
            "Test demand before expanding catalog",
            "Use differentiated creative instead of generic AI merch filler",
            "Optimize for traffic and learning before catalog breadth",
            "Keep fulfillment and operations simple enough to repeat",
        ],
        "goal_contract_authority": "private_shared_ops",
        "aliases": ["ai-swag-store", "ai swag store", "swag store"],
        "route": None,
        "accent": "#f59e0b",
        "snapshot_mode": "scaffold",
        "portfolio_visible": True,
        "capability_keys": ["product_delivery", "commerce_operations"],
    },
    {
        "key": "agc",
        "kind": "workspace",
        "display_name": "AGC",
        "short_label": "AGC",
        "brief_heading": "AGC",
        "workspace_root": "agc",
        "status": "standing_up",
        "priority_order": 5,
        "operator_name": "AGC Operator Agent",
        "manager_agent": "Jean-Claude",
        "target_agent": "AGC Operator Agent",
        "workspace_agent": "AGC Operator Agent",
        "execution_mode": "delegated",
        "default_standup_kind": "workspace_sync",
        "workspace_sync_participants": ["Jean-Claude", "AGC Operator Agent"],
        "description": "Government-contracting-first operating system for AGC, starting with AI consulting and optimizing for qualified inbound email conversations.",
        "operating_principles": [
            "Lead with a government-contracting-first AI consulting posture",
            "Earn credibility without inventing capability claims",
            "Optimize for qualified inbound email from real buyers",
        ],
        "goal_contract_authority": "private_shared_ops",
        "aliases": ["agc"],
        "route": None,
        "accent": "#a78bfa",
        "snapshot_mode": "scaffold",
        "portfolio_visible": True,
        "capability_keys": ["government_contracting"],
    },
    {
        "key": "work-life-tools",
        "kind": "workspace",
        "display_name": "Work Life Tools",
        "short_label": "Work Life",
        "brief_heading": "Work Life Tools",
        "workspace_root": "work-life-tools",
        "status": "live",
        "priority_order": 6,
        "operator_name": "Work Life Tools Operator Agent",
        "manager_agent": "Jean-Claude",
        "target_agent": "Work Life Tools Operator Agent",
        "workspace_agent": "Work Life Tools Operator Agent",
        "execution_mode": "delegated",
        "default_standup_kind": "workspace_sync",
        "workspace_sync_participants": ["Jean-Claude", "Work Life Tools Operator Agent"],
        "description": "Faceless work-and-lifestyle utility business beginning with the True Job Value Calculator and a YouTube-to-website acquisition loop.",
        "operating_principles": [
            "Make the tool genuinely useful before optimizing ad inventory",
            "Keep the public brand faceless and separate from Feeze's identity",
            "Use verified product and traffic evidence before expanding the tool set",
            "Preserve private career evidence without inventing impact claims",
        ],
        "goal_contract_authority": "private_shared_ops",
        "aliases": [
            "work-life-tools",
            "work life tools",
            "work life calculator",
            "true-job-value",
            "true job value",
            "true job value calculator",
        ],
        "route": None,
        "accent": "#0f766e",
        "snapshot_mode": "live",
        "portfolio_visible": True,
        "capability_keys": ["product_delivery", "career_tools"],
    },
)


def _validated_goal_contract(workspace_key: str, contract: Any) -> dict[str, Any]:
    if not isinstance(contract, dict):
        raise ValueError(f"Workspace `{workspace_key}` is missing its canonical goal contract.")
    expected_fields = {"schema_version", *WORKSPACE_GOAL_CONTRACT_REQUIRED_FIELDS}
    if set(contract) != expected_fields:
        raise ValueError(f"Workspace `{workspace_key}` goal contract has unsupported fields.")
    if str(contract.get("schema_version") or "") != WORKSPACE_GOAL_CONTRACT_SCHEMA_VERSION:
        raise ValueError(f"Workspace `{workspace_key}` has an unsupported goal-contract schema.")
    missing = [field for field in WORKSPACE_GOAL_CONTRACT_REQUIRED_FIELDS if not contract.get(field)]
    if missing:
        raise ValueError(f"Workspace `{workspace_key}` goal contract is missing: {', '.join(missing)}.")

    normalized = {"schema_version": WORKSPACE_GOAL_CONTRACT_SCHEMA_VERSION}
    for field in ("progress_signals", "safe_internal_boundary", "owner_required_boundary", "authority_refs"):
        values = contract.get(field)
        if not isinstance(values, list) or not all(isinstance(value, str) and value.strip() for value in values):
            raise ValueError(f"Workspace `{workspace_key}` goal-contract field `{field}` must contain non-empty strings.")
        normalized[field] = [value.strip() for value in values]
    for field in ("goal", "phase_gate", "no_action_trigger"):
        value = contract.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Workspace `{workspace_key}` goal-contract field `{field}` must be a non-empty string.")
        normalized[field] = value.strip()
    return normalized


def _parse_authority_observed_at(value: Any) -> str:
    raw = str(value or "").strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Workspace goal authority observed_at must be ISO-8601.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Workspace goal authority observed_at must be timezone-aware.")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@lru_cache(maxsize=1)
def _load_private_goal_contract_authority() -> dict[str, Any] | None:
    """Read the private goal authority when this checkout legitimately has it.

    The public deployment tree intentionally excludes this file. Missing is
    therefore a bounded availability state, while a present-but-invalid file
    fails closed for goal-directed work without disabling structural routing.
    """

    path = WORKSPACE_GOAL_CONTRACT_AUTHORITY_PATH
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise ValueError("Workspace goal authority must be a regular non-symlink file.")
    if path.stat().st_size > WORKSPACE_GOAL_CONTRACT_AUTHORITY_MAX_BYTES:
        raise ValueError("Workspace goal authority exceeds its bounded size.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Workspace goal authority could not be read as bounded JSON.") from exc
    required_top_level = {
        "schema_version",
        "observed_at",
        "clock",
        "write_authority",
        "contracts",
    }
    if not isinstance(payload, dict) or set(payload) != required_top_level:
        raise ValueError("Workspace goal authority has unsupported top-level fields.")
    if payload.get("schema_version") != WORKSPACE_GOAL_CONTRACT_AUTHORITY_SCHEMA_VERSION:
        raise ValueError("Workspace goal authority has an unsupported schema.")
    if payload.get("write_authority") != "private_workspace_repository":
        raise ValueError("Workspace goal authority has an unsupported writer.")
    clock = payload.get("clock")
    if (
        not isinstance(clock, dict)
        or set(clock) != {"authority", "timestamp_meaning"}
        or clock.get("authority") != "ai_clone_utc"
        or not str(clock.get("timestamp_meaning") or "").strip()
    ):
        raise ValueError("Workspace goal authority has an invalid clock contract.")
    observed_at = _parse_authority_observed_at(payload.get("observed_at"))
    contracts = payload.get("contracts")
    expected_keys = {str(entry["key"]) for entry in _WORKSPACE_REGISTRY}
    if not isinstance(contracts, dict) or set(contracts) != expected_keys:
        raise ValueError("Workspace goal authority must cover the exact canonical portfolio.")
    normalized_contracts = {
        workspace_key: _validated_goal_contract(workspace_key, contracts[workspace_key])
        for workspace_key in sorted(expected_keys)
    }
    canonical = {
        "schema_version": WORKSPACE_GOAL_CONTRACT_AUTHORITY_SCHEMA_VERSION,
        "observed_at": observed_at,
        "clock": {
            "authority": "ai_clone_utc",
            "timestamp_meaning": str(clock["timestamp_meaning"]).strip(),
        },
        "write_authority": "private_workspace_repository",
        "contracts": normalized_contracts,
    }
    canonical["authority_sha256"] = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return canonical


def _goal_contract_authority_state() -> tuple[dict[str, Any] | None, str]:
    try:
        authority = _load_private_goal_contract_authority()
    except ValueError:
        return None, "invalid_private_authority"
    if authority is None:
        return None, "private_authority_unavailable"
    return authority, "available_private_authority"


@lru_cache(maxsize=1)
def workspace_registry_entries() -> tuple[dict[str, Any], ...]:
    ordered = sorted(_WORKSPACE_REGISTRY, key=lambda item: (int(item.get("priority_order") or 0), str(item.get("key") or "")))
    goal_authority, goal_authority_state = _goal_contract_authority_state()
    contracts = goal_authority.get("contracts") if isinstance(goal_authority, dict) else {}
    enriched: list[dict[str, Any]] = []
    for entry in ordered:
        capability_keys = list(
            dict.fromkeys(
                [
                    *BASE_WORKSPACE_CAPABILITY_KEYS,
                    *(str(key).strip() for key in entry.get("capability_keys") or [] if str(key).strip()),
                ]
            )
        )
        enriched.append(
            {
                **entry,
                "goal_contract": dict(contracts.get(str(entry["key"])) or {}),
                "goal_contract_status": goal_authority_state,
                "goal_contract_source_path": (
                    "workspaces/shared-ops/workspace_goal_contracts.json"
                    if goal_authority_state == "available_private_authority"
                    else None
                ),
                "goal_contract_observed_at": (
                    goal_authority.get("observed_at") if isinstance(goal_authority, dict) else None
                ),
                "goal_contract_authority_sha256": (
                    goal_authority.get("authority_sha256") if isinstance(goal_authority, dict) else None
                ),
                "capability_keys": capability_keys,
                "capabilities": [
                    {"key": key, **WORKSPACE_CAPABILITY_CATALOG[key]}
                    for key in capability_keys
                    if key in WORKSPACE_CAPABILITY_CATALOG
                ],
            }
        )
    return tuple(enriched)


@lru_cache(maxsize=1)
def workspace_registry_map() -> dict[str, dict[str, Any]]:
    return {str(entry["key"]): dict(entry) for entry in workspace_registry_entries()}


@lru_cache(maxsize=1)
def workspace_aliases_map() -> dict[str, frozenset[str]]:
    return {
        str(entry["key"]): frozenset(str(alias).strip() for alias in entry.get("aliases") or [] if str(alias).strip())
        for entry in _WORKSPACE_REGISTRY
    }


@lru_cache(maxsize=1)
def workspace_alias_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    for canonical, aliases in workspace_aliases_map().items():
        for alias in aliases:
            lookup[alias] = canonical
    return lookup


def clear_workspace_registry_caches() -> None:
    """Clear the bounded registry/goal read caches after an authority change."""

    _load_private_goal_contract_authority.cache_clear()
    workspace_registry_entries.cache_clear()
    workspace_registry_map.cache_clear()
    workspace_aliases_map.cache_clear()
    workspace_alias_lookup.cache_clear()


def workspace_registry_keys(*, include_executive: bool = True) -> tuple[str, ...]:
    entries = workspace_registry_entries()
    if include_executive:
        return tuple(str(entry["key"]) for entry in entries)
    return tuple(str(entry["key"]) for entry in entries if entry.get("kind") == "workspace")


def project_workspace_keys() -> tuple[str, ...]:
    return tuple(
        str(entry["key"])
        for entry in workspace_registry_entries()
        if entry.get("kind") == "workspace" and str(entry.get("key")) != "feezie-os"
    )


def portfolio_workspace_keys() -> tuple[str, ...]:
    """Return the canonical active portfolio scope used by Dream and Ops."""

    return active_portfolio_workspace_keys()


def active_portfolio_workspace_keys(
    entries: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
) -> tuple[str, ...]:
    source = entries if entries is not None else workspace_registry_entries()
    return tuple(
        str(entry["key"])
        for entry in source
        if entry.get("kind") in {None, "workspace"}
        and bool(entry.get("portfolio_visible"))
        and str(entry.get("status") or "") in ACTIVE_PORTFOLIO_WORKSPACE_STATUSES
        and str(entry.get("key") or "").strip()
    )


def workspace_registry_entry(workspace_key: str | None, *, default: str = "shared_ops") -> dict[str, Any]:
    canonical = canonicalize_workspace_key(workspace_key, default=default)
    entry = workspace_registry_map().get(canonical)
    if entry is not None:
        return dict(entry)
    fallback_key = canonical or default
    return {
        "key": fallback_key,
        "kind": "workspace",
        "display_name": fallback_key,
        "portfolio_label": fallback_key,
        "short_label": fallback_key,
        "brief_heading": fallback_key,
        "workspace_root": fallback_key,
        "status": "planned",
        "priority_order": 999,
        "operator_name": "Workspace Agent",
        "manager_agent": "Jean-Claude",
        "target_agent": "Workspace Agent",
        "workspace_agent": "Workspace Agent",
        "execution_mode": "delegated",
        "default_standup_kind": "workspace_sync",
        "workspace_sync_participants": ["Jean-Claude", "Workspace Agent"],
        "description": f"{fallback_key} workspace",
        "operating_principles": [],
        "aliases": [fallback_key],
        "route": None,
        "accent": "#94a3b8",
        "snapshot_mode": "scaffold",
        "portfolio_visible": True,
        "capability_keys": list(BASE_WORKSPACE_CAPABILITY_KEYS),
        "capabilities": [
            {"key": key, **WORKSPACE_CAPABILITY_CATALOG[key]}
            for key in BASE_WORKSPACE_CAPABILITY_KEYS
        ],
    }


def canonicalize_workspace_key(workspace_key: str | None, *, default: str = "shared_ops") -> str:
    raw = str(workspace_key or "").strip()
    if not raw:
        return default
    lowered = raw.lower().strip()
    variants = {
        lowered,
        lowered.replace("_", "-"),
        lowered.replace("-", " "),
        lowered.replace("_", " "),
    }
    for candidate in variants:
        canonical = workspace_alias_lookup().get(candidate.strip())
        if canonical:
            return canonical
    return raw


def workspace_storage_aliases(workspace_key: str | None, *, default: str = "shared_ops") -> tuple[str, ...]:
    """Return every persisted spelling that belongs to one canonical workspace.

    Historical PM cards and standups intentionally retain their original
    workspace keys for auditability. Read surfaces use this alias set so a
    canonical workspace view can include that history without rewriting it.
    """

    canonical = canonicalize_workspace_key(workspace_key, default=default)
    entry = workspace_registry_entry(canonical, default=default)
    candidates = {
        canonical,
        str(entry.get("key") or ""),
        str(entry.get("workspace_root") or ""),
        *(str(alias) for alias in entry.get("aliases") or []),
    }
    normalized: set[str] = set()
    for candidate in candidates:
        lowered = candidate.strip().lower()
        if not lowered:
            continue
        normalized.update(
            {
                lowered,
                lowered.replace("_", "-"),
                lowered.replace("-", " "),
                lowered.replace("_", " "),
            }
        )
    return tuple(sorted(normalized))


def workspace_root_slug(workspace_key: str | None) -> str:
    entry = workspace_registry_entry(workspace_key)
    return str(entry.get("workspace_root") or entry.get("key") or "")


def workspace_root_path(workspace_key: str | None, *, repo_root: Path | None = None) -> Path:
    root = repo_root or REPO_ROOT
    return root / "workspaces" / workspace_root_slug(workspace_key)


def workspace_registry_payload(*, include_executive: bool = True) -> dict[str, Any]:
    workspaces = [
        entry
        for entry in workspace_registry_entries()
        if include_executive or entry.get("kind") != "executive"
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": "workspace_registry/v2",
        "capability_catalog": [
            {"key": key, **definition}
            for key, definition in WORKSPACE_CAPABILITY_CATALOG.items()
        ],
        "workspaces": [
            {
                **{
                    key: value
                    for key, value in entry.items()
                    if key not in {
                        "goal_contract",
                        "goal_contract_source_path",
                        "goal_contract_status",
                        "goal_contract_observed_at",
                        "goal_contract_authority_sha256",
                    }
                },
                "goal_contract_status": "private_authority_not_exposed_by_structural_registry",
            }
            for entry in workspaces
        ],
    }
