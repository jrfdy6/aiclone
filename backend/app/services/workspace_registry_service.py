from __future__ import annotations

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
WORKSPACE_KIND_VALUES = ("executive", "workspace")

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
        "aliases": ["shared_ops", "shared-ops", "shared ops"],
        "route": None,
        "accent": "#f59e0b",
        "snapshot_mode": "scaffold",
        "portfolio_visible": False,
    },
    {
        "key": "feezie-os",
        "kind": "workspace",
        "display_name": "FEEZIE OS",
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
        "workspace_sync_participants": ["Jean-Claude", "Neo", "Yoda"],
        "description": "Executive-facing public-signal execution workspace for source intake, reaction loops, content generation, and persona-grounded FEEZIE visibility.",
        "operating_principles": [
            "Persona truth first, posting second",
            "Use live source signals before generic ideation",
            "Turn reactions into reusable visibility assets",
        ],
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
        "aliases": ["fusion-os", "fusion os", "fusion"],
        "route": None,
        "accent": "#22c55e",
        "snapshot_mode": "scaffold",
        "portfolio_visible": True,
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
        "aliases": ["easyoutfitapp", "easy outfit app", "easy outfit"],
        "route": None,
        "accent": "#f472b6",
        "snapshot_mode": "live",
        "portfolio_visible": True,
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
        "aliases": ["ai-swag-store", "ai swag store", "swag store"],
        "route": None,
        "accent": "#f59e0b",
        "snapshot_mode": "scaffold",
        "portfolio_visible": True,
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
        "aliases": ["agc"],
        "route": None,
        "accent": "#a78bfa",
        "snapshot_mode": "scaffold",
        "portfolio_visible": True,
    },
)


@lru_cache(maxsize=1)
def workspace_registry_entries() -> tuple[dict[str, Any], ...]:
    ordered = sorted(_WORKSPACE_REGISTRY, key=lambda item: (int(item.get("priority_order") or 0), str(item.get("key") or "")))
    return tuple({**entry} for entry in ordered)


@lru_cache(maxsize=1)
def workspace_registry_map() -> dict[str, dict[str, Any]]:
    return {str(entry["key"]): dict(entry) for entry in workspace_registry_entries()}


@lru_cache(maxsize=1)
def workspace_aliases_map() -> dict[str, frozenset[str]]:
    return {
        str(entry["key"]): frozenset(str(alias).strip() for alias in entry.get("aliases") or [] if str(alias).strip())
        for entry in workspace_registry_entries()
    }


@lru_cache(maxsize=1)
def workspace_alias_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    for canonical, aliases in workspace_aliases_map().items():
        for alias in aliases:
            lookup[alias] = canonical
    return lookup


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
    return tuple(
        str(entry["key"])
        for entry in workspace_registry_entries()
        if entry.get("kind") == "workspace" and bool(entry.get("portfolio_visible"))
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
        "workspaces": [dict(entry) for entry in workspaces],
    }
