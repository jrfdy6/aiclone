from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.services import persona_delta_service
from app.services.content_reservoir_service import build_content_reservoir_payload
from app.services.feezie_runtime_context_service import (
    build_feezie_private_runtime_context_status,
    load_persisted_feezie_strategy_contract,
)
from app.services.social_feed_builder_service import (
    build_feed as build_social_feed_runtime_payload,
    discover_linkedin_workspace_root,
)
from app.services.social_feedback_service import social_feedback_service
from app.services.social_feed_refresh import social_feed_refresh_service
from app.services.linkedin_source_lifecycle_service import build_source_lifecycle
from app.services.linkedin_performance_ledger_service import (
    LinkedinPerformanceLedgerCorruption,
    build_browser_performance_summary,
    linkedin_performance_ledger_service,
)
from app.services.open_brain_db import get_pool
from app.services.social_long_form_signal_service import build_long_form_route_summary
from app.services.social_persona_review_service import social_persona_review_service
from app.services.social_source_asset_service import build_source_asset_inventory
from app.services.workspace_snapshot_store import get_snapshot_payload, list_snapshot_payloads, upsert_snapshot
from app.utils.runtime_workspace_root import resolve_runtime_workspace_root


TRANSCRIPT_LIBRARY_SKIP_NAMES = {"README.md", "TEMPLATE.md", "INDEX.md"}
PINNED_DOC_PATHS = (
    "SOURCE_OF_TRUTH.md",
    "CODEX_STARTUP.md",
    "AGENTS.md",
    "IDENTITY.md",
    "CHARTER.md",
    "SOUL.md",
    "USER.md",
    "MEMORY.md",
    "memory/persistent_state.md",
    "memory/roadmap.md",
    "SOPs/_index.md",
    "docs/aiclone_system_architecture.md",
    "docs/aiclone_brain_architecture.md",
)
_DOC_EXCLUDED_DIRECTORY_NAMES = frozenset({"runtime_snapshots", "runtime-snapshots"})
_DOC_RETIRED_PATH_MARKERS = ("openclaw", "qmd")


def _count_matching_files(path: Path, pattern: str, *, exclude_names: set[str] | None = None) -> int:
    if not path.exists() or not path.is_dir():
        return 0
    excluded = exclude_names or set()
    return sum(1 for item in path.rglob(pattern) if item.is_file() and item.name not in excluded)


def _workspace_root_score(path: Path) -> tuple[int, int]:
    score = 0
    if (path / "workspaces" / "linkedin-content-os").exists():
        score += 100
    if (path / "backend" / "workspaces" / "linkedin-content-os").exists():
        score += 60
    score += _count_matching_files(path / "knowledge" / "ingestions", "normalized.md") * 20
    score += _count_matching_files(
        path / "knowledge" / "aiclone" / "transcripts",
        "*.md",
        exclude_names=TRANSCRIPT_LIBRARY_SKIP_NAMES,
    ) * 8
    return score, -len(path.parts)


def _external_workspace_roots() -> list[Path]:
    configured = os.environ.get("AI_CLONE_ROOT")
    candidates = [configured]
    roots: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        if path in seen:
            continue
        seen.add(path)
        roots.append(path)
    return roots


def resolve_workspace_root() -> Path:
    return resolve_runtime_workspace_root(__file__)


ROOT = resolve_workspace_root()
PRIVATE_STATE_ROOT = Path(
    os.getenv("AI_CLONE_STATE_ROOT") or (Path.home() / ".codex" / "ai-clone" / "state")
).expanduser()
_SCRIPTS_ROOT = ROOT / "scripts"
if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))

from runtime_paths import resolve_memory_read_path  # noqa: E402


OPERATOR_STORY_SIGNALS_LOGICAL_REF = "memory/reports/operator_story_signals_latest.json"
CONTENT_SAFE_OPERATOR_LESSONS_LOGICAL_REF = "memory/reports/content_safe_operator_lessons_latest.json"
OPERATOR_STORY_SIGNALS_PATH = ROOT / OPERATOR_STORY_SIGNALS_LOGICAL_REF
CONTENT_SAFE_OPERATOR_LESSONS_PATH = ROOT / CONTENT_SAFE_OPERATOR_LESSONS_LOGICAL_REF


def _memory_report_read_path(logical_ref: str, configured_path: Path) -> Path:
    project_default = ROOT / logical_ref
    if configured_path != project_default:
        # Preserve explicit test and packaged-runtime overrides.
        return configured_path
    return resolve_memory_read_path(
        Path(logical_ref).relative_to("memory"),
        project_root=ROOT,
        state_root=PRIVATE_STATE_ROOT,
    )


def _candidate_roots() -> list[Path]:
    current = Path(__file__).resolve()
    candidates = list(current.parents) + [Path.cwd(), *Path.cwd().parents, *_external_workspace_roots(), ROOT, Path("/app"), Path("/app/backend"), Path("/")]
    ordered: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        ordered.append(candidate)
    return ordered


def _find_dir(*relative_patterns: str) -> Path | None:
    for base in _candidate_roots():
        for pattern in relative_patterns:
            candidate = base / pattern
            if candidate.exists() and candidate.is_dir():
                return candidate
    return None


def _find_richest_dir(*relative_patterns: str, pattern: str, exclude_names: set[str] | None = None) -> Path | None:
    candidates: list[Path] = []
    seen: set[Path] = set()
    for base in _candidate_roots():
        for relative_pattern in relative_patterns:
            candidate = base / relative_pattern
            if not candidate.exists() or not candidate.is_dir():
                continue
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            candidates.append(resolved)
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: (
            _count_matching_files(item, pattern, exclude_names=exclude_names),
            -len(item.parts),
        ),
    )


def _find_file(*relative_patterns: str) -> Path | None:
    for base in _candidate_roots():
        for pattern in relative_patterns:
            candidate = base / pattern
            if candidate.exists() and candidate.is_file():
                return candidate
    return None


def _discover_linkedin_root() -> Path:
    return discover_linkedin_workspace_root()


def _discover_persona_root() -> Path:
    direct = _find_dir(
        "knowledge/persona/feeze",
        "backend/knowledge/persona/feeze",
        "persona/feeze",
    )
    if direct:
        return direct

    for base in [ROOT, Path.cwd(), Path("/app"), Path("/app/backend")]:
        if not base.exists():
            continue
        match = next(base.rglob("knowledge/persona/feeze/identity/claims.md"), None)
        if match:
            return match.parent.parent

    return ROOT / "knowledge" / "persona" / "feeze"


def _discover_doc_roots() -> list[tuple[Path, str]]:
    candidates = [
        (_find_dir("SOPs", "backend/SOPs"), "Operating Docs"),
        (_find_dir("docs", "backend/docs"), "System Docs"),
        (_find_dir("deliverables", "backend/deliverables"), "Reference Docs"),
        (_find_dir("workspaces/linkedin-content-os/docs", "backend/workspaces/linkedin-content-os/docs"), "Workspace Reference"),
        (_find_dir("workspaces/fusion-os/docs", "backend/workspaces/fusion-os/docs"), "Workspace Reference"),
        (_find_dir("workspaces/easyoutfitapp/docs", "backend/workspaces/easyoutfitapp/docs"), "Workspace Reference"),
        (_find_dir("workspaces/ai-swag-store/docs", "backend/workspaces/ai-swag-store/docs"), "Workspace Reference"),
        (_find_dir("workspaces/agc/docs", "backend/workspaces/agc/docs"), "Workspace Reference"),
        (_find_dir("workspaces/work-life-tools/docs", "backend/workspaces/work-life-tools/docs"), "Workspace Reference"),
    ]
    roots: list[tuple[Path, str]] = []
    seen: set[Path] = set()
    for root, label in candidates:
        if root is None or root in seen:
            continue
        seen.add(root)
        roots.append((root, label))
    return roots


def _discover_doc_targets() -> list[tuple[Path, str]]:
    patterns = [
        ("SOURCE_OF_TRUTH.md", "backend/SOURCE_OF_TRUTH.md", "Start Here"),
        ("CODEX_STARTUP.md", "backend/CODEX_STARTUP.md", "Operating Docs"),
        ("AGENTS.md", "backend/AGENTS.md", "Operating Docs"),
        ("IDENTITY.md", "backend/IDENTITY.md", "Identity"),
        ("CHARTER.md", "backend/CHARTER.md", "Identity"),
        ("SOUL.md", "backend/SOUL.md", "Identity"),
        ("USER.md", "backend/USER.md", "Identity"),
        ("MEMORY.md", "backend/MEMORY.md", "Canonical Memory"),
        ("memory/persistent_state.md", "backend/memory/persistent_state.md", "Canonical Memory"),
        ("memory/roadmap.md", "backend/memory/roadmap.md", "Canonical Memory"),
        ("README.md", "backend/README.md", "Reference Docs"),
        ("workspaces/linkedin-content-os/README.md", "backend/workspaces/linkedin-content-os/README.md", "Workspace Reference"),
        ("workspaces/linkedin-content-os/AGENTS.md", "backend/workspaces/linkedin-content-os/AGENTS.md", "Workspace Reference"),
    ]
    targets: list[tuple[Path, str]] = []
    seen: set[Path] = set()
    for primary, fallback, label in patterns:
        found = _find_file(primary, fallback)
        if found is None or found in seen:
            continue
        seen.add(found)
        targets.append((found, label))
    return targets


def _ordered_existing_paths(paths: list[Path]) -> list[Path]:
    ordered: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        try:
            resolved = path.resolve()
        except Exception:
            resolved = path
        if resolved in seen or not resolved.exists():
            continue
        seen.add(resolved)
        ordered.append(resolved)
    return ordered


def _workspace_file_roots() -> list[tuple[Path, str, str | None]]:
    persona_candidates = _ordered_existing_paths(
        [
            ROOT / "knowledge" / "persona" / "feeze",
            ROOT.parent / "knowledge" / "persona" / "feeze",
            _discover_persona_root(),
        ]
    )
    linkedin_candidates = _ordered_existing_paths(
        [
            ROOT / "workspaces" / "linkedin-content-os",
            ROOT.parent / "workspaces" / "linkedin-content-os",
            _discover_linkedin_root(),
        ]
    )
    roots: list[tuple[Path, str, str | None]] = []
    roots.extend((path, "persona-bundle", None) for path in persona_candidates)
    roots.append(
        (
            PRIVATE_STATE_ROOT / "workspaces" / "feezie-os",
            "linkedin-content-os",
            "workspaces/linkedin-content-os",
        )
    )
    roots.extend(
        (path, "linkedin-content-os", "workspaces/linkedin-content-os")
        for path in linkedin_candidates
    )
    return roots


def _doc_root_candidates() -> list[tuple[Path, str]]:
    candidates = [
        (ROOT / "SOPs", "Operating Docs"),
        (ROOT.parent / "SOPs", "Operating Docs"),
        (ROOT / "docs", "System Docs"),
        (ROOT.parent / "docs", "System Docs"),
        (ROOT / "deliverables", "Reference Docs"),
        (ROOT.parent / "deliverables", "Reference Docs"),
        (ROOT / "workspaces" / "linkedin-content-os" / "docs", "Workspace Reference"),
        (ROOT.parent / "workspaces" / "linkedin-content-os" / "docs", "Workspace Reference"),
    ]
    for workspace_key in ("fusion-os", "easyoutfitapp", "ai-swag-store", "agc", "work-life-tools"):
        candidates.extend(
            [
                (ROOT / "workspaces" / workspace_key / "docs", "Workspace Reference"),
                (ROOT.parent / "workspaces" / workspace_key / "docs", "Workspace Reference"),
            ]
        )
    roots: list[tuple[Path, str]] = []
    seen: set[Path] = set()
    for path, label in candidates:
        resolved = path.resolve() if path.exists() else path
        if not resolved.exists() or not resolved.is_dir() or resolved in seen:
            continue
        seen.add(resolved)
        roots.append((resolved, label))
    for path, label in _discover_doc_roots():
        resolved = path.resolve() if path.exists() else path
        if not resolved.exists() or not resolved.is_dir() or resolved in seen:
            continue
        seen.add(resolved)
        roots.append((resolved, label))
    return roots


def _doc_target_candidates() -> list[tuple[Path, str]]:
    candidates = [
        (ROOT / "SOURCE_OF_TRUTH.md", "Start Here"),
        (ROOT.parent / "SOURCE_OF_TRUTH.md", "Start Here"),
        (ROOT / "CODEX_STARTUP.md", "Operating Docs"),
        (ROOT.parent / "CODEX_STARTUP.md", "Operating Docs"),
        (ROOT / "AGENTS.md", "Operating Docs"),
        (ROOT.parent / "AGENTS.md", "Operating Docs"),
        (ROOT / "IDENTITY.md", "Identity"),
        (ROOT.parent / "IDENTITY.md", "Identity"),
        (ROOT / "CHARTER.md", "Identity"),
        (ROOT.parent / "CHARTER.md", "Identity"),
        (ROOT / "SOUL.md", "Identity"),
        (ROOT.parent / "SOUL.md", "Identity"),
        (ROOT / "USER.md", "Identity"),
        (ROOT.parent / "USER.md", "Identity"),
        (ROOT / "MEMORY.md", "Canonical Memory"),
        (ROOT.parent / "MEMORY.md", "Canonical Memory"),
        (ROOT / "memory" / "persistent_state.md", "Canonical Memory"),
        (ROOT.parent / "memory" / "persistent_state.md", "Canonical Memory"),
        (ROOT / "memory" / "roadmap.md", "Canonical Memory"),
        (ROOT.parent / "memory" / "roadmap.md", "Canonical Memory"),
        (ROOT / "README.md", "Reference Docs"),
        (ROOT.parent / "README.md", "Reference Docs"),
        (ROOT / "workspaces" / "linkedin-content-os" / "README.md", "Workspace Reference"),
        (ROOT.parent / "workspaces" / "linkedin-content-os" / "README.md", "Workspace Reference"),
        (ROOT / "workspaces" / "linkedin-content-os" / "AGENTS.md", "Workspace Reference"),
        (ROOT.parent / "workspaces" / "linkedin-content-os" / "AGENTS.md", "Workspace Reference"),
    ]
    targets: list[tuple[Path, str]] = []
    seen: set[Path] = set()
    for path, label in candidates:
        resolved = path.resolve() if path.exists() else path
        if not resolved.exists() or not resolved.is_file() or resolved in seen:
            continue
        seen.add(resolved)
        targets.append((resolved, label))
    for path, label in _discover_doc_targets():
        resolved = path.resolve() if path.exists() else path
        if not resolved.exists() or not resolved.is_file() or resolved in seen:
            continue
        seen.add(resolved)
        targets.append((resolved, label))
    return targets


WORKSPACE_KEY = "linkedin-content-os"
CANONICAL_FEEZIE_WORKSPACE_KEY = "feezie-os"
SNAPSHOT_WEEKLY_PLAN = "weekly_plan"
SNAPSHOT_REACTION_QUEUE = "reaction_queue"
SNAPSHOT_SOCIAL_FEED = "social_feed"
SNAPSHOT_FEEDBACK_SUMMARY = "feedback_summary"
SNAPSHOT_PUBLICATION_PERFORMANCE = "publication_performance_summary"
SNAPSHOT_PUBLICATION_PERFORMANCE_STATUS = "publication_performance_status"
SNAPSHOT_SOURCE_ASSETS = "source_assets"
SNAPSHOT_PERSONA_REVIEW_SUMMARY = "persona_review_summary"
SNAPSHOT_LONG_FORM_ROUTES = "long_form_routes"
SNAPSHOT_CONTENT_RESERVOIR = "content_reservoir"
SNAPSHOT_WORKSPACE_FILES = "workspace_files"
SNAPSHOT_DOC_ENTRIES = "doc_entries"
SNAPSHOT_OPERATOR_STORY_SIGNALS = "operator_story_signals"
SNAPSHOT_CONTENT_SAFE_OPERATOR_LESSONS = "content_safe_operator_lessons"
PERSONA_REVIEW_REFRESH_LOCK_KEY = "aiclone:linkedin-content-os:persona-review-summary"
FEEZIE_WEEKLY_PLAN_PROJECTION_SCHEMA = "feezie_weekly_plan_projection/v1"
FEEZIE_WEEKLY_PLAN_DATA_POLICY = {
    "projection": "public_safe_editorial_metadata",
    "raw_drafts_included": False,
    "raw_persona_included": False,
    "recommendation_copy_included": False,
    "source_urls_included": False,
    "source_paths_included": False,
    "publishing_identity_included": False,
    "absolute_paths_included": False,
    "hold_items_included": False,
    "market_signals_included": False,
    "research_notes_included": False,
}
FEEZIE_WEEKLY_PLAN_LEGACY_BROWSER_SCHEMA = "feezie_weekly_plan_browser_status/v1"
FEEZIE_WEEKLY_PLAN_LEGACY_BROWSER_DATA_POLICY = {
    "projection": "legacy_aggregate_status_only",
    "legacy_rows_included": False,
    "recommendation_copy_included": False,
    "publishing_cards_included": False,
    "portfolio_learning_rows_included": False,
    "identifiers_or_hashes_included": False,
    "source_urls_included": False,
    "source_paths_included": False,
    "raw_drafts_included": False,
    "raw_persona_included": False,
}
PRIVATE_INVENTORY_SCHEMA = "privacy_safe_workspace_inventory/v1"
BROWSER_PRIVATE_GROUNDING_SCHEMA = "feezie_private_grounding_browser_status/v1"
WORKSPACE_SNAPSHOT_STATUS_SCHEMA = "workspace_editorial_status/v1"
BROWSER_PRIVATE_GROUNDING_SNAPSHOT_TYPES = (
    SNAPSHOT_SOURCE_ASSETS,
    SNAPSHOT_CONTENT_RESERVOIR,
    SNAPSHOT_OPERATOR_STORY_SIGNALS,
    SNAPSHOT_CONTENT_SAFE_OPERATOR_LESSONS,
    SNAPSHOT_PERSONA_REVIEW_SUMMARY,
    SNAPSHOT_LONG_FORM_ROUTES,
)
BROWSER_PRIVATE_GROUNDING_COUNT_KEYS = {
    SNAPSHOT_SOURCE_ASSETS: (
        "total",
        "long_form_media",
        "pending_segmentation",
        "feed_ready",
        "structured_summary_ready",
        "lessons_ready",
        "anecdotes_ready",
        "quotes_ready",
        "deep_harvest_ready",
        "deep_harvest_fragments",
    ),
    SNAPSHOT_PERSONA_REVIEW_SUMMARY: (
        "total",
        "brain_pending_review",
        "workspace_saved",
        "approved_unpromoted",
        "pending_promotion",
        "committed",
    ),
}
EDITORIAL_SECTION_STALE_HOURS = {
    SNAPSHOT_WEEKLY_PLAN: 24 * 8,
    SNAPSHOT_REACTION_QUEUE: 48,
    SNAPSHOT_SOCIAL_FEED: 48,
    SNAPSHOT_FEEDBACK_SUMMARY: 48,
    SNAPSHOT_SOURCE_ASSETS: 24 * 8,
    SNAPSHOT_CONTENT_RESERVOIR: 24 * 8,
    SNAPSHOT_PERSONA_REVIEW_SUMMARY: 24 * 8,
    SNAPSHOT_LONG_FORM_ROUTES: 24 * 8,
}
PUBLICATION_PERFORMANCE_BROWSER_KEYS = {
    "schema_version",
    "generated_at",
    "workspace_key",
    "strategy_contract",
    "counts",
    "feedback_completeness",
    "rolling_topic_mix",
    "rolling_intent_mix",
    "initial_pilot",
    "primary_kpi",
    "learning_gate",
    "learning_aggregates",
    "actionable_gaps",
    "data_policy",
}
PUBLICATION_PERFORMANCE_BROWSER_POLICY = {
    "aggregate_only": True,
    "per_publication_rows_included": False,
    "external_post_links_included": False,
    "raw_metric_snapshots_included": False,
    "private_notes_included": False,
    "audience_identities_included": False,
    "raw_copy_included": False,
}

_WEEKLY_PLAN_TOP_LEVEL_KEYS = {
    "schema_version",
    "generated_at",
    "workspace",
    "strategy_contract",
    "positioning_model",
    "priority_lanes",
    "pillar_coverage",
    "development_card_count",
    "recommendations",
    "publishing_board",
    "portfolio_learning",
    "source_counts",
    "data_policy",
}
_WEEKLY_RECOMMENDATION_TEXT_LIMITS = {
    "title": 240,
    "intent": 40,
    "priority_lane": 160,
    "publish_posture": 80,
    "canonical_pillar": 160,
    "career_signal": 80,
    "employer_proximity": 80,
    "employer_safety": 80,
    "proof_posture": 80,
    "audience": 240,
    "audience_consequence": 600,
    "distinct_thesis": 600,
    "why_now": 600,
    "development_status": 80,
    "source_kind": 80,
}
_WEEKLY_RECOMMENDATION_KEYS = set(_WEEKLY_RECOMMENDATION_TEXT_LIMITS)
_WEEKLY_PORTFOLIO_LEARNING_KEYS = {
    "schema_version",
    "source_state",
    "summary_generated_at",
    "learning_mode",
    "confidence",
    "counts",
    "thresholds",
    "remaining_to_advisory",
    "remaining_to_strategy_review",
    "contract_sequence",
    "advisory_aggregates",
    "decision_policy",
}
_WEEKLY_PRIVATE_FIELD_NAMES = {
    "body",
    "content",
    "copy",
    "draft",
    "draft_body",
    "excerpt",
    "file",
    "files",
    "notes",
    "persona",
    "private",
    "raw",
    "raw_copy",
    "raw_draft",
    "raw_persona",
    "raw_text",
    "record",
    "records",
    "research_notes",
    "source_path",
    "source_url",
    "text",
}
_WEEKLY_PRIVATE_TEXT_RE = re.compile(
    r"(?:/Users/|file://|~/|[A-Za-z]:\\\\|BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY|"
    r"(?:password|access[_ -]?token|api[_ -]?key|client[_ -]?secret)\s*[:=]\s*\S+)",
    flags=re.IGNORECASE,
)
_WEEKLY_EMAIL_RE = re.compile(r"(?<![\w.+-])[\w.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![\w.-])")


def _weekly_projection_text(
    value: Any,
    *,
    field: str,
    max_length: int,
    required: bool = False,
) -> str | None:
    if value is None:
        if required:
            raise ValueError(f"weekly_plan.{field} is required.")
        return None
    if not isinstance(value, str):
        raise ValueError(f"weekly_plan.{field} must be a string.")
    text = " ".join(value.split())
    if not text:
        if required:
            raise ValueError(f"weekly_plan.{field} cannot be empty.")
        return None
    if len(text) > max_length:
        raise ValueError(f"weekly_plan.{field} exceeds its bounded length.")
    if _WEEKLY_PRIVATE_TEXT_RE.search(text) or _WEEKLY_EMAIL_RE.search(text):
        raise ValueError(f"weekly_plan.{field} contains private or credential-shaped text.")
    return text


def _weekly_projection_text_list(
    value: Any,
    *,
    field: str,
    max_items: int,
    max_length: int,
) -> list[str]:
    if not isinstance(value, list) or len(value) > max_items:
        raise ValueError(f"weekly_plan.{field} must be a bounded list.")
    compacted: list[str] = []
    for index, item in enumerate(value):
        text = _weekly_projection_text(
            item,
            field=f"{field}[{index}]",
            max_length=max_length,
        )
        if text is not None:
            compacted.append(text)
    return compacted


def _weekly_projection_counts(
    value: Any,
    *,
    field: str,
    max_items: int = 24,
    max_value: int = 1_000_000,
) -> dict[str, int]:
    if not isinstance(value, dict) or len(value) > max_items:
        raise ValueError(f"weekly_plan.{field} must be a bounded count map.")
    compacted: dict[str, int] = {}
    for raw_key, raw_value in value.items():
        key = _weekly_projection_text(
            raw_key,
            field=f"{field}.key",
            max_length=120,
            required=True,
        )
        if isinstance(raw_value, bool) or not isinstance(raw_value, int) or not 0 <= raw_value <= max_value:
            raise ValueError(f"weekly_plan.{field}.{key} must be a bounded nonnegative integer.")
        compacted[key] = raw_value
    return compacted


def _compact_weekly_strategy_contract(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("weekly_plan.strategy_contract is required.")
    allowed = {
        "schema_version",
        "version",
        "contract_version",
        "contract_hash",
        "approved_at",
        "freshness_state",
    }
    unsupported = set(value) - allowed
    if unsupported:
        raise ValueError("weekly_plan.strategy_contract contains unsupported content.")
    schema_version = _weekly_projection_text(
        value.get("schema_version"),
        field="strategy_contract.schema_version",
        max_length=80,
        required=True,
    )
    contract_hash = _weekly_projection_text(
        value.get("contract_hash"),
        field="strategy_contract.contract_hash",
        max_length=64,
        required=True,
    )
    if re.fullmatch(r"[a-f0-9]{64}", contract_hash.lower()) is None:
        raise ValueError("weekly_plan.strategy_contract.contract_hash must be a SHA-256 value.")
    compacted: dict[str, Any] = {
        "schema_version": schema_version,
        "contract_hash": contract_hash.lower(),
    }
    for key, limit in (
        ("version", 40),
        ("contract_version", 40),
        ("approved_at", 64),
        ("freshness_state", 40),
    ):
        text = _weekly_projection_text(
            value.get(key),
            field=f"strategy_contract.{key}",
            max_length=limit,
        )
        if text is not None:
            compacted[key] = text
    return compacted


def _compact_weekly_pillar_coverage(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("weekly_plan.pillar_coverage is required.")
    allowed = {"counts", "unmapped_count", "missing_pillars", "warnings"}
    if set(value) - allowed:
        raise ValueError("weekly_plan.pillar_coverage contains unsupported fields.")
    counts = _weekly_projection_counts(value.get("counts"), field="pillar_coverage.counts", max_items=8)
    unmapped_count = value.get("unmapped_count", 0)
    if isinstance(unmapped_count, bool) or not isinstance(unmapped_count, int) or not 0 <= unmapped_count <= 1_000:
        raise ValueError("weekly_plan.pillar_coverage.unmapped_count is invalid.")
    return {
        "counts": counts,
        "unmapped_count": unmapped_count,
        "missing_pillars": _weekly_projection_text_list(
            value.get("missing_pillars"),
            field="pillar_coverage.missing_pillars",
            max_items=8,
            max_length=160,
        ),
        "warnings": _weekly_projection_text_list(
            value.get("warnings"),
            field="pillar_coverage.warnings",
            max_items=8,
            max_length=320,
        ),
    }


def _compact_weekly_recommendation(value: Any, *, index: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"weekly_plan.recommendations[{index}] must be an object.")
    unsupported = set(value) - _WEEKLY_RECOMMENDATION_KEYS
    if unsupported:
        raise ValueError(f"weekly_plan.recommendations[{index}] contains unsupported or private fields.")
    compacted: dict[str, Any] = {}
    for key, max_length in _WEEKLY_RECOMMENDATION_TEXT_LIMITS.items():
        text = _weekly_projection_text(
            value.get(key),
            field=f"recommendations[{index}].{key}",
            max_length=max_length,
            required=key == "title",
        )
        if text is not None:
            compacted[key] = text
    enums = {
        "intent": {"value", "invitation", "personal"},
        "career_signal": {"education_anchor", "bridge", "tech_proof"},
        "employer_proximity": {"personal_build", "public_event", "generalized_work", "employer_specific"},
        "employer_safety": {"pass", "owner_review_required"},
        "proof_posture": {
            "verified_public",
            "verified_private_anonymize",
            "owner_confirmation_required",
            "principle_only",
            "missing",
        },
    }
    for key, allowed in enums.items():
        if key in compacted and compacted[key] not in allowed:
            raise ValueError(f"weekly_plan.recommendations[{index}].{key} is not allowlisted.")
    return compacted


def _compact_weekly_publishing_board_card(value: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"weekly_plan.{field} must contain receipt objects.")
    allowed = {
        "schema_version",
        "board_role",
        "canonical_pillar",
        "intent",
        "treatment",
        "employer_safety",
        "proof_posture",
        "exact_copy_bound",
        "critic_status",
        "owner_decision_state",
        "approval_completed",
        "publication_confirmed",
        "performance_state",
        "lifecycle_state",
        "next_action",
    }
    if set(value) - allowed:
        raise ValueError(f"weekly_plan.{field} contains non-lifecycle content.")
    schema_version = _weekly_projection_text(
        value.get("schema_version"),
        field=f"{field}.schema_version",
        max_length=80,
        required=True,
    )
    if schema_version != "feezie_publishing_board_card/v1":
        raise ValueError(f"weekly_plan.{field} has an unsupported receipt schema.")
    compacted: dict[str, Any] = {"schema_version": schema_version}
    for key, limit in (
        ("board_role", 40),
        ("canonical_pillar", 160),
        ("intent", 40),
        ("treatment", 120),
        ("employer_safety", 80),
        ("proof_posture", 80),
        ("critic_status", 80),
        ("owner_decision_state", 80),
        ("performance_state", 80),
        ("lifecycle_state", 80),
        ("next_action", 160),
    ):
        text = _weekly_projection_text(value.get(key), field=f"{field}.{key}", max_length=limit)
        if text is not None:
            compacted[key] = text
    for key in ("exact_copy_bound", "approval_completed", "publication_confirmed"):
        raw = value.get(key)
        if not isinstance(raw, bool):
            raise ValueError(f"weekly_plan.{field}.{key} must be boolean.")
        compacted[key] = raw
    if compacted["publication_confirmed"] and not compacted["approval_completed"]:
        raise ValueError(f"weekly_plan.{field} cannot confirm publication before approval.")
    return compacted


def _compact_weekly_publishing_board(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("weekly_plan.publishing_board is required.")
    allowed = {
        "schema_version",
        "window_days",
        "primary",
        "backup",
        "developing",
        "publication_authority",
        "may_publish_fewer",
        "exact_copy_rule",
    }
    if set(value) - allowed:
        raise ValueError("weekly_plan.publishing_board contains unsupported content.")
    if value.get("schema_version") != "feezie_seven_day_publishing_board/v1":
        raise ValueError("weekly_plan.publishing_board has an unsupported schema.")
    window_days = value.get("window_days")
    if isinstance(window_days, bool) or not isinstance(window_days, int) or not 1 <= window_days <= 14:
        raise ValueError("weekly_plan.publishing_board.window_days is invalid.")
    compacted: dict[str, Any] = {
        "schema_version": "feezie_seven_day_publishing_board/v1",
        "window_days": window_days,
    }
    for key, limit in (("primary", 3), ("backup", 3), ("developing", 3)):
        items = value.get(key)
        if not isinstance(items, list) or len(items) > limit:
            raise ValueError(f"weekly_plan.publishing_board.{key} must be bounded.")
        compacted[key] = [
            _compact_weekly_publishing_board_card(item, field=f"publishing_board.{key}[{index}]")
            for index, item in enumerate(items)
        ]
    authority = _weekly_projection_text(
        value.get("publication_authority"),
        field="publishing_board.publication_authority",
        max_length=40,
        required=True,
    )
    if authority != "owner_only" or not isinstance(value.get("may_publish_fewer"), bool):
        raise ValueError("weekly_plan.publishing_board authority policy is invalid.")
    compacted["publication_authority"] = authority
    compacted["may_publish_fewer"] = value["may_publish_fewer"]
    exact_copy_rule = _weekly_projection_text(
        value.get("exact_copy_rule"),
        field="publishing_board.exact_copy_rule",
        max_length=600,
        required=True,
    )
    compacted["exact_copy_rule"] = exact_copy_rule
    return compacted


def _compact_weekly_aggregate_value(value: Any, *, field: str, depth: int = 0) -> Any:
    if depth > 6:
        raise ValueError(f"weekly_plan.{field} exceeds the aggregate depth limit.")
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        if not -1_000_000 <= value <= 1_000_000:
            raise ValueError(f"weekly_plan.{field} contains an unbounded integer.")
        return value
    if isinstance(value, float):
        if not math.isfinite(value) or not -1_000_000 <= value <= 1_000_000:
            raise ValueError(f"weekly_plan.{field} contains an unbounded number.")
        return value
    if isinstance(value, str):
        return _weekly_projection_text(value, field=field, max_length=240)
    if isinstance(value, list):
        if len(value) > 24:
            raise ValueError(f"weekly_plan.{field} contains an oversized aggregate list.")
        return [
            _compact_weekly_aggregate_value(item, field=f"{field}[{index}]", depth=depth + 1)
            for index, item in enumerate(value)
        ]
    if isinstance(value, dict):
        if len(value) > 40:
            raise ValueError(f"weekly_plan.{field} contains an oversized aggregate map.")
        compacted: dict[str, Any] = {}
        for raw_key, item in value.items():
            key = str(raw_key or "").strip()
            if (
                not key
                or len(key) > 80
                or re.fullmatch(r"[A-Za-z0-9_.:-]+", key) is None
                or key.lower() in _WEEKLY_PRIVATE_FIELD_NAMES
            ):
                raise ValueError(f"weekly_plan.{field} contains a private or invalid aggregate field.")
            compacted[key] = _compact_weekly_aggregate_value(
                item,
                field=f"{field}.{key}",
                depth=depth + 1,
            )
        return compacted
    raise ValueError(f"weekly_plan.{field} contains an unsupported aggregate value.")


def _compact_weekly_portfolio_learning(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("weekly_plan.portfolio_learning is required.")
    if set(value) - _WEEKLY_PORTFOLIO_LEARNING_KEYS:
        raise ValueError("weekly_plan.portfolio_learning contains non-aggregate content.")
    if value.get("schema_version") != "feezie_portfolio_learning_receipt/v1":
        raise ValueError("weekly_plan.portfolio_learning has an unsupported schema.")
    compacted = _compact_weekly_aggregate_value(value, field="portfolio_learning")
    if not isinstance(compacted, dict):
        raise ValueError("weekly_plan.portfolio_learning could not be compacted.")
    decision_policy = compacted.get("decision_policy")
    if not isinstance(decision_policy, dict):
        raise ValueError("weekly_plan.portfolio_learning.decision_policy is required.")
    if decision_policy.get("strategy_contract_mutation_allowed") is not False:
        raise ValueError("weekly_plan.portfolio_learning cannot authorize strategy mutation.")
    return compacted


def compact_and_validate_weekly_plan_projection(
    value: Any,
    *,
    envelope_generated_at: str,
) -> dict[str, Any]:
    """Return the closed, public-safe weekly plan projection accepted from the Mac."""

    if not isinstance(value, dict):
        raise ValueError("weekly_plan must be an object.")
    unsupported = set(value) - _WEEKLY_PLAN_TOP_LEVEL_KEYS
    if unsupported:
        raise ValueError("weekly_plan contains unsupported or private top-level fields.")
    if value.get("schema_version") != FEEZIE_WEEKLY_PLAN_PROJECTION_SCHEMA:
        raise ValueError("weekly_plan has an unsupported projection schema.")
    if value.get("generated_at") != envelope_generated_at:
        raise ValueError("weekly_plan generated_at must exactly match the sync envelope.")
    if value.get("workspace") not in {WORKSPACE_KEY, "workspaces/linkedin-content-os"}:
        raise ValueError("weekly_plan workspace identity is invalid.")
    recommendations = value.get("recommendations")
    if not isinstance(recommendations, list) or len(recommendations) > 5:
        raise ValueError("weekly_plan recommendations must contain at most five items.")
    compacted_recommendations = [
        _compact_weekly_recommendation(item, index=index)
        for index, item in enumerate(recommendations)
    ]
    development_card_count = value.get("development_card_count")
    if (
        isinstance(development_card_count, bool)
        or not isinstance(development_card_count, int)
        or not 0 <= development_card_count <= min(3, len(compacted_recommendations))
    ):
        raise ValueError("weekly_plan development_card_count is invalid.")
    if value.get("data_policy") != FEEZIE_WEEKLY_PLAN_DATA_POLICY:
        raise ValueError("weekly_plan data_policy does not match the public-safe projection contract.")

    compacted = {
        "schema_version": FEEZIE_WEEKLY_PLAN_PROJECTION_SCHEMA,
        "generated_at": envelope_generated_at,
        "workspace": WORKSPACE_KEY,
        "strategy_contract": _compact_weekly_strategy_contract(value.get("strategy_contract")),
        "positioning_model": _weekly_projection_text_list(
            value.get("positioning_model"),
            field="positioning_model",
            max_items=8,
            max_length=320,
        ),
        "priority_lanes": _weekly_projection_text_list(
            value.get("priority_lanes"),
            field="priority_lanes",
            max_items=8,
            max_length=200,
        ),
        "pillar_coverage": _compact_weekly_pillar_coverage(value.get("pillar_coverage")),
        "development_card_count": development_card_count,
        "recommendations": compacted_recommendations,
        "publishing_board": _compact_weekly_publishing_board(value.get("publishing_board")),
        "portfolio_learning": _compact_weekly_portfolio_learning(value.get("portfolio_learning")),
        "source_counts": _weekly_projection_counts(value.get("source_counts"), field="source_counts"),
        "data_policy": dict(FEEZIE_WEEKLY_PLAN_DATA_POLICY),
    }
    encoded = json.dumps(compacted, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    if len(encoded) > 128 * 1024:
        raise ValueError("weekly_plan projection exceeds the 128 KB compacted limit.")
    return compacted

ACTIVITY_STAGE_ORDER = {
    "owner_review": 0,
    "latent_seed": 1,
    "post_seed": 2,
    "weekly_plan": 3,
    "source": 4,
}


def _normalize_activity_key(value: Any) -> str:
    raw = str(value or "").strip()
    root_prefix = f"{ROOT.resolve().as_posix().rstrip('/')}/"
    if raw.startswith(root_prefix):
        raw = raw.removeprefix(root_prefix)
    raw = re.sub(r"^Source file:\s*", "", raw, flags=re.IGNORECASE)
    raw = raw.lstrip("./")
    return raw.lower()


def _activity_keys(*values: Any) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _normalize_activity_key(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return tuple(ordered)


def _activity_stage_metadata(stage: str) -> dict[str, Any]:
    if stage == "owner_review":
        return {
            "label": "Owner review",
            "detail": "Already drafted. The next decision is approve, revise, or park.",
            "action_label": "Open owner review",
            "tone": "#fbbf24",
            "allowed_actions": ["approve", "revise", "park", "annotate_notes"],
        }
    if stage == "weekly_plan":
        return {
            "label": "Weekly plan",
            "detail": "Already selected for the active weekly plan.",
            "action_label": "Use planned seed",
            "tone": "#38bdf8",
            "allowed_actions": ["use_in_pipeline", "write_post", "write_comment", "copy", "feedback", "approve_quote"],
        }
    if stage == "post_seed":
        return {
            "label": "Banked seed",
            "detail": "Already stored in the standalone post-seed lane.",
            "action_label": "Use banked seed",
            "tone": "#22c55e",
            "allowed_actions": ["use_in_pipeline", "write_post", "write_comment", "copy", "feedback", "approve_quote"],
        }
    if stage == "latent_seed":
        return {
            "label": "Needs anecdote",
            "detail": "Already preserved as a latent seed that needs proof, taste, or an anecdote.",
            "action_label": "Work latent seed",
            "tone": "#fb923c",
            "allowed_actions": ["use_in_pipeline", "write_post", "write_comment", "copy", "feedback", "approve_quote"],
        }
    return {
        "label": "Source",
        "detail": "React to it, draft from it, or push the strongest angle into the pipeline.",
        "action_label": "Use in pipeline",
        "tone": "#fb923c",
        "allowed_actions": ["use_in_pipeline", "write_post", "write_comment", "copy", "feedback", "approve_quote"],
    }


def _build_activity_planning_index(
    *,
    owner_review_items: list[dict[str, Any]],
    weekly_plan: dict[str, Any] | None,
    reaction_queue: dict[str, Any] | None,
) -> dict[str, set[str]]:
    index = {
        "owner_review_titles": set(),
        "owner_review_urls": set(),
        "owner_review_paths": set(),
        "weekly_titles": set(),
        "weekly_paths": set(),
        "post_seed_titles": set(),
        "post_seed_paths": set(),
        "latent_seed_titles": set(),
        "latent_seed_paths": set(),
    }

    for item in owner_review_items:
        index["owner_review_titles"].update(_activity_keys(item.get("title")))
        index["owner_review_urls"].update(_activity_keys(item.get("source_url")))
        index["owner_review_paths"].update(_activity_keys(item.get("source_path")))

    for item in (weekly_plan or {}).get("recommendations") or []:
        index["weekly_titles"].update(_activity_keys(item.get("title")))
        index["weekly_paths"].update(_activity_keys(item.get("source_path")))

    for item in (reaction_queue or {}).get("post_seeds") or []:
        index["post_seed_titles"].update(_activity_keys(item.get("title")))
        index["post_seed_paths"].update(_activity_keys(item.get("source_path")))

    for item in (reaction_queue or {}).get("latent_post_seeds") or []:
        index["latent_seed_titles"].update(_activity_keys(item.get("title")))
        index["latent_seed_paths"].update(_activity_keys(item.get("source_path")))

    return index


def _resolve_activity_stage_for_source_item(item: dict[str, Any], index: dict[str, set[str]]) -> str:
    title_keys = _activity_keys(item.get("title"))
    url_keys = _activity_keys(item.get("source_url"))
    path_keys = _activity_keys(item.get("source_path"))

    if (
        any(key in index["owner_review_titles"] for key in title_keys)
        or any(key in index["owner_review_urls"] for key in url_keys)
        or any(key in index["owner_review_paths"] for key in path_keys)
    ):
        return "owner_review"
    if any(key in index["weekly_titles"] for key in title_keys) or any(key in index["weekly_paths"] for key in path_keys):
        return "weekly_plan"
    if any(key in index["post_seed_titles"] for key in title_keys) or any(key in index["post_seed_paths"] for key in path_keys):
        return "post_seed"
    if any(key in index["latent_seed_titles"] for key in title_keys) or any(key in index["latent_seed_paths"] for key in path_keys):
        return "latent_seed"
    return "source"


def _build_activity_feed_payload(
    *,
    social_feed: dict[str, Any] | None,
    weekly_plan: dict[str, Any] | None,
    reaction_queue: dict[str, Any] | None,
) -> dict[str, Any] | None:
    items = (social_feed or {}).get("items") or []
    if not isinstance(items, list):
        items = []

    try:
        from app.services.linkedin_owner_review_service import list_owner_review_items

        owner_review_payload = list_owner_review_items()
        owner_review_items = owner_review_payload.get("items") or []
    except Exception:
        owner_review_items = []

    planning_index = _build_activity_planning_index(
        owner_review_items=owner_review_items if isinstance(owner_review_items, list) else [],
        weekly_plan=weekly_plan if isinstance(weekly_plan, dict) else None,
        reaction_queue=reaction_queue if isinstance(reaction_queue, dict) else None,
    )

    feed_index: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        for key in _activity_keys(item.get("title"), item.get("source_url"), item.get("source_path")):
            feed_index.setdefault(key, []).append(item)

    matched_feed_ids: set[str] = set()
    activity_items: list[dict[str, Any]] = []

    for owner_review_item in owner_review_items if isinstance(owner_review_items, list) else []:
        if not isinstance(owner_review_item, dict):
            continue
        matched_feed_item: dict[str, Any] | None = None
        for key in _activity_keys(
            owner_review_item.get("title"),
            owner_review_item.get("source_url"),
            owner_review_item.get("source_path"),
        ):
            candidates = feed_index.get(key) or []
            unmatched = [
                candidate
                for candidate in candidates
                if str(candidate.get("id") or "").strip() and str(candidate.get("id") or "").strip() not in matched_feed_ids
            ]
            if unmatched:
                matched_feed_item = max(
                    unmatched,
                    key=lambda candidate: float(((candidate.get("ranking") or {}).get("total") or 0.0)),
                )
                matched_feed_ids.add(str(matched_feed_item.get("id") or "").strip())
                break

        stage = "owner_review"
        stage_meta = _activity_stage_metadata(stage)
        activity_items.append(
            {
                "id": f"activity:{owner_review_item.get('queue_id') or owner_review_item.get('title')}",
                "kind": "owner_review",
                "stage": stage,
                "stage_order": ACTIVITY_STAGE_ORDER[stage],
                "stage_label": stage_meta["label"],
                "stage_detail": stage_meta["detail"],
                "action_label": stage_meta["action_label"],
                "tone": stage_meta["tone"],
                "allowed_actions": stage_meta["allowed_actions"],
                "source_key": "|".join(
                    _activity_keys(
                        owner_review_item.get("title"),
                        owner_review_item.get("source_url"),
                        owner_review_item.get("source_path"),
                    )
                ),
                "title": owner_review_item.get("title"),
                "author": matched_feed_item.get("author") if matched_feed_item else None,
                "source_url": owner_review_item.get("source_url") or (matched_feed_item.get("source_url") if matched_feed_item else None),
                "source_path": owner_review_item.get("source_path") or (matched_feed_item.get("source_path") if matched_feed_item else None),
                "queue_id": owner_review_item.get("queue_id"),
                "draft_path": owner_review_item.get("draft_path"),
                "owner_packet_path": owner_review_item.get("owner_packet_path"),
                "status_summary": owner_review_item.get("approval_status") or owner_review_item.get("status"),
                "ranking_total": (
                    ((matched_feed_item or {}).get("ranking") or {}).get("total")
                    if isinstance(matched_feed_item, dict)
                    else None
                ),
                "feed_item": matched_feed_item,
                "owner_review_item": owner_review_item,
            }
        )

    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or "").strip()
        if item_id and item_id in matched_feed_ids:
            continue
        stage = _resolve_activity_stage_for_source_item(item, planning_index)
        stage_meta = _activity_stage_metadata(stage)
        activity_items.append(
            {
                "id": f"activity:{item_id or item.get('title')}",
                "kind": "source",
                "stage": stage,
                "stage_order": ACTIVITY_STAGE_ORDER.get(stage, ACTIVITY_STAGE_ORDER["source"]),
                "stage_label": stage_meta["label"],
                "stage_detail": stage_meta["detail"],
                "action_label": stage_meta["action_label"],
                "tone": stage_meta["tone"],
                "allowed_actions": stage_meta["allowed_actions"],
                "source_key": "|".join(_activity_keys(item.get("title"), item.get("source_url"), item.get("source_path"))),
                "title": item.get("title"),
                "author": item.get("author"),
                "source_url": item.get("source_url"),
                "source_path": item.get("source_path"),
                "queue_id": None,
                "draft_path": None,
                "owner_packet_path": None,
                "status_summary": stage_meta["label"],
                "ranking_total": ((item.get("ranking") or {}).get("total") if isinstance(item.get("ranking"), dict) else None),
                "feed_item": item,
                "owner_review_item": None,
            }
        )

    if not activity_items:
        return None

    def _sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
        stage = str(item.get("stage") or "source")
        raw_stage_order = item.get("stage_order")
        stage_order = int(raw_stage_order) if isinstance(raw_stage_order, (int, float)) else ACTIVITY_STAGE_ORDER["source"]
        if stage == "owner_review":
            queue_id = str(item.get("queue_id") or "")
            title = str(item.get("title") or "")
            return (stage_order, 0, queue_id or title.lower())
        ranking_total = item.get("ranking_total")
        score = float(ranking_total) if isinstance(ranking_total, (float, int)) else 0.0
        return (stage_order, 1, -score, str(item.get("title") or "").lower())

    activity_items.sort(key=_sort_key)

    counts: dict[str, int] = {}
    for item in activity_items:
        stage = str(item.get("stage") or "source")
        counts[stage] = counts.get(stage, 0) + 1

    generated_at = (
        (social_feed or {}).get("generated_at")
        or (weekly_plan or {}).get("generated_at")
        or (reaction_queue or {}).get("generated_at")
        or datetime.now(timezone.utc).isoformat()
    )
    return {
        "generated_at": generated_at,
        "total_count": len(activity_items),
        "counts": counts,
        "items": activity_items,
    }


def _load_module(module_name: str, script_path: Path) -> Any | None:
    if not script_path.exists():
        return None
    script_dir = str(script_path.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _first_meaningful_line(raw: str) -> str:
    return next(
        (
            line
            for line in (segment.strip() for segment in raw.splitlines())
            if line and not line.startswith("#")
        ),
        "",
    )


def _walk(dir_path: Path) -> list[Path]:
    if not dir_path.exists():
        return []
    results: list[Path] = []
    for entry in sorted(dir_path.iterdir(), key=lambda item: item.name):
        if entry.is_dir():
            results.extend(_walk(entry))
        else:
            results.append(entry)
    return results


def _display_path_from_workspace_root(file_path: Path) -> str:
    try:
        return file_path.relative_to(ROOT).as_posix()
    except ValueError:
        try:
            return file_path.resolve().relative_to(ROOT.resolve()).as_posix()
        except ValueError:
            return file_path.as_posix()


def _serialize_file(
    file_path: Path,
    root: Path,
    label: str,
    display_root: str | None = None,
) -> dict[str, str]:
    relative_to_root = file_path.relative_to(root).as_posix()
    relative_path = (
        (Path(display_root) / relative_to_root).as_posix()
        if display_root
        else _display_path_from_workspace_root(file_path)
    )
    segments = relative_to_root.split("/")
    group = f"{label}/{segments[0]}" if len(segments) > 1 else label
    raw = file_path.read_text(encoding="utf-8")
    stat = file_path.stat()
    return {
        "group": group,
        "name": file_path.name,
        "path": relative_path,
        "snippet": _first_meaningful_line(raw),
        "content": raw,
        "updatedAt": datetime.fromtimestamp(stat.st_mtime).isoformat(),
    }


def _load_workspace_files() -> list[dict[str, str]]:
    files_by_key: dict[tuple[str, str], dict[str, str]] = {}
    for root, label, display_root in _workspace_file_roots():
        if not root.exists():
            continue
        for file_path in _walk(root):
            if file_path.suffix not in {".md", ".json"}:
                continue
            relative_to_root = file_path.relative_to(root).as_posix()
            files_by_key.setdefault(
                (label, relative_to_root),
                _serialize_file(file_path, root, label, display_root),
            )
    return list(files_by_key.values())


def _doc_path_is_excluded(display_path: str) -> bool:
    relative = Path(display_path)
    lowered_parts = tuple(part.lower() for part in relative.parts)
    if any(part in _DOC_EXCLUDED_DIRECTORY_NAMES for part in lowered_parts):
        return True
    normalized = relative.as_posix().lower()
    return any(marker in normalized for marker in _DOC_RETIRED_PATH_MARKERS)


def _doc_authority_metadata(display_path: str, group: str) -> dict[str, Any]:
    authority_by_path = {
        "SOURCE_OF_TRUTH.md": ("binding", "active"),
        "CODEX_STARTUP.md": ("operating", "active"),
        "AGENTS.md": ("operating", "active"),
        "IDENTITY.md": ("identity", "active"),
        "CHARTER.md": ("identity", "active"),
        "SOUL.md": ("identity", "active"),
        "USER.md": ("identity", "active"),
        "MEMORY.md": ("durable_guardrails", "active"),
        "memory/persistent_state.md": ("current_context", "active"),
        "memory/roadmap.md": ("directional", "directional"),
        "SOPs/_index.md": ("procedure_registry", "active"),
    }
    default_authority = "procedural" if group == "Operating Docs" else "supporting"
    default_status = "indexed" if group == "Operating Docs" else "reference"
    authority, status = authority_by_path.get(display_path, (default_authority, default_status))
    return {
        "authority": authority,
        "status": status,
        "readOrder": PINNED_DOC_PATHS.index(display_path) if display_path in PINNED_DOC_PATHS else None,
    }


def _load_doc_entries() -> list[dict[str, Any]]:
    """Compatibility inventory for Workspace; Ops/Brain use /api/brain/docs."""

    entries_by_path: dict[str, dict[str, Any]] = {}
    for root, label in _doc_root_candidates():
        for file_path in _walk(root):
            if file_path.suffix != ".md":
                continue
            entry = _serialize_file(file_path, root, label)
            if _doc_path_is_excluded(entry["path"]):
                continue
            entry["group"] = label
            entry.update(_doc_authority_metadata(entry["path"], label))
            entries_by_path[entry["path"]] = entry

    for file_path, label in _doc_target_candidates():
        raw = file_path.read_text(encoding="utf-8")
        stat = file_path.stat()
        relative_path = _display_path_from_workspace_root(file_path)
        if _doc_path_is_excluded(relative_path):
            continue
        entries_by_path[relative_path] = {
            "name": file_path.name,
            "path": relative_path,
            "snippet": _first_meaningful_line(raw),
            "content": raw,
            "updatedAt": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "group": label,
            **_doc_authority_metadata(relative_path, label),
        }

    entries = list(entries_by_path.values())
    entries.sort(
        key=lambda item: (
            0 if item["path"] in PINNED_DOC_PATHS else 1,
            PINNED_DOC_PATHS.index(item["path"]) if item["path"] in PINNED_DOC_PATHS else 999,
            item["path"],
        )
    )
    return entries


def _snapshot_collection_payload(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workspace": WORKSPACE_KEY,
        "items": items,
        "counts": {"total": len(items)},
    }


def _privacy_safe_inventory_payload(snapshot_type: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    """Reduce file snapshots to aggregate inventory before persistence or API projection.

    Workspace files and operating documents can contain private drafts, memory,
    dispatch packets, and analytics notes.  Their bodies, snippets, names, and
    paths are local-only; Railway and browser responses receive counts only.
    """

    source = payload if isinstance(payload, dict) else {}
    items = source.get("items") if isinstance(source.get("items"), list) else []
    counts = source.get("counts") if isinstance(source.get("counts"), dict) else {}
    raw_total = counts.get("total")
    total = int(raw_total) if isinstance(raw_total, (int, float)) and raw_total >= 0 else len(items)
    detected_redacted_item_count = sum(
        1
        for item in items
        if isinstance(item, dict)
        and any(item.get(key) not in (None, "") for key in ("content", "snippet", "name", "path"))
    )
    prior_redacted_count = counts.get("redacted_item_count")
    redacted_item_count = (
        int(prior_redacted_count)
        if isinstance(prior_redacted_count, (int, float)) and prior_redacted_count >= 0
        else detected_redacted_item_count
    )
    generated_at = str(source.get("generated_at") or "").strip() or datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": PRIVATE_INVENTORY_SCHEMA,
        "generated_at": generated_at,
        "workspace": WORKSPACE_KEY,
        "inventory_kind": snapshot_type,
        "items": [],
        "counts": {
            "total": total,
            "browser_visible_items": 0,
            "redacted_item_count": redacted_item_count,
        },
        "data_policy": {
            "projection": "aggregate_only",
            "raw_content_included": False,
            "snippets_included": False,
            "file_names_included": False,
            "file_paths_included": False,
        },
    }


def _browser_status_timestamp(value: Any) -> str | None:
    """Return a canonical timestamp without forwarding untrusted source text."""

    parsed: datetime
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _browser_grounding_count(snapshot_type: str, payload: dict[str, Any]) -> int:
    counts = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
    raw_total = counts.get("total")
    if isinstance(raw_total, int) and not isinstance(raw_total, bool) and 0 <= raw_total <= 1_000_000:
        return raw_total

    direct_count_keys = {
        SNAPSHOT_LONG_FORM_ROUTES: "segments_total",
    }
    direct_key = direct_count_keys.get(snapshot_type)
    if direct_key:
        raw_direct = payload.get(direct_key)
        if isinstance(raw_direct, int) and not isinstance(raw_direct, bool) and 0 <= raw_direct <= 1_000_000:
            return raw_direct

    collection_keys = {
        SNAPSHOT_SOURCE_ASSETS: "items",
        SNAPSHOT_CONTENT_RESERVOIR: "items",
        SNAPSHOT_OPERATOR_STORY_SIGNALS: "signals",
        SNAPSHOT_CONTENT_SAFE_OPERATOR_LESSONS: "lessons",
        SNAPSHOT_PERSONA_REVIEW_SUMMARY: "recent",
        SNAPSHOT_LONG_FORM_ROUTES: "candidates",
    }
    collection = payload.get(collection_keys[snapshot_type])
    return min(len(collection), 1_000_000) if isinstance(collection, list) else 0


def _browser_private_grounding_projection(snapshot_type: str, payload: Any) -> dict[str, Any]:
    """Project private grounding state through a closed aggregate-only schema."""

    available = isinstance(payload, dict)
    state = "available" if available else "missing" if payload is None else "invalid"
    source = payload if available else {}
    source_counts = source.get("counts") if isinstance(source.get("counts"), dict) else {}
    projected_counts = {
        "total": _browser_grounding_count(snapshot_type, source),
    }
    for key in BROWSER_PRIVATE_GROUNDING_COUNT_KEYS.get(snapshot_type, ()):
        raw_value = source_counts.get(key)
        if isinstance(raw_value, int) and not isinstance(raw_value, bool) and 0 <= raw_value <= 1_000_000:
            projected_counts[key] = raw_value
    return {
        "schema_version": BROWSER_PRIVATE_GROUNDING_SCHEMA,
        "snapshot_type": snapshot_type,
        "state": state,
        "available": available,
        "generated_at": _browser_status_timestamp(source.get("generated_at")),
        "counts": projected_counts,
        "data_policy": {
            "projection": "aggregate_status_only",
            "raw_content_included": False,
            "names_included": False,
            "identifiers_or_hashes_included": False,
            "filenames_included": False,
            "paths_included": False,
            "excerpts_included": False,
        },
    }


def _browser_weekly_strategy_freshness(value: Any) -> dict[str, Any] | None:
    """Return only bounded strategy freshness state and approved identifiers."""

    if not isinstance(value, dict):
        return None
    state = value.get("state")
    if state not in {"current", "stale", "legacy", "unavailable"}:
        return None
    compacted: dict[str, Any] = {"state": state}
    for key in ("planned_hash", "current_hash"):
        raw_hash = value.get(key)
        if raw_hash is None:
            compacted[key] = None
        elif isinstance(raw_hash, str) and re.fullmatch(r"[a-f0-9]{64}", raw_hash.lower()):
            compacted[key] = raw_hash.lower()
        else:
            compacted[key] = None
    compacted["approved_at"] = _browser_status_timestamp(value.get("approved_at"))
    if compacted["approved_at"] is None:
        approved_date = value.get("approved_at")
        if isinstance(approved_date, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", approved_date.strip()):
            compacted["approved_at"] = approved_date.strip()
    compacted["checked_at"] = _browser_status_timestamp(value.get("checked_at"))
    return compacted


def _bounded_browser_collection_count(value: Any, *, maximum: int = 1_000) -> int:
    if not isinstance(value, list):
        return 0
    return min(len(value), maximum)


def _legacy_weekly_plan_browser_projection(payload: Any) -> dict[str, Any]:
    """Reduce an old or invalid weekly plan to status/counts without forwarding rows."""

    source = payload if isinstance(payload, dict) else {}
    board = source.get("publishing_board") if isinstance(source.get("publishing_board"), dict) else {}
    source_counts = source.get("source_counts") if isinstance(source.get("source_counts"), dict) else {}
    safe_source_counts: dict[str, int] = {}
    for key in ("drafts", "media", "research", "total"):
        raw_count = source_counts.get(key)
        if isinstance(raw_count, int) and not isinstance(raw_count, bool) and 0 <= raw_count <= 1_000_000:
            safe_source_counts[key] = raw_count
    development_card_count = source.get("development_card_count")
    if (
        isinstance(development_card_count, bool)
        or not isinstance(development_card_count, int)
        or not 0 <= development_card_count <= 3
    ):
        development_card_count = 0
    projected = {
        "schema_version": FEEZIE_WEEKLY_PLAN_LEGACY_BROWSER_SCHEMA,
        "state": "legacy_redacted" if isinstance(payload, dict) else "missing",
        "generated_at": _browser_status_timestamp(source.get("generated_at")),
        "workspace": WORKSPACE_KEY,
        "positioning_model": [],
        "priority_lanes": [],
        "pillar_coverage": {
            "counts": {},
            "unmapped_count": 0,
            "missing_pillars": [],
            "warnings": [],
        },
        "development_card_count": development_card_count,
        "recommendation_count": _bounded_browser_collection_count(source.get("recommendations")),
        "recommendations": [],
        "publishing_board": {
            "schema_version": "feezie_publishing_board_browser_status/v1",
            "counts": {
                key: _bounded_browser_collection_count(board.get(key), maximum=3)
                for key in ("primary", "backup", "developing")
            },
        },
        "portfolio_learning": {},
        "source_counts": safe_source_counts,
        "data_policy": dict(FEEZIE_WEEKLY_PLAN_LEGACY_BROWSER_DATA_POLICY),
    }
    freshness = _browser_weekly_strategy_freshness(source.get("strategy_contract_freshness"))
    if freshness is not None:
        projected["strategy_contract_freshness"] = freshness
    return projected


def _browser_weekly_plan_projection(payload: Any) -> dict[str, Any]:
    """Keep signed narrow plans useful and redact all legacy weekly-plan rows."""

    if not isinstance(payload, dict) or payload.get("schema_version") != FEEZIE_WEEKLY_PLAN_PROJECTION_SCHEMA:
        return _legacy_weekly_plan_browser_projection(payload)
    source = dict(payload)
    raw_freshness = source.pop("strategy_contract_freshness", None)
    generated_at = source.get("generated_at")
    if not isinstance(generated_at, str):
        return _legacy_weekly_plan_browser_projection(payload)
    try:
        projected = compact_and_validate_weekly_plan_projection(
            source,
            envelope_generated_at=generated_at,
        )
    except (TypeError, ValueError):
        return _legacy_weekly_plan_browser_projection(payload)
    freshness = _browser_weekly_strategy_freshness(raw_freshness)
    if freshness is not None:
        projected["strategy_contract_freshness"] = freshness
    return projected


def project_linkedin_os_snapshot_for_browser(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Return the authenticated browser projection without private grounding rows."""

    if not isinstance(snapshot, dict):
        raise TypeError("Workspace snapshot must be a mapping.")
    projected = dict(snapshot)
    projected[SNAPSHOT_WEEKLY_PLAN] = _browser_weekly_plan_projection(snapshot.get(SNAPSHOT_WEEKLY_PLAN))
    for snapshot_type in BROWSER_PRIVATE_GROUNDING_SNAPSHOT_TYPES:
        projected[snapshot_type] = _browser_private_grounding_projection(
            snapshot_type,
            snapshot.get(snapshot_type),
        )
    return projected


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _read_text(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _load_operator_story_signals_payload() -> dict[str, Any] | None:
    payload = _load_json(
        _memory_report_read_path(
            OPERATOR_STORY_SIGNALS_LOGICAL_REF,
            OPERATOR_STORY_SIGNALS_PATH,
        )
    )
    return payload if _snapshot_is_usable(SNAPSHOT_OPERATOR_STORY_SIGNALS, payload or {}) else None


def _load_content_safe_operator_lessons_payload() -> dict[str, Any] | None:
    payload = _load_json(
        _memory_report_read_path(
            CONTENT_SAFE_OPERATOR_LESSONS_LOGICAL_REF,
            CONTENT_SAFE_OPERATOR_LESSONS_PATH,
        )
    )
    if not _snapshot_is_usable(SNAPSHOT_CONTENT_SAFE_OPERATOR_LESSONS, payload or {}):
        try:
            from app.services.content_safe_operator_lesson_service import (
                build_content_safe_operator_lessons_payload,
            )

            payload = build_content_safe_operator_lessons_payload()
        except Exception:
            # A missing or malformed private input must degrade to unavailable;
            # snapshot consumers can retain their last known-good projection.
            payload = None
    return payload if _snapshot_is_usable(SNAPSHOT_CONTENT_SAFE_OPERATOR_LESSONS, payload or {}) else None


def _extract_markdown_section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    start = text.find(marker)
    if start == -1:
        return ""
    section = text[start + len(marker) :].lstrip()
    next_heading = section.find("\n## ")
    if next_heading != -1:
        section = section[:next_heading]
    return section.strip()


def _split_markdown_blocks(section: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"^###\s+(.+)$", section, flags=re.MULTILINE))
    blocks: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(section)
        blocks.append((match.group(1).strip(), section[start:end].strip()))
    return blocks


def _clean_markdown_value(value: str) -> str:
    cleaned = value.strip()
    if cleaned.startswith("`") and cleaned.endswith("`"):
        cleaned = cleaned[1:-1]
    return "" if cleaned == "-" else cleaned


def _parse_markdown_fields(block: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    current_key: str | None = None
    for raw_line in block.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped.startswith("- ") and ":" in stripped:
            key, value = stripped[2:].split(":", 1)
            current_key = key.strip().lower()
            fields[current_key] = _clean_markdown_value(value)
            continue
        if current_key and line.startswith("  ") and stripped:
            existing = fields.get(current_key, "")
            fields[current_key] = f"{existing}\n{stripped}".strip()
    return fields


def _parse_pillar_coverage_markdown(text: str) -> dict[str, Any] | None:
    section = _extract_markdown_section(text, "Canonical Pillar Coverage")
    if not section:
        return None

    counts_text, _, warnings_text = section.partition("### Coverage Warnings")
    counts: dict[str, int] = {}
    for raw_line in counts_text.splitlines():
        stripped = raw_line.strip()
        if not stripped.startswith("- ") or ":" not in stripped:
            continue
        label, raw_count = stripped[2:].rsplit(":", 1)
        try:
            count = int(raw_count.strip())
        except ValueError:
            continue
        clean_label = label.strip()
        if clean_label:
            counts[clean_label] = count

    warnings = [
        raw_line.strip()[2:].strip()
        for raw_line in warnings_text.splitlines()
        if raw_line.strip().startswith("- ") and raw_line.strip()[2:].strip()
    ]
    if not counts and not warnings:
        return None
    return {
        "counts": counts,
        "missing_pillars": [pillar for pillar, count in counts.items() if count == 0],
        "warnings": warnings,
    }


def _parse_weekly_plan_markdown(path: Path) -> dict[str, Any] | None:
    text = _read_text(path)
    if not text:
        return None
    generated_match = re.search(r"^Generated:\s+(.+)$", text, flags=re.MULTILINE)
    strategy_contract_fields = _parse_markdown_fields(
        _extract_markdown_section(text, "Strategy Contract")
    )
    strategy_contract = {
        "schema_version": strategy_contract_fields.get("schema", ""),
        "contract_hash": strategy_contract_fields.get("contract hash", ""),
    }
    strategy_contract = {
        key: value
        for key, value in strategy_contract.items()
        if value
    }
    recommendations = []
    for heading, block in _split_markdown_blocks(_extract_markdown_section(text, "Recommended Posts")):
        fields = _parse_markdown_fields(block)
        title = re.sub(r"^\d+\.\s*", "", heading).strip()
        why_now = fields.get("why now", "")
        recommendations.append(
            {
                "source_kind": fields.get("source", ""),
                "title": title,
                "category": fields.get("category", ""),
                "role_alignment": fields.get("role alignment", ""),
                "risk_level": fields.get("risk level", ""),
                "publish_posture": fields.get("publish posture", ""),
                "hook": fields.get("hook", ""),
                "rationale": why_now,
                "why_now": why_now,
                "source_path": fields.get("source file", ""),
                "score": 0,
                "priority_lane": fields.get("priority lane", ""),
                "canonical_pillar": fields.get("canonical pillar", ""),
                "career_signal": fields.get("career signal", ""),
                "employer_proximity": fields.get("employer proximity", ""),
                "employer_safety": fields.get("employer safety", ""),
                "proof_posture": fields.get("proof posture", ""),
                "audience": fields.get("audience", ""),
                "audience_consequence": fields.get("audience consequence", ""),
                "distinct_thesis": fields.get("distinct thesis", ""),
                "development_status": fields.get("development status", ""),
            }
        )
    market_signals = []
    for heading, block in _split_markdown_blocks(_extract_markdown_section(text, "Market Signals")):
        fields = _parse_markdown_fields(block)
        market_signals.append(
            {
                "source_kind": fields.get("source", ""),
                "title": heading,
                "theme": fields.get("theme", ""),
                "priority_lane": fields.get("priority lane", ""),
                "role_alignment": fields.get("role alignment", ""),
                "summary": fields.get("what the market is saying", ""),
                "pain_points": [item.strip() for item in fields.get("pain points", "").split(",") if item.strip()],
                "language_patterns": [item.strip() for item in fields.get("language patterns", "").split(",") if item.strip()],
                "headline_candidates": [item.strip() for item in fields.get("hook candidates", "").split(",") if item.strip()],
                "source_path": fields.get("source file", ""),
            }
        )
    positioning_model = [line[2:].strip() for line in _extract_markdown_section(text, "Positioning Model").splitlines() if line.startswith("- ")]
    priority_lanes = [line[2:].strip() for line in _extract_markdown_section(text, "This Week's Priority Lanes").splitlines() if line.startswith("- ")]
    research_notes = [line[2:].strip("`") for line in _extract_markdown_section(text, "Research Feed").splitlines() if line.startswith("- ")]
    pillar_coverage = _parse_pillar_coverage_markdown(text)
    linkedin_root = _discover_linkedin_root()
    draft_count = len([path for path in (linkedin_root / "drafts").glob("*.md") if path.name != "README.md" and not path.name.startswith("queue_")])
    payload = {
        "generated_at": generated_match.group(1).strip() if generated_match else None,
        "workspace": "workspaces/linkedin-content-os",
        "positioning_model": positioning_model,
        "priority_lanes": priority_lanes,
        "recommendations": recommendations,
        "hold_items": [],
        "market_signals": market_signals,
        "research_notes": research_notes,
        "source_counts": {
            "drafts": draft_count,
            "media": 0,
            "research": len(market_signals),
        },
    }
    if strategy_contract:
        payload["strategy_contract"] = strategy_contract
    if pillar_coverage:
        payload["pillar_coverage"] = pillar_coverage
    return payload


def _long_form_plan_candidate(candidate: dict[str, Any], *, source_kind: str) -> dict[str, Any]:
    lane_hint = str(candidate.get("lane_hint") or "").strip()
    title = str(candidate.get("title") or "Long-form source").strip() or "Long-form source"
    segment = str(candidate.get("segment") or "").strip()
    route_reason = str(candidate.get("route_reason") or "").strip()
    belief_summary = str(candidate.get("belief_summary") or "").strip()
    rationale = route_reason
    if belief_summary:
        rationale = f"{route_reason} Belief: {belief_summary}.".strip()
    return {
        "source_kind": source_kind,
        "title": title,
        "category": "Long-form media",
        "role_alignment": "operator clarity",
        "risk_level": "review",
        "publish_posture": "draft",
        "hook": segment,
        "rationale": rationale,
        "source_path": str(candidate.get("source_path") or ""),
        "score": int(candidate.get("route_score") or 0),
        "priority_lane": lane_hint,
        "source_url": str(candidate.get("source_url") or ""),
        "target_file": str(candidate.get("target_file") or ""),
        "route_reason": route_reason,
        "response_modes": list(candidate.get("response_modes") or []),
        "handoff_lane": str(candidate.get("handoff_lane") or ""),
        "handoff_reason": str(candidate.get("handoff_reason") or ""),
        "secondary_consumers": list(candidate.get("secondary_consumers") or []),
    }


def _augment_weekly_plan_payload(payload: dict[str, Any] | None, long_form_routes: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return payload
    # A signed FEEZIE weekly projection is already the complete, closed
    # browser-safe contract.  The legacy long-form overlay adds source rows and
    # changes generated_at, so applying it here would make a valid projection
    # fail closed as a legacy plan at the browser boundary.
    if payload.get("schema_version") == FEEZIE_WEEKLY_PLAN_PROJECTION_SCHEMA:
        return payload
    if not isinstance(long_form_routes, dict):
        return payload

    candidates = long_form_routes.get("candidates")
    if not isinstance(candidates, list):
        return payload

    def _candidate_lane(candidate: dict[str, Any]) -> str:
        handoff_lane = str(candidate.get("handoff_lane") or "").strip()
        if handoff_lane:
            return handoff_lane
        primary_route = str(candidate.get("primary_route") or "").strip()
        if primary_route == "post_seed":
            return "post_candidate"
        if primary_route == "belief_evidence":
            return "persona_candidate"
        return primary_route

    media_post_seeds = [
        _long_form_plan_candidate(candidate, source_kind="long_form_post_seed")
        for candidate in candidates
        if isinstance(candidate, dict) and _candidate_lane(candidate) == "post_candidate"
    ][:6]
    brief_awareness_candidates = [
        _long_form_plan_candidate(candidate, source_kind="long_form_brief_awareness")
        for candidate in candidates
        if isinstance(candidate, dict) and _candidate_lane(candidate) == "brief_only"
    ][:6]
    belief_evidence_candidates = [
        _long_form_plan_candidate(candidate, source_kind="long_form_belief_evidence")
        for candidate in candidates
        if isinstance(candidate, dict) and _candidate_lane(candidate) == "persona_candidate"
    ][:6]
    operational_route_candidates = [
        _long_form_plan_candidate(candidate, source_kind="long_form_route_to_pm")
        for candidate in candidates
        if isinstance(candidate, dict) and _candidate_lane(candidate) == "route_to_pm"
    ][:6]

    counts = payload.get("source_counts")
    counts_dict = dict(counts) if isinstance(counts, dict) else {}
    counts_dict["media"] = len(media_post_seeds)
    counts_dict["brief_only"] = len(brief_awareness_candidates)
    counts_dict["belief_evidence"] = len(belief_evidence_candidates)
    counts_dict["route_to_pm"] = len(operational_route_candidates)

    augmented = dict(payload)
    base_generated_at = payload.get("generated_at")
    route_generated_at = long_form_routes.get("generated_at")
    has_route_overlay = bool(media_post_seeds or brief_awareness_candidates or belief_evidence_candidates or operational_route_candidates)
    if has_route_overlay:
        augmented["base_generated_at"] = base_generated_at
        augmented["generated_at"] = route_generated_at or base_generated_at
    augmented["source_counts"] = counts_dict
    augmented["media_post_seeds"] = media_post_seeds
    augmented["brief_awareness_candidates"] = brief_awareness_candidates
    augmented["belief_evidence_candidates"] = belief_evidence_candidates
    augmented["operational_route_candidates"] = operational_route_candidates
    augmented["media_summary"] = {
        "generated_at": route_generated_at,
        "assets_considered": int(long_form_routes.get("assets_considered") or 0),
        "segments_total": int(long_form_routes.get("segments_total") or 0),
        "route_counts": long_form_routes.get("route_counts") or {},
        "primary_route_counts": long_form_routes.get("primary_route_counts") or {},
        "handoff_lane_counts": long_form_routes.get("handoff_lane_counts") or {},
    }
    return augmented


def _parse_reaction_queue_markdown(path: Path) -> dict[str, Any] | None:
    text = _read_text(path)
    if not text:
        return None
    generated_match = re.search(r"^Generated:\s+(.+)$", text, flags=re.MULTILINE)
    comment_opportunities = []
    for heading, block in _split_markdown_blocks(_extract_markdown_section(text, "Immediate Comment Opportunities")):
        fields = _parse_markdown_fields(block)
        comment_opportunities.append(
            {
                "title": heading,
                "author": fields.get("source", "").split("/", 1)[1].strip() if "/" in fields.get("source", "") else "",
                "source_platform": fields.get("source", "").split("/", 1)[0].strip("` ").lower() if fields.get("source") else "",
                "source_type": "post",
                "source_url": "",
                "source_path": fields.get("source file", ""),
                "priority_lane": fields.get("lane", ""),
                "role_alignment": "",
                "risk_level": "",
                "publish_posture": "",
                "recommended_move": fields.get("move", ""),
                "hook": fields.get("hook to react to", ""),
                "summary": fields.get("why this matters", ""),
                "why_it_matters": fields.get("why this matters", ""),
                "comment_angle": fields.get("comment angle", ""),
                "suggested_comment": fields.get("suggested comment", "").replace("\n", " ").strip(),
                "post_angle": "",
                "score": 0,
            }
        )
    post_seeds = []
    for heading, block in _split_markdown_blocks(_extract_markdown_section(text, "Standalone Post Seeds")):
        fields = _parse_markdown_fields(block)
        post_seeds.append(
            {
                "title": heading,
                "author": "",
                "source_platform": "",
                "source_type": "",
                "source_url": "",
                "source_path": fields.get("source file", ""),
                "priority_lane": "",
                "role_alignment": fields.get("role alignment", ""),
                "risk_level": fields.get("risk", ""),
                "publish_posture": "",
                "recommended_move": "save_for_post",
                "hook": "",
                "summary": fields.get("post angle", ""),
                "why_it_matters": "",
                "comment_angle": "",
                "suggested_comment": "",
                "post_angle": fields.get("post angle", ""),
                "score": 0,
            }
        )
    return {
        "generated_at": generated_match.group(1).strip() if generated_match else None,
        "workspace": "workspaces/linkedin-content-os",
        "comment_opportunities": comment_opportunities,
        "post_seeds": post_seeds,
        "background_only": [],
        "counts": {
            "comment_opportunities": len(comment_opportunities),
            "post_seeds": len(post_seeds),
            "background_only": 0,
        },
    }


def _parse_social_feed_markdown(path: Path) -> dict[str, Any] | None:
    text = _read_text(path)
    if not text:
        return None
    updated_match = re.search(r"^Updated\s+(.+)$", text, flags=re.MULTILINE)
    return {
        "generated_at": updated_match.group(1).strip() if updated_match else None,
        "workspace": "linkedin-content-os",
        "strategy_mode": "production",
        "items": [],
    }


def _ingestions_root() -> Path:
    direct = _find_richest_dir("knowledge/ingestions", "backend/knowledge/ingestions", pattern="normalized.md")
    if direct:
        return direct
    return ROOT / "knowledge" / "ingestions"


def _transcripts_root() -> Path:
    direct = _find_richest_dir(
        "knowledge/aiclone/transcripts",
        "backend/knowledge/aiclone/transcripts",
        pattern="*.md",
        exclude_names=TRANSCRIPT_LIBRARY_SKIP_NAMES,
    )
    if direct:
        return direct
    return ROOT / "knowledge" / "aiclone" / "transcripts"


def _build_weekly_plan_payload() -> dict[str, Any] | None:
    linkedin_root = _discover_linkedin_root()
    script_path = _find_file(
        "backend/scripts/personal-brand/generate_linkedin_weekly_plan.py",
        "scripts/personal-brand/generate_linkedin_weekly_plan.py",
    )
    module = _load_module("generate_linkedin_weekly_plan_runtime", script_path) if script_path else None
    if module is None or not linkedin_root.exists():
        return None
    if hasattr(module, "build_weekly_plan"):
        payload = module.build_weekly_plan(linkedin_root)
    else:
        draft_candidates, draft_source_refs = module.load_draft_candidates(linkedin_root)
        media_candidates = module.load_media_candidates(_ingestions_root())
        research_candidates, research_signals, research_notes = module.load_research_candidates(linkedin_root)
        filtered_research_candidates = [item for item in research_candidates if item.source_path not in draft_source_refs]
        all_candidates = sorted(draft_candidates + media_candidates + filtered_research_candidates, key=lambda item: (-item.score, item.title.lower()))
        recommendations = [item for item in all_candidates if item.publish_posture != "hold_private"][:5]
        hold_items = [item for item in all_candidates if item.publish_posture == "hold_private" or item.risk_level == "high"][:10]
        payload = module.plan_payload(
            workspace_dir=linkedin_root,
            recommendations=recommendations,
            hold_items=hold_items,
            research_signals=research_signals,
            research_notes=research_notes,
            counts={
                "drafts": len(draft_candidates),
                "media": len(media_candidates),
                "research": len(filtered_research_candidates),
            },
        )
    long_form_routes = _current_long_form_routes_payload()
    return _augment_weekly_plan_payload(payload, long_form_routes)


def _build_reaction_queue_payload() -> dict[str, Any] | None:
    linkedin_root = _discover_linkedin_root()
    script_path = _find_file(
        "backend/scripts/personal-brand/generate_linkedin_reaction_queue.py",
        "scripts/personal-brand/generate_linkedin_reaction_queue.py",
    )
    module = _load_module("generate_linkedin_reaction_queue_runtime", script_path) if script_path else None
    if module is None or not linkedin_root.exists():
        return None
    items = module.load_market_signal_items(linkedin_root)[:8]
    return module.queue_payload(linkedin_root, items)


def _build_social_feed_payload() -> dict[str, Any] | None:
    linkedin_root = _discover_linkedin_root()
    try:
        payload = build_social_feed_runtime_payload(linkedin_root)
    except Exception:
        return None
    return payload if _snapshot_is_usable(SNAPSHOT_SOCIAL_FEED, payload) else None


def _build_source_assets_payload() -> dict[str, Any] | None:
    try:
        payload = build_source_asset_inventory(
            transcripts_root=_transcripts_root(),
            ingestions_root=_ingestions_root(),
            repo_root=ROOT,
        )
    except Exception:
        payload = None

    if _snapshot_is_usable(SNAPSHOT_SOURCE_ASSETS, payload or {}):
        items = payload.get("items") or []
        if items:
            return payload

    fallback = _build_source_assets_from_persona_review()
    if _snapshot_is_usable(SNAPSHOT_SOURCE_ASSETS, fallback or {}):
        return fallback
    return payload if _snapshot_is_usable(SNAPSHOT_SOURCE_ASSETS, payload or {}) else None


def _build_long_form_routes_payload() -> dict[str, Any] | None:
    try:
        source_assets_payload = _load_snapshot(SNAPSHOT_SOURCE_ASSETS)
        payload = build_long_form_route_summary(
            repo_root=ROOT,
            source_assets=source_assets_payload,
            transcripts_root=_transcripts_root(),
            ingestions_root=_ingestions_root(),
        )
    except Exception:
        return None
    return payload if _snapshot_is_usable(SNAPSHOT_LONG_FORM_ROUTES, payload) else None


def _current_long_form_routes_payload() -> dict[str, Any] | None:
    runtime = _build_long_form_routes_payload()
    if runtime:
        return runtime
    persisted = get_snapshot_payload(WORKSPACE_KEY, SNAPSHOT_LONG_FORM_ROUTES)
    return persisted if persisted and _snapshot_is_usable(SNAPSHOT_LONG_FORM_ROUTES, persisted) else None


def _build_content_reservoir_payload() -> dict[str, Any] | None:
    source_assets_payload = _load_snapshot(SNAPSHOT_SOURCE_ASSETS)
    if not source_assets_payload:
        source_assets_payload = _build_source_assets_payload()
    try:
        payload = build_content_reservoir_payload(source_assets=source_assets_payload)
    except Exception:
        return None
    return payload if _snapshot_is_usable(SNAPSHOT_CONTENT_RESERVOIR, payload or {}) else None


def _load_feedback_summary_payload() -> dict[str, Any] | None:
    linkedin_root = _discover_linkedin_root()
    try:
        return social_feedback_service.load_summary()
    except Exception:
        return _load_json(linkedin_root / "analytics" / "feed_feedback_summary.json")


def _load_publication_performance_payload() -> dict[str, Any] | None:
    # Corruption must remain observable.  The caller converts it into a
    # privacy-safe status snapshot without replacing the last good summary.
    return linkedin_performance_ledger_service.load_summary()


def _metadata_text(metadata: dict[str, Any] | None, key: str) -> str | None:
    if not isinstance(metadata, dict):
        return None
    value = metadata.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _metadata_bool(metadata: dict[str, Any] | None, key: str) -> bool:
    if not isinstance(metadata, dict):
        return False
    value = metadata.get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _metadata_array(metadata: dict[str, Any] | None, key: str) -> list[Any]:
    if not isinstance(metadata, dict):
        return []
    value = metadata.get(key)
    return value if isinstance(value, list) else []


def _has_selectable_promotion_metadata(metadata: dict[str, Any] | None) -> bool:
    return any(
        _metadata_array(metadata, key)
        for key in ("talking_points", "frameworks", "anecdotes", "phrase_candidates", "stats")
    )


def _is_brain_pending_review(status: str, metadata: dict[str, Any] | None) -> bool:
    normalized = (status or "draft").strip().lower()
    review_source = _metadata_text(metadata, "review_source")
    if review_source == "long_form_media.segment":
        sync_state = _metadata_text(metadata, "sync_state") or ""
        primary_route = _metadata_text(metadata, "primary_route")
        if sync_state.startswith("stale_"):
            return False
        if _metadata_bool(metadata, "weak_source_fragment"):
            return False
        if primary_route and primary_route != "belief_evidence":
            return False
    if normalized in {"draft", "pending", "in_review"}:
        return True
    return normalized == "reviewed" and _has_selectable_promotion_metadata(metadata) and not _metadata_bool(metadata, "pending_promotion")


def _is_workspace_approved(status: str, metadata: dict[str, Any] | None) -> bool:
    normalized = (status or "draft").strip().lower()
    review_source = _metadata_text(metadata, "review_source")
    approval_state = _metadata_text(metadata, "approval_state")
    return normalized == "approved" and (
        review_source == "linkedin_workspace.feed_quote" or approval_state == "approved_from_workspace"
    )


def _persona_review_stage(status: str, metadata: dict[str, Any] | None) -> str:
    normalized = (status or "draft").strip().lower()
    if normalized == "committed":
        return "committed"
    if _metadata_bool(metadata, "pending_promotion"):
        return "pending_promotion"
    if _is_workspace_approved(normalized, metadata):
        return "workspace_saved"
    if _is_brain_pending_review(normalized, metadata):
        return "brain_pending_review"
    if normalized == "approved":
        return "approved_unpromoted"
    return normalized or "draft"


def _build_persona_review_summary_from_deltas(
    deltas: list[Any],
    *,
    sync_result: dict[str, Any] | None = None,
) -> dict[str, Any]:

    stage_counts = {
        "brain_pending_review": 0,
        "workspace_saved": 0,
        "approved_unpromoted": 0,
        "pending_promotion": 0,
        "committed": 0,
    }
    status_counts: dict[str, int] = {}
    review_source_counts: dict[str, int] = {}
    target_file_counts: dict[str, int] = {}
    belief_relation_counts: dict[str, int] = {}
    recent: list[dict[str, Any]] = []

    for delta in deltas:
        metadata = delta.metadata if isinstance(delta.metadata, dict) else {}
        status = (delta.status or "draft").strip().lower()
        stage = _persona_review_stage(status, metadata)
        if stage in stage_counts:
            stage_counts[stage] += 1
        status_counts[status] = status_counts.get(status, 0) + 1

        review_source = _metadata_text(metadata, "review_source") or "unknown"
        review_source_counts[review_source] = review_source_counts.get(review_source, 0) + 1

        target_file = _metadata_text(metadata, "target_file")
        if target_file:
            target_file_counts[target_file] = target_file_counts.get(target_file, 0) + 1

        belief_relation = _metadata_text(metadata, "belief_relation")
        if belief_relation:
            belief_relation_counts[belief_relation] = belief_relation_counts.get(belief_relation, 0) + 1

        if len(recent) < 12:
            recent.append(
                {
                    "id": delta.id,
                    "trait": delta.trait,
                    "persona_target": delta.persona_target,
                    "status": status,
                    "stage": stage,
                    "review_source": review_source,
                    "target_file": target_file,
                    "belief_relation": belief_relation,
                    "approval_state": _metadata_text(metadata, "approval_state"),
                    "created_at": delta.created_at.isoformat() if delta.created_at else None,
                    "committed_at": delta.committed_at.isoformat() if delta.committed_at else None,
                }
            )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workspace": WORKSPACE_KEY,
        "counts": {
            "total": len(deltas),
            **stage_counts,
        },
        "status_counts": status_counts,
        "review_source_counts": review_source_counts,
        "target_file_counts": target_file_counts,
        "belief_relation_counts": belief_relation_counts,
        "recent": recent,
        "long_form_sync": sync_result or {
            "assets_considered": 0,
            "created_count": 0,
            "skipped_existing": 0,
            "skipped_no_segments": 0,
            "resolved_stale": 0,
            "created": [],
        },
    }


def _build_persona_review_summary_payload() -> dict[str, Any] | None:
    sync_result: dict[str, Any] | None = None
    source_assets_payload = _load_snapshot(SNAPSHOT_SOURCE_ASSETS)
    if source_assets_payload:
        try:
            sync_result = social_persona_review_service.sync_long_form_worldview_reviews(
                repo_root=ROOT,
                source_assets=source_assets_payload,
                transcripts_root=_transcripts_root(),
                ingestions_root=_ingestions_root(),
            )
        except Exception:
            sync_result = None

    try:
        # This filesystem-capable compatibility path cannot prove a global
        # total once the bounded read is full.  Refuse to publish a seemingly
        # current partial summary; the DB-owned command below performs the
        # exact aggregate used by Railway.
        deltas = persona_delta_service.list_deltas(limit=201)
    except Exception:
        return None
    if len(deltas) > 200:
        return None
    return _build_persona_review_summary_from_deltas(deltas, sync_result=sync_result)


def _snapshot_payload_sha256(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


_PERSONA_REVIEW_DB_AGGREGATE_SQL = """
    WITH normalized AS (
        SELECT
            id::text AS id,
            COALESCE(persona_target, 'unknown') AS persona_target,
            COALESCE(trait, '') AS trait,
            COALESCE(NULLIF(LOWER(BTRIM(status)), ''), 'draft') AS normalized_status,
            COALESCE(metadata, '{}'::jsonb) AS metadata,
            created_at,
            committed_at
        FROM persona_deltas
    ),
    flags AS (
        SELECT
            *,
            COALESCE(NULLIF(BTRIM(metadata->>'review_source'), ''), 'unknown') AS review_source,
            NULLIF(BTRIM(metadata->>'target_file'), '') AS target_file,
            NULLIF(BTRIM(metadata->>'belief_relation'), '') AS belief_relation,
            NULLIF(BTRIM(metadata->>'approval_state'), '') AS approval_state,
            NULLIF(BTRIM(metadata->>'sync_state'), '') AS sync_state,
            NULLIF(BTRIM(metadata->>'primary_route'), '') AS primary_route,
            CASE jsonb_typeof(metadata->'pending_promotion')
                WHEN 'boolean' THEN (metadata->>'pending_promotion')::boolean
                WHEN 'string' THEN LOWER(BTRIM(metadata->>'pending_promotion')) IN ('1', 'true', 'yes', 'y', 'on')
                WHEN 'number' THEN (metadata->>'pending_promotion')::numeric <> 0
                WHEN 'array' THEN jsonb_array_length(metadata->'pending_promotion') > 0
                WHEN 'object' THEN metadata->'pending_promotion' <> '{}'::jsonb
                ELSE FALSE
            END AS pending_promotion,
            CASE jsonb_typeof(metadata->'weak_source_fragment')
                WHEN 'boolean' THEN (metadata->>'weak_source_fragment')::boolean
                WHEN 'string' THEN LOWER(BTRIM(metadata->>'weak_source_fragment')) IN ('1', 'true', 'yes', 'y', 'on')
                WHEN 'number' THEN (metadata->>'weak_source_fragment')::numeric <> 0
                WHEN 'array' THEN jsonb_array_length(metadata->'weak_source_fragment') > 0
                WHEN 'object' THEN metadata->'weak_source_fragment' <> '{}'::jsonb
                ELSE FALSE
            END AS weak_source_fragment,
            (
                CASE WHEN jsonb_typeof(metadata->'talking_points') = 'array'
                    THEN jsonb_array_length(metadata->'talking_points') ELSE 0 END > 0
                OR CASE WHEN jsonb_typeof(metadata->'frameworks') = 'array'
                    THEN jsonb_array_length(metadata->'frameworks') ELSE 0 END > 0
                OR CASE WHEN jsonb_typeof(metadata->'anecdotes') = 'array'
                    THEN jsonb_array_length(metadata->'anecdotes') ELSE 0 END > 0
                OR CASE WHEN jsonb_typeof(metadata->'phrase_candidates') = 'array'
                    THEN jsonb_array_length(metadata->'phrase_candidates') ELSE 0 END > 0
                OR CASE WHEN jsonb_typeof(metadata->'stats') = 'array'
                    THEN jsonb_array_length(metadata->'stats') ELSE 0 END > 0
            ) AS has_selectable_promotion_metadata
        FROM normalized
    ),
    classified AS (
        SELECT
            *,
            CASE
                WHEN normalized_status = 'committed' THEN 'committed'
                WHEN pending_promotion THEN 'pending_promotion'
                WHEN normalized_status = 'approved'
                    AND (
                        review_source = 'linkedin_workspace.feed_quote'
                        OR approval_state = 'approved_from_workspace'
                    ) THEN 'workspace_saved'
                WHEN NOT (
                    review_source = 'long_form_media.segment'
                    AND (
                        COALESCE(sync_state, '') LIKE 'stale\\_%' ESCAPE '\\'
                        OR weak_source_fragment
                        OR (primary_route IS NOT NULL AND primary_route <> 'belief_evidence')
                    )
                ) AND (
                    normalized_status IN ('draft', 'pending', 'in_review')
                    OR (
                        normalized_status = 'reviewed'
                        AND has_selectable_promotion_metadata
                        AND NOT pending_promotion
                    )
                ) THEN 'brain_pending_review'
                WHEN normalized_status = 'approved' THEN 'approved_unpromoted'
                ELSE normalized_status
            END AS stage
        FROM flags
    )
    SELECT
        (SELECT COUNT(*)::bigint FROM classified) AS total,
        COALESCE((
            SELECT jsonb_object_agg(grouped.item_key, grouped.item_count)
            FROM (
                SELECT stage AS item_key, COUNT(*)::bigint AS item_count
                FROM classified
                GROUP BY stage
            ) AS grouped
        ), '{}'::jsonb) AS stage_counts,
        COALESCE((
            SELECT jsonb_object_agg(grouped.item_key, grouped.item_count)
            FROM (
                SELECT normalized_status AS item_key, COUNT(*)::bigint AS item_count
                FROM classified
                GROUP BY normalized_status
            ) AS grouped
        ), '{}'::jsonb) AS status_counts,
        COALESCE((
            SELECT jsonb_object_agg(grouped.item_key, grouped.item_count)
            FROM (
                SELECT review_source AS item_key, COUNT(*)::bigint AS item_count
                FROM classified
                GROUP BY review_source
            ) AS grouped
        ), '{}'::jsonb) AS review_source_counts,
        COALESCE((
            SELECT jsonb_object_agg(grouped.item_key, grouped.item_count)
            FROM (
                SELECT target_file AS item_key, COUNT(*)::bigint AS item_count
                FROM classified
                WHERE target_file IS NOT NULL
                GROUP BY target_file
            ) AS grouped
        ), '{}'::jsonb) AS target_file_counts,
        COALESCE((
            SELECT jsonb_object_agg(grouped.item_key, grouped.item_count)
            FROM (
                SELECT belief_relation AS item_key, COUNT(*)::bigint AS item_count
                FROM classified
                WHERE belief_relation IS NOT NULL
                GROUP BY belief_relation
            ) AS grouped
        ), '{}'::jsonb) AS belief_relation_counts,
        COALESCE((
            SELECT jsonb_agg(
                jsonb_build_object(
                    'id', recent.id,
                    'trait', recent.trait,
                    'persona_target', recent.persona_target,
                    'status', recent.normalized_status,
                    'stage', recent.stage,
                    'review_source', recent.review_source,
                    'target_file', recent.target_file,
                    'belief_relation', recent.belief_relation,
                    'approval_state', recent.approval_state,
                    'created_at', recent.created_at,
                    'committed_at', recent.committed_at
                )
                ORDER BY recent.created_at DESC NULLS LAST, recent.id DESC
            )
            FROM (
                SELECT *
                FROM classified
                ORDER BY created_at DESC NULLS LAST, id DESC
                LIMIT 12
            ) AS recent
        ), '[]'::jsonb) AS recent,
        clock_timestamp() AS observation_generated_at
"""


_PERSONA_REVIEW_MONOTONIC_UPSERT_SQL = """
    INSERT INTO workspace_snapshots (id, workspace_key, snapshot_type, payload, metadata)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (workspace_key, snapshot_type) DO UPDATE
    SET payload = EXCLUDED.payload,
        metadata = COALESCE(workspace_snapshots.metadata, '{}'::jsonb) || EXCLUDED.metadata,
        updated_at = NOW()
    WHERE CASE
        WHEN COALESCE(workspace_snapshots.payload->>'generated_at', '') ~
             '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}'
        THEN (workspace_snapshots.payload->>'generated_at')::timestamptz
        ELSE '-infinity'::timestamptz
    END < %s
    RETURNING id, workspace_key, snapshot_type, payload, metadata, created_at, updated_at
"""


def _validated_persona_refresh_request_generated_at(value: str) -> datetime:
    if not isinstance(value, str) or not value.strip() or len(value) > 64:
        raise ValueError("Persona refresh request_generated_at must be a bounded ISO-8601 timestamp.")
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("Persona refresh request_generated_at must be a valid ISO-8601 timestamp.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Persona refresh request_generated_at must be timezone-aware.")
    parsed = parsed.astimezone(timezone.utc)
    if parsed > datetime.now(timezone.utc) + timedelta(hours=1):
        raise ValueError("Persona refresh request_generated_at is too far in the future.")
    return parsed


def _exact_count_map(value: Any, *, label: str) -> dict[str, int]:
    if not isinstance(value, dict):
        raise RuntimeError(f"Persona review aggregate {label} is unavailable.")
    counts: dict[str, int] = {}
    for raw_key, raw_count in value.items():
        if isinstance(raw_count, bool):
            raise RuntimeError(f"Persona review aggregate {label} is invalid.")
        try:
            count = int(raw_count)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"Persona review aggregate {label} is invalid.") from exc
        if count < 0:
            raise RuntimeError(f"Persona review aggregate {label} is invalid.")
        counts[str(raw_key)] = count
    return counts


def _build_db_owned_persona_review_summary(aggregate: Any) -> tuple[dict[str, Any], datetime]:
    if not isinstance(aggregate, dict):
        raise RuntimeError("Persona review aggregate is unavailable.")
    raw_total = aggregate.get("total")
    if isinstance(raw_total, bool):
        raise RuntimeError("Persona review aggregate total is invalid.")
    try:
        total = int(raw_total)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Persona review aggregate total is invalid.") from exc
    if total < 0:
        raise RuntimeError("Persona review aggregate total is invalid.")

    stage_counts = _exact_count_map(aggregate.get("stage_counts"), label="stage_counts")
    status_counts = _exact_count_map(aggregate.get("status_counts"), label="status_counts")
    review_source_counts = _exact_count_map(
        aggregate.get("review_source_counts"),
        label="review_source_counts",
    )
    target_file_counts = _exact_count_map(
        aggregate.get("target_file_counts"),
        label="target_file_counts",
    )
    belief_relation_counts = _exact_count_map(
        aggregate.get("belief_relation_counts"),
        label="belief_relation_counts",
    )
    if (
        sum(stage_counts.values()) != total
        or sum(status_counts.values()) != total
        or sum(review_source_counts.values()) != total
    ):
        raise RuntimeError("Persona review aggregate completeness check failed.")

    recent = aggregate.get("recent")
    if (
        not isinstance(recent, list)
        or len(recent) != min(total, 12)
        or any(not isinstance(item, dict) for item in recent)
    ):
        raise RuntimeError("Persona review aggregate recent rows are invalid.")

    observed_at = aggregate.get("observation_generated_at")
    if isinstance(observed_at, str):
        normalized_observed_at = observed_at[:-1] + "+00:00" if observed_at.endswith("Z") else observed_at
        try:
            observed_at = datetime.fromisoformat(normalized_observed_at)
        except ValueError as exc:
            raise RuntimeError("Persona review observation timestamp is invalid.") from exc
    if not isinstance(observed_at, datetime) or observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise RuntimeError("Persona review observation timestamp is invalid.")
    observed_at = observed_at.astimezone(timezone.utc)

    payload = {
        "generated_at": observed_at.isoformat(),
        "workspace": WORKSPACE_KEY,
        "counts": {
            "total": total,
            "brain_pending_review": stage_counts.get("brain_pending_review", 0),
            "workspace_saved": stage_counts.get("workspace_saved", 0),
            "approved_unpromoted": stage_counts.get("approved_unpromoted", 0),
            "pending_promotion": stage_counts.get("pending_promotion", 0),
            "committed": stage_counts.get("committed", 0),
        },
        "status_counts": status_counts,
        "review_source_counts": review_source_counts,
        "target_file_counts": target_file_counts,
        "belief_relation_counts": belief_relation_counts,
        "recent": recent,
        "long_form_sync": {
            "assets_considered": 0,
            "created_count": 0,
            "skipped_existing": 0,
            "skipped_no_segments": 0,
            "resolved_stale": 0,
            "created": [],
        },
    }
    return payload, observed_at


def _load_exact_persona_review_summary(cursor: Any) -> tuple[dict[str, Any], datetime]:
    cursor.execute(_PERSONA_REVIEW_DB_AGGREGATE_SQL)
    return _build_db_owned_persona_review_summary(cursor.fetchone())


def _snapshot_row_from_db(row: Any) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    return {
        "id": str(row.get("id") or ""),
        "workspace_key": row.get("workspace_key"),
        "snapshot_type": row.get("snapshot_type"),
        "payload": row.get("payload") or {},
        "metadata": row.get("metadata") or {},
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _upsert_persona_review_summary_monotonic(
    cursor: Any,
    payload: dict[str, Any],
    *,
    observation_generated_at: datetime,
    request_generated_at: str,
) -> tuple[dict[str, Any] | None, bool]:
    cursor.execute(
        _PERSONA_REVIEW_MONOTONIC_UPSERT_SQL,
        (
            str(uuid4()),
            WORKSPACE_KEY,
            SNAPSHOT_PERSONA_REVIEW_SUMMARY,
            Jsonb(payload),
            Jsonb(
                {
                    "source": "db_owned_persona_review_refresh",
                    "payload_generated_at": payload.get("generated_at"),
                    "request_generated_at": request_generated_at,
                }
            ),
            observation_generated_at,
        ),
    )
    stored_row = cursor.fetchone()
    if stored_row is not None:
        return _snapshot_row_from_db(stored_row), True

    cursor.execute(
        """
        SELECT id, workspace_key, snapshot_type, payload, metadata, created_at, updated_at
        FROM workspace_snapshots
        WHERE workspace_key = %s AND snapshot_type = %s
        """,
        (WORKSPACE_KEY, SNAPSHOT_PERSONA_REVIEW_SUMMARY),
    )
    return _snapshot_row_from_db(cursor.fetchone()), False


def _build_source_assets_from_persona_review() -> dict[str, Any] | None:
    try:
        deltas = persona_delta_service.list_deltas(limit=400)
    except Exception:
        return None

    items_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for delta in deltas:
        metadata = delta.metadata if isinstance(delta.metadata, dict) else {}
        if _metadata_text(metadata, "review_source") != "long_form_media.segment":
            continue

        asset_id = _metadata_text(metadata, "source_asset_id")
        source_path = _metadata_text(metadata, "source_path")
        source_url = _metadata_text(metadata, "source_url")
        evidence_source = _metadata_text(metadata, "evidence_source") or asset_id or source_path or "Long-form source"
        key = (asset_id or source_path or evidence_source, source_path or "", source_url or "")
        existing = items_by_key.get(key)

        candidate = {
            "asset_id": asset_id or f"review-derived-{len(items_by_key) + 1}",
            "title": evidence_source,
            "source_class": _metadata_text(metadata, "source_class") or "long_form_media",
            "source_channel": _metadata_text(metadata, "source_channel") or "unknown",
            "source_type": _metadata_text(metadata, "source_type") or "review_segment",
            "source_url": source_url or "",
            "author": "",
            "captured_at": delta.created_at.isoformat() if delta.created_at else None,
            "source_path": source_path or "",
            "raw_path": "",
            "summary": _metadata_text(metadata, "segment_excerpt") or evidence_source,
            "topics": [],
            "tags": ["review_derived"],
            "response_modes": ["post_seed", "belief_evidence"],
            "routing_status": "review_backfill",
            "feed_ready": False,
            "segmentation_ready": False,
            "origin": "persona_review_backfill",
            "word_count": None,
        }
        if existing is None:
            items_by_key[key] = candidate
            continue

        existing_created = existing.get("captured_at") or ""
        candidate_created = candidate.get("captured_at") or ""
        if candidate_created > existing_created:
            items_by_key[key] = candidate

    items = sorted(
        items_by_key.values(),
        key=lambda item: ((item.get("captured_at") or ""), str(item.get("title") or "").lower()),
        reverse=True,
    )
    if not items:
        return None

    by_channel: dict[str, int] = {}
    for item in items:
        channel = _clean_markdown_value(str(item.get("source_channel") or "")) or "unknown"
        by_channel[channel] = by_channel.get(channel, 0) + 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workspace": WORKSPACE_KEY,
        "items": items,
        "counts": {
            "total": len(items),
            "long_form_media": len(items),
            "pending_segmentation": 0,
            "feed_ready": 0,
            "by_channel": by_channel,
        },
        "backfill_source": "persona_review_summary",
    }


def _runtime_snapshot_payload(snapshot_type: str) -> dict[str, Any] | None:
    linkedin_root = _discover_linkedin_root()
    if snapshot_type == SNAPSHOT_WEEKLY_PLAN:
        payload = (
            _build_weekly_plan_payload()
            or _load_json(linkedin_root / "plans" / "weekly_plan.json")
            or _parse_weekly_plan_markdown(linkedin_root / "plans" / "weekly_plan.md")
        )
        long_form_routes = _current_long_form_routes_payload()
        return _augment_weekly_plan_payload(payload, long_form_routes)
    if snapshot_type == SNAPSHOT_REACTION_QUEUE:
        return (
            _build_reaction_queue_payload()
            or _load_json(linkedin_root / "plans" / "reaction_queue.json")
            or _parse_reaction_queue_markdown(linkedin_root / "plans" / "reaction_queue.md")
        )
    if snapshot_type == SNAPSHOT_SOCIAL_FEED:
        built = _build_social_feed_payload()
        if built:
            return built
        json_payload = _load_json(linkedin_root / "plans" / "social_feed.json")
        if json_payload and _snapshot_is_usable(SNAPSHOT_SOCIAL_FEED, json_payload):
            return json_payload
        markdown_payload = _parse_social_feed_markdown(linkedin_root / "plans" / "social_feed.md")
        if markdown_payload and _snapshot_is_usable(SNAPSHOT_SOCIAL_FEED, markdown_payload):
            return markdown_payload
        return None
    if snapshot_type == SNAPSHOT_FEEDBACK_SUMMARY:
        return _load_feedback_summary_payload()
    if snapshot_type == SNAPSHOT_PUBLICATION_PERFORMANCE:
        return _load_publication_performance_payload()
    if snapshot_type == SNAPSHOT_PUBLICATION_PERFORMANCE_STATUS:
        summary = _load_publication_performance_payload()
        return linkedin_performance_ledger_service.build_projection_status(summary)
    if snapshot_type == SNAPSHOT_SOURCE_ASSETS:
        return _build_source_assets_payload()
    if snapshot_type == SNAPSHOT_PERSONA_REVIEW_SUMMARY:
        return _build_persona_review_summary_payload()
    if snapshot_type == SNAPSHOT_LONG_FORM_ROUTES:
        return _build_long_form_routes_payload()
    if snapshot_type == SNAPSHOT_CONTENT_RESERVOIR:
        return _build_content_reservoir_payload()
    if snapshot_type == SNAPSHOT_WORKSPACE_FILES:
        return _privacy_safe_inventory_payload(
            snapshot_type,
            _snapshot_collection_payload(_load_workspace_files()),
        )
    if snapshot_type == SNAPSHOT_DOC_ENTRIES:
        return _privacy_safe_inventory_payload(
            snapshot_type,
            _snapshot_collection_payload(_load_doc_entries()),
        )
    if snapshot_type == SNAPSHOT_OPERATOR_STORY_SIGNALS:
        return _load_operator_story_signals_payload()
    if snapshot_type == SNAPSHOT_CONTENT_SAFE_OPERATOR_LESSONS:
        return _load_content_safe_operator_lessons_payload()
    return None


def _persist_snapshot(snapshot_type: str, payload: dict[str, Any], source: str) -> dict[str, Any]:
    if snapshot_type in {SNAPSHOT_WORKSPACE_FILES, SNAPSHOT_DOC_ENTRIES}:
        payload = _privacy_safe_inventory_payload(snapshot_type, payload)
    payload_for_storage = payload
    if snapshot_type == SNAPSHOT_PUBLICATION_PERFORMANCE:
        payload_for_storage = build_browser_performance_summary(payload)
        payload_for_storage = build_browser_performance_summary(payload_for_storage)
        if not _is_closed_publication_performance_projection(payload_for_storage):
            raise LinkedinPerformanceLedgerCorruption(
                "Publication performance summary could not be reduced to the privacy-safe projection contract."
            )
    workspace_key = (
        CANONICAL_FEEZIE_WORKSPACE_KEY
        if snapshot_type in {SNAPSHOT_PUBLICATION_PERFORMANCE, SNAPSHOT_PUBLICATION_PERFORMANCE_STATUS}
        else WORKSPACE_KEY
    )
    upsert_snapshot(
        workspace_key,
        snapshot_type,
        payload_for_storage,
        metadata={
            "source": source,
            "payload_generated_at": payload_for_storage.get("generated_at"),
        },
    )
    return payload


def _is_local_publication_performance_summary(payload: dict[str, Any]) -> bool:
    return bool(
        payload.get("schema_version") == "linkedin_publication_summary/v1"
        and payload.get("workspace_key") == CANONICAL_FEEZIE_WORKSPACE_KEY
        and isinstance(payload.get("counts"), dict)
        and isinstance(payload.get("publication_lifecycle_index"), list)
    )


def _is_closed_publication_performance_projection(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    if (
        set(payload) != PUBLICATION_PERFORMANCE_BROWSER_KEYS
        or payload.get("schema_version") != "linkedin_publication_summary/v1"
        or payload.get("workspace_key") != CANONICAL_FEEZIE_WORKSPACE_KEY
        or not isinstance(payload.get("counts"), dict)
        or payload.get("data_policy") != PUBLICATION_PERFORMANCE_BROWSER_POLICY
    ):
        return False
    projected = build_browser_performance_summary(payload)
    if not isinstance(projected, dict):
        return False
    normalized = dict(payload)
    normalized["generated_at"] = projected.get("generated_at")
    return normalized == projected


def _snapshot_is_usable(snapshot_type: str, payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict) or not payload:
        return False
    if snapshot_type == SNAPSHOT_SOCIAL_FEED:
        items = payload.get("items")
        if not isinstance(items, list) or not items:
            return False
        first_item = items[0]
        return (
            isinstance(first_item, dict)
            and bool(first_item.get("lens_variants"))
            and bool(first_item.get("source_class"))
            and bool(first_item.get("unit_kind"))
            and isinstance(first_item.get("response_modes"), list)
        )
    if snapshot_type == SNAPSHOT_WEEKLY_PLAN:
        return isinstance(payload.get("recommendations"), list) and isinstance(payload.get("positioning_model"), list)
    if snapshot_type == SNAPSHOT_REACTION_QUEUE:
        return isinstance(payload.get("comment_opportunities"), list) and isinstance(payload.get("post_seeds"), list)
    if snapshot_type == SNAPSHOT_FEEDBACK_SUMMARY:
        return "total_events" in payload
    if snapshot_type == SNAPSHOT_PUBLICATION_PERFORMANCE:
        return _is_local_publication_performance_summary(
            payload
        ) or _is_closed_publication_performance_projection(
            payload
        )
    if snapshot_type == SNAPSHOT_PUBLICATION_PERFORMANCE_STATUS:
        return (
            payload.get("schema_version") == "linkedin_publication_status/v1"
            and payload.get("workspace_key") == CANONICAL_FEEZIE_WORKSPACE_KEY
            and payload.get("state") in {"fresh", "stale", "missing", "degraded", "corrupt"}
        )
    if snapshot_type == SNAPSHOT_SOURCE_ASSETS:
        items = payload.get("items")
        counts = payload.get("counts")
        return isinstance(items, list) and isinstance(counts, dict)
    if snapshot_type == SNAPSHOT_PERSONA_REVIEW_SUMMARY:
        return isinstance(payload.get("counts"), dict) and isinstance(payload.get("recent"), list)
    if snapshot_type == SNAPSHOT_LONG_FORM_ROUTES:
        return isinstance(payload.get("route_counts"), dict) and isinstance(payload.get("candidates"), list)
    if snapshot_type == SNAPSHOT_CONTENT_RESERVOIR:
        return isinstance(payload.get("counts"), dict) and isinstance(payload.get("items"), list)
    if snapshot_type in {SNAPSHOT_WORKSPACE_FILES, SNAPSHOT_DOC_ENTRIES}:
        items = payload.get("items")
        counts = payload.get("counts")
        total = counts.get("total") if isinstance(counts, dict) else None
        return (
            payload.get("schema_version") == PRIVATE_INVENTORY_SCHEMA
            and isinstance(items, list)
            and not items
            and isinstance(total, int)
            and total >= 0
            and ((payload.get("data_policy") or {}).get("raw_content_included") is False)
        )
    if snapshot_type == SNAPSHOT_OPERATOR_STORY_SIGNALS:
        return isinstance(payload.get("counts"), dict) and isinstance(payload.get("signals"), list)
    if snapshot_type == SNAPSHOT_CONTENT_SAFE_OPERATOR_LESSONS:
        return isinstance(payload.get("counts"), dict) and isinstance(payload.get("lessons"), list)
    return True


def _social_feed_signature(payload: dict[str, Any]) -> list[tuple[str, str, str]]:
    items = payload.get("items") or []
    signature: list[tuple[str, str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        signature.append(
            (
                str(item.get("platform") or ""),
                str(item.get("source_url") or ""),
                str(item.get("title") or ""),
            )
        )
    return signature


def _source_assets_signature(payload: dict[str, Any]) -> list[tuple[str, str, str]]:
    items = payload.get("items") or []
    signature: list[tuple[str, str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        signature.append(
            (
                str(item.get("asset_id") or ""),
                str(item.get("source_path") or ""),
                str(item.get("title") or ""),
            )
        )
    return signature


def _weekly_plan_signature(payload: dict[str, Any]) -> tuple[Any, ...]:
    recommendations = payload.get("recommendations") or []
    brief_awareness_candidates = payload.get("brief_awareness_candidates") or []
    media_post_seeds = payload.get("media_post_seeds") or []
    belief_evidence_candidates = payload.get("belief_evidence_candidates") or []
    operational_route_candidates = payload.get("operational_route_candidates") or []
    source_counts = payload.get("source_counts") or {}
    if not isinstance(recommendations, list):
        recommendations = []
    if not isinstance(brief_awareness_candidates, list):
        brief_awareness_candidates = []
    if not isinstance(media_post_seeds, list):
        media_post_seeds = []
    if not isinstance(belief_evidence_candidates, list):
        belief_evidence_candidates = []
    if not isinstance(operational_route_candidates, list):
        operational_route_candidates = []
    if not isinstance(source_counts, dict):
        source_counts = {}

    def _candidate_signature(items: list[Any]) -> tuple[tuple[str, ...], ...]:
        signature: list[tuple[str, ...]] = []
        for item in items[:12]:
            if not isinstance(item, dict):
                continue
            signature.append(
                (
                    str(item.get("title") or ""),
                    str(item.get("source_path") or ""),
                    str(item.get("priority_lane") or ""),
                    str(item.get("handoff_lane") or ""),
                    str(item.get("canonical_pillar") or ""),
                    str(item.get("career_signal") or ""),
                    str(item.get("employer_proximity") or ""),
                    str(item.get("employer_safety") or ""),
                    str(item.get("proof_posture") or ""),
                    str(item.get("audience") or ""),
                    str(item.get("audience_consequence") or ""),
                    str(item.get("distinct_thesis") or ""),
                    str(item.get("why_now") or item.get("rationale") or ""),
                    str(item.get("development_status") or ""),
                )
            )
        return tuple(signature)

    strategy_contract = payload.get("strategy_contract")
    strategy_contract_signature = (
        json.dumps(strategy_contract, sort_keys=True, separators=(",", ":"), default=str)
        if isinstance(strategy_contract, dict)
        else ""
    )

    return (
        strategy_contract_signature,
        tuple(sorted((str(key), int(value)) for key, value in source_counts.items() if isinstance(value, (int, float)))),
        _candidate_signature(recommendations),
        _candidate_signature(brief_awareness_candidates),
        _candidate_signature(media_post_seeds),
        _candidate_signature(belief_evidence_candidates),
        _candidate_signature(operational_route_candidates),
    )


def _source_assets_count(payload: dict[str, Any] | None) -> int:
    if not isinstance(payload, dict):
        return 0
    counts = payload.get("counts")
    if isinstance(counts, dict):
        total = counts.get("total")
        if isinstance(total, (int, float)):
            return int(total)
    items = payload.get("items")
    return len(items) if isinstance(items, list) else 0


def _snapshot_item_count(snapshot_type: str, payload: dict[str, Any] | None) -> int:
    if snapshot_type == SNAPSHOT_LONG_FORM_ROUTES:
        return int((payload or {}).get("assets_considered") or 0)
    return _source_assets_count(payload)


def _should_preserve_persisted_source_assets(
    persisted: dict[str, Any] | None,
    runtime: dict[str, Any] | None,
) -> bool:
    """Keep richer durable inventory when runtime can only build a fallback."""

    if not (isinstance(persisted, dict) and _snapshot_is_usable(SNAPSHOT_SOURCE_ASSETS, persisted)):
        return False
    persisted_count = _source_assets_count(persisted)
    runtime_count = _source_assets_count(runtime)
    if persisted_count <= 0:
        return False
    if runtime_count == 0:
        return True
    return bool((runtime or {}).get("backfill_source")) and runtime_count < persisted_count


def _should_preserve_nonempty_snapshot(
    snapshot_type: str,
    persisted: dict[str, Any] | None,
    runtime: dict[str, Any] | None,
) -> bool:
    return bool(
        isinstance(persisted, dict)
        and _snapshot_is_usable(snapshot_type, persisted)
        and _snapshot_item_count(snapshot_type, persisted) > 0
        and _snapshot_item_count(snapshot_type, runtime) == 0
    )


def _snapshot_collection_signature(payload: dict[str, Any]) -> tuple[Any, ...]:
    if payload.get("schema_version") == PRIVATE_INVENTORY_SCHEMA:
        counts = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
        return (
            PRIVATE_INVENTORY_SCHEMA,
            str(payload.get("inventory_kind") or ""),
            int(counts.get("total") or 0),
            int(counts.get("browser_visible_items") or 0),
        )
    items = payload.get("items") or []
    if not isinstance(items, list):
        return ()

    signature: list[tuple[str, str, str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        signature.append(
            (
                str(item.get("path") or ""),
                str(item.get("group") or ""),
                str(item.get("updatedAt") or ""),
                str(item.get("name") or ""),
            )
        )
    return tuple(signature)


def _content_reservoir_signature(payload: dict[str, Any]) -> tuple[Any, ...]:
    counts = payload.get("counts") or {}
    items = payload.get("items") or []
    if not isinstance(counts, dict):
        counts = {}
    if not isinstance(items, list):
        items = []

    item_signature: list[tuple[str, str, str, str]] = []
    for item in items[:20]:
        if not isinstance(item, dict):
            continue
        item_signature.append(
            (
                str(item.get("reservoir_id") or ""),
                str(item.get("reservoir_lane") or ""),
                str(item.get("source_path") or ""),
                str(item.get("text") or ""),
            )
        )

    return (
        tuple(sorted((str(key), int(value)) for key, value in counts.items() if isinstance(value, (int, float)))),
        tuple(item_signature),
    )


def _operator_story_signals_signature(payload: dict[str, Any]) -> tuple[Any, ...]:
    counts = payload.get("counts") or {}
    signals = payload.get("signals") or []
    if not isinstance(counts, dict):
        counts = {}
    if not isinstance(signals, list):
        signals = []

    signal_signature: list[tuple[str, str, str, str]] = []
    for item in signals[:20]:
        if not isinstance(item, dict):
            continue
        signal_signature.append(
            (
                str(item.get("id") or ""),
                str(item.get("route") or ""),
                str(item.get("source_kind") or ""),
                str(item.get("claim") or ""),
            )
        )

    return (
        tuple(sorted((str(key), int(value)) for key, value in counts.items() if isinstance(value, (int, float)))),
        tuple(signal_signature),
    )


def _content_safe_operator_lessons_signature(payload: dict[str, Any]) -> tuple[Any, ...]:
    counts = payload.get("counts") or {}
    lessons = payload.get("lessons") or []
    if not isinstance(counts, dict):
        counts = {}
    if not isinstance(lessons, list):
        lessons = []

    lesson_signature: list[tuple[str, str, str, str]] = []
    for item in lessons[:20]:
        if not isinstance(item, dict):
            continue
        lesson_signature.append(
            (
                str(item.get("id") or ""),
                str(item.get("safe_angle") or ""),
                str(item.get("workspace_scope") or ""),
                str(item.get("macro_thesis") or ""),
            )
        )

    return (
        tuple(sorted((str(key), int(value)) for key, value in counts.items() if isinstance(value, (int, float)))),
        tuple(lesson_signature),
    )


def _persona_review_signature(payload: dict[str, Any]) -> tuple[Any, ...]:
    counts = payload.get("counts") or {}
    status_counts = payload.get("status_counts") or {}
    review_source_counts = payload.get("review_source_counts") or {}
    belief_relation_counts = payload.get("belief_relation_counts") or {}
    recent = payload.get("recent") or []
    long_form_sync = payload.get("long_form_sync") or {}
    if not isinstance(counts, dict):
        counts = {}
    if not isinstance(status_counts, dict):
        status_counts = {}
    if not isinstance(review_source_counts, dict):
        review_source_counts = {}
    if not isinstance(belief_relation_counts, dict):
        belief_relation_counts = {}
    if not isinstance(recent, list):
        recent = []
    if not isinstance(long_form_sync, dict):
        long_form_sync = {}

    recent_signature: list[tuple[str, str, str, str, str]] = []
    for item in recent[:12]:
        if not isinstance(item, dict):
            continue
        recent_signature.append(
            (
                str(item.get("id") or ""),
                str(item.get("status") or ""),
                str(item.get("stage") or ""),
                str(item.get("review_source") or ""),
                str(item.get("belief_relation") or ""),
            )
        )

    return (
        tuple(sorted((str(key), int(value)) for key, value in counts.items() if isinstance(value, (int, float)))),
        tuple(sorted((str(key), int(value)) for key, value in status_counts.items() if isinstance(value, (int, float)))),
        tuple(sorted((str(key), int(value)) for key, value in review_source_counts.items() if isinstance(value, (int, float)))),
        tuple(sorted((str(key), int(value)) for key, value in belief_relation_counts.items() if isinstance(value, (int, float)))),
        tuple(recent_signature),
        (
            int(long_form_sync.get("assets_considered") or 0),
            int(long_form_sync.get("created_count") or 0),
            int(long_form_sync.get("skipped_existing") or 0),
            int(long_form_sync.get("skipped_no_segments") or 0),
            int(long_form_sync.get("resolved_stale") or 0),
        ),
    )


def _long_form_routes_signature(payload: dict[str, Any]) -> tuple[Any, ...]:
    route_counts = payload.get("route_counts") or {}
    primary_route_counts = payload.get("primary_route_counts") or {}
    by_channel = payload.get("by_channel") or {}
    candidates = payload.get("candidates") or []
    if not isinstance(route_counts, dict):
        route_counts = {}
    if not isinstance(primary_route_counts, dict):
        primary_route_counts = {}
    if not isinstance(by_channel, dict):
        by_channel = {}
    if not isinstance(candidates, list):
        candidates = []

    candidate_signature: list[tuple[str, str, str, str]] = []
    for item in candidates[:12]:
        if not isinstance(item, dict):
            continue
        candidate_signature.append(
            (
                str(item.get("candidate_id") or ""),
                str(item.get("primary_route") or ""),
                str(item.get("source_channel") or ""),
                str(item.get("target_file") or ""),
            )
        )

    return (
        int(payload.get("assets_considered") or 0),
        int(payload.get("segments_total") or 0),
        int(payload.get("skipped_no_segments") or 0),
        tuple(sorted((str(key), int(value)) for key, value in route_counts.items() if isinstance(value, (int, float)))),
        tuple(sorted((str(key), int(value)) for key, value in primary_route_counts.items() if isinstance(value, (int, float)))),
        tuple(sorted((str(key), int(value)) for key, value in by_channel.items() if isinstance(value, (int, float)))),
        tuple(candidate_signature),
    )


def _load_snapshot(snapshot_type: str) -> dict[str, Any] | None:
    persisted = get_snapshot_payload(
        (
            CANONICAL_FEEZIE_WORKSPACE_KEY
            if snapshot_type in {SNAPSHOT_PUBLICATION_PERFORMANCE, SNAPSHOT_PUBLICATION_PERFORMANCE_STATUS}
            else WORKSPACE_KEY
        ),
        snapshot_type,
    )
    if snapshot_type in {SNAPSHOT_WORKSPACE_FILES, SNAPSHOT_DOC_ENTRIES} and persisted:
        persisted = _privacy_safe_inventory_payload(snapshot_type, persisted)
    if (
        snapshot_type == SNAPSHOT_PUBLICATION_PERFORMANCE
        and persisted
        and not _is_closed_publication_performance_projection(persisted)
    ):
        raise LinkedinPerformanceLedgerCorruption(
            "Persisted publication performance summary does not match the privacy-safe projection contract."
        )
    if snapshot_type == SNAPSHOT_WEEKLY_PLAN:
        runtime = _runtime_snapshot_payload(snapshot_type)
        if runtime:
            if not (persisted and _snapshot_is_usable(snapshot_type, persisted)):
                return _persist_snapshot(snapshot_type, runtime, "runtime_bootstrap")
            if _weekly_plan_signature(persisted) != _weekly_plan_signature(runtime):
                return _persist_snapshot(snapshot_type, runtime, "runtime_refresh")
            return runtime
        if persisted and _snapshot_is_usable(snapshot_type, persisted):
            return persisted
        return None
    if snapshot_type == SNAPSHOT_SOCIAL_FEED:
        runtime = _runtime_snapshot_payload(snapshot_type)
        if runtime:
            if not (persisted and _snapshot_is_usable(snapshot_type, persisted)):
                return _persist_snapshot(snapshot_type, runtime, "runtime_bootstrap")
            if _social_feed_signature(persisted) != _social_feed_signature(runtime):
                return _persist_snapshot(snapshot_type, runtime, "runtime_refresh")
            return runtime
        if persisted and _snapshot_is_usable(snapshot_type, persisted):
            return persisted
        return None
    if snapshot_type == SNAPSHOT_SOURCE_ASSETS:
        runtime = _runtime_snapshot_payload(snapshot_type)
        if runtime:
            if _should_preserve_persisted_source_assets(persisted, runtime):
                return persisted
            if not (persisted and _snapshot_is_usable(snapshot_type, persisted)):
                return _persist_snapshot(snapshot_type, runtime, "runtime_bootstrap")
            if _source_assets_signature(persisted) != _source_assets_signature(runtime):
                return _persist_snapshot(snapshot_type, runtime, "runtime_refresh")
            return runtime
        if persisted and _snapshot_is_usable(snapshot_type, persisted):
            return persisted
        return None
    if snapshot_type == SNAPSHOT_PERSONA_REVIEW_SUMMARY:
        runtime = _runtime_snapshot_payload(snapshot_type)
        if runtime:
            if not (persisted and _snapshot_is_usable(snapshot_type, persisted)):
                return _persist_snapshot(snapshot_type, runtime, "runtime_bootstrap")
            if _persona_review_signature(persisted) != _persona_review_signature(runtime):
                return _persist_snapshot(snapshot_type, runtime, "runtime_refresh")
            return runtime
        if persisted and _snapshot_is_usable(snapshot_type, persisted):
            return persisted
        return None
    if snapshot_type == SNAPSHOT_LONG_FORM_ROUTES:
        runtime = _runtime_snapshot_payload(snapshot_type)
        if runtime:
            if _should_preserve_nonempty_snapshot(snapshot_type, persisted, runtime):
                return persisted
            if not (persisted and _snapshot_is_usable(snapshot_type, persisted)):
                return _persist_snapshot(snapshot_type, runtime, "runtime_bootstrap")
            if _long_form_routes_signature(persisted) != _long_form_routes_signature(runtime):
                return _persist_snapshot(snapshot_type, runtime, "runtime_refresh")
            return runtime
        if persisted and _snapshot_is_usable(snapshot_type, persisted):
            return persisted
        return None
    if snapshot_type == SNAPSHOT_CONTENT_RESERVOIR:
        runtime = _runtime_snapshot_payload(snapshot_type)
        if runtime:
            if _should_preserve_nonempty_snapshot(snapshot_type, persisted, runtime):
                return persisted
            if not (persisted and _snapshot_is_usable(snapshot_type, persisted)):
                return _persist_snapshot(snapshot_type, runtime, "runtime_bootstrap")
            if _content_reservoir_signature(persisted) != _content_reservoir_signature(runtime):
                return _persist_snapshot(snapshot_type, runtime, "runtime_refresh")
            return runtime
        if persisted and _snapshot_is_usable(snapshot_type, persisted):
            return persisted
        return None
    if snapshot_type in {SNAPSHOT_WORKSPACE_FILES, SNAPSHOT_DOC_ENTRIES}:
        runtime = _runtime_snapshot_payload(snapshot_type)
        if runtime and _snapshot_is_usable(snapshot_type, runtime):
            if not (persisted and _snapshot_is_usable(snapshot_type, persisted)):
                return _persist_snapshot(snapshot_type, runtime, "runtime_bootstrap")
            if _snapshot_collection_signature(persisted) != _snapshot_collection_signature(runtime):
                return _persist_snapshot(snapshot_type, runtime, "runtime_refresh")
            return runtime
        if persisted and _snapshot_is_usable(snapshot_type, persisted):
            return persisted
        return None
    if snapshot_type == SNAPSHOT_OPERATOR_STORY_SIGNALS:
        runtime = _runtime_snapshot_payload(snapshot_type)
        if runtime:
            if not (persisted and _snapshot_is_usable(snapshot_type, persisted)):
                return _persist_snapshot(snapshot_type, runtime, "runtime_bootstrap")
            if _operator_story_signals_signature(persisted) != _operator_story_signals_signature(runtime):
                return _persist_snapshot(snapshot_type, runtime, "runtime_refresh")
            return runtime
        if persisted and _snapshot_is_usable(snapshot_type, persisted):
            return persisted
        return None
    if snapshot_type == SNAPSHOT_CONTENT_SAFE_OPERATOR_LESSONS:
        runtime = _runtime_snapshot_payload(snapshot_type)
        if runtime:
            if _should_preserve_nonempty_snapshot(snapshot_type, persisted, runtime):
                return persisted
            if not (persisted and _snapshot_is_usable(snapshot_type, persisted)):
                return _persist_snapshot(snapshot_type, runtime, "runtime_bootstrap")
            if _content_safe_operator_lessons_signature(persisted) != _content_safe_operator_lessons_signature(runtime):
                return _persist_snapshot(snapshot_type, runtime, "runtime_refresh")
            return runtime
        if persisted and _snapshot_is_usable(snapshot_type, persisted):
            return persisted
        return None
    if persisted and _snapshot_is_usable(snapshot_type, persisted):
        return persisted
    payload = _runtime_snapshot_payload(snapshot_type)
    if payload:
        source = "runtime_refresh" if persisted else "runtime_bootstrap"
        return _persist_snapshot(snapshot_type, payload, source)
    return None


def _load_persisted_snapshot(
    snapshot_type: str,
    *,
    persisted_payloads: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    if snapshot_type in {SNAPSHOT_PUBLICATION_PERFORMANCE, SNAPSHOT_PUBLICATION_PERFORMANCE_STATUS}:
        persisted = get_snapshot_payload(CANONICAL_FEEZIE_WORKSPACE_KEY, snapshot_type)
    else:
        persisted = (
            persisted_payloads.get(snapshot_type)
            if isinstance(persisted_payloads, dict)
            else get_snapshot_payload(WORKSPACE_KEY, snapshot_type)
        )
    if snapshot_type in {SNAPSHOT_WORKSPACE_FILES, SNAPSHOT_DOC_ENTRIES} and persisted:
        persisted = _privacy_safe_inventory_payload(snapshot_type, persisted)
    if snapshot_type == SNAPSHOT_PUBLICATION_PERFORMANCE:
        if persisted and _is_closed_publication_performance_projection(persisted):
            return persisted
        if persisted:
            raise LinkedinPerformanceLedgerCorruption(
                "Persisted publication performance summary does not match the privacy-safe projection contract."
            )
        return None
    if persisted and _snapshot_is_usable(snapshot_type, persisted):
        return persisted
    if persisted and snapshot_type in {SNAPSHOT_PUBLICATION_PERFORMANCE, SNAPSHOT_PUBLICATION_PERFORMANCE_STATUS}:
        raise LinkedinPerformanceLedgerCorruption(
            f"Persisted {snapshot_type} does not match the privacy-safe projection contract."
        )
    return None


def _load_current_feezie_strategy_contract() -> dict[str, Any] | None:
    """Load the validated current contract without trusting the weekly plan itself."""

    try:
        from app.services.feezie_positioning_contract_service import (
            EDITORIAL_MIX_PATH,
            POSITIONING_CONTRACT_PATH,
            load_feezie_strategy_contract,
        )
    except Exception:
        return None

    candidates = (
        ROOT,
        ROOT / "backend",
        Path(__file__).resolve().parents[3],
        Path.cwd(),
        Path.cwd() / "backend",
    )
    seen: set[Path] = set()
    saw_local_strategy_file = False
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        positioning_exists = (resolved / POSITIONING_CONTRACT_PATH).is_file()
        editorial_exists = (resolved / EDITORIAL_MIX_PATH).is_file()
        saw_local_strategy_file = saw_local_strategy_file or positioning_exists or editorial_exists
        if not (positioning_exists and editorial_exists):
            continue
        try:
            return load_feezie_strategy_contract(resolved)
        except Exception:
            # The first complete contract location is authoritative. An invalid
            # contract must read as unavailable rather than falling through to
            # a potentially unrelated checkout.
            return None

    # A partial local pair is broken canonical state, not permission to use an
    # older mirror. Privacy-reduced Railway images, however, intentionally ship
    # neither private strategy document. Their current comparison comes from
    # the fresh, exact-receipt-validated private runtime bundle synced by the
    # same signed action as the weekly projection.
    if saw_local_strategy_file:
        return None
    try:
        return load_persisted_feezie_strategy_contract()
    except Exception:
        return None


def _strategy_contract_freshness(
    weekly_plan: dict[str, Any] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    checked_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    planned_contract = weekly_plan.get("strategy_contract") if isinstance(weekly_plan, dict) else None
    planned_hash_text = (
        str(planned_contract.get("contract_hash") or "").strip()
        if isinstance(planned_contract, dict)
        else ""
    )
    planned_hash = planned_hash_text or None

    current_contract = _load_current_feezie_strategy_contract()
    current_hash_text = (
        str(current_contract.get("contract_hash") or "").strip()
        if isinstance(current_contract, dict)
        else ""
    )
    current_hash = current_hash_text or None
    approved_dates: list[str] = []
    if isinstance(current_contract, dict):
        for section_name in ("positioning", "editorial_mix"):
            section = current_contract.get(section_name)
            approved_at = str(section.get("approved_at") or "").strip() if isinstance(section, dict) else ""
            if approved_at:
                approved_dates.append(approved_at)
    approved_at = max(approved_dates) if approved_dates else None

    if not isinstance(weekly_plan, dict) or not current_hash:
        state = "unavailable"
    elif not planned_hash:
        state = "legacy"
    elif planned_hash == current_hash:
        state = "current"
    else:
        state = "stale"

    return {
        "state": state,
        "planned_hash": planned_hash,
        "current_hash": current_hash,
        "approved_at": approved_at,
        "checked_at": checked_at,
    }


def _project_weekly_plan_strategy_contract_freshness(
    weekly_plan: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Add a response-time comparison without mutating the persisted weekly plan."""

    if not isinstance(weekly_plan, dict):
        return weekly_plan
    projected = dict(weekly_plan)
    # Contract files can change independently of the last persisted plan. Keep
    # checked_at and the comparison live on every response rather than storing
    # a freshness result that becomes stale by definition.
    projected["strategy_contract_freshness"] = _strategy_contract_freshness(weekly_plan)
    return projected


def _status_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _editorial_section_status(
    snapshot_type: str,
    payload: dict[str, Any] | None,
    *,
    now: datetime,
) -> dict[str, Any]:
    stale_after_hours = int(EDITORIAL_SECTION_STALE_HOURS[snapshot_type])
    if not isinstance(payload, dict):
        return {
            "state": "missing",
            "available": False,
            "generated_at": None,
            "age_hours": None,
            "stale_after_hours": stale_after_hours,
        }
    generated = _status_timestamp(payload.get("generated_at"))
    if generated is None:
        return {
            "state": "corrupt",
            "available": True,
            "generated_at": None,
            "age_hours": None,
            "stale_after_hours": stale_after_hours,
        }
    future_skew_hours = (generated - now).total_seconds() / 3600
    if future_skew_hours > 1:
        return {
            "state": "corrupt",
            "available": True,
            "generated_at": generated.replace(microsecond=0).isoformat(),
            "age_hours": None,
            "stale_after_hours": stale_after_hours,
        }
    age_hours = round(max(0.0, (now - generated).total_seconds() / 3600), 2)
    return {
        "state": "stale" if age_hours > stale_after_hours else "fresh",
        "available": True,
        "generated_at": generated.replace(microsecond=0).isoformat(),
        "age_hours": age_hours,
        "stale_after_hours": stale_after_hours,
    }


def _feedback_section_status(
    payload: dict[str, Any] | None,
    *,
    now: datetime,
) -> dict[str, Any]:
    stale_after_hours = int(EDITORIAL_SECTION_STALE_HOURS[SNAPSHOT_FEEDBACK_SUMMARY])
    if not isinstance(payload, dict):
        return {
            "state": "missing",
            "available": False,
            "generated_at": None,
            "age_hours": None,
            "stale_after_hours": stale_after_hours,
            "evidence_state": "missing",
            "evidence_at": None,
        }
    total_events = payload.get("total_events")
    if isinstance(total_events, bool) or not isinstance(total_events, int) or total_events < 0:
        return {
            "state": "corrupt",
            "available": True,
            "generated_at": _browser_status_timestamp(payload.get("generated_at")),
            "age_hours": None,
            "stale_after_hours": stale_after_hours,
            "evidence_state": "invalid",
            "evidence_at": None,
        }
    generated = _status_timestamp(payload.get("generated_at"))
    generated_at = generated.replace(microsecond=0).isoformat() if generated is not None else None
    if total_events == 0:
        return {
            "state": "not_measured",
            "available": True,
            "generated_at": generated_at,
            "age_hours": None,
            "stale_after_hours": stale_after_hours,
            "evidence_state": "empty",
            "evidence_at": None,
        }

    evidence_at = _status_timestamp(payload.get("latest_event_at"))
    if evidence_at is None:
        recent_events = payload.get("recent_events") if isinstance(payload.get("recent_events"), list) else []
        candidates = [
            timestamp
            for event in recent_events
            if isinstance(event, dict)
            for timestamp in [_status_timestamp(event.get("recorded_at"))]
            if timestamp is not None
        ]
        evidence_at = max(candidates, default=None)
    if evidence_at is None:
        return {
            "state": "measurement_unverifiable",
            "available": True,
            "generated_at": generated_at,
            "age_hours": None,
            "stale_after_hours": stale_after_hours,
            "evidence_state": "present",
            "evidence_at": None,
        }
    future_skew_hours = (evidence_at - now).total_seconds() / 3600
    if future_skew_hours > 1:
        return {
            "state": "corrupt",
            "available": True,
            "generated_at": generated_at,
            "age_hours": None,
            "stale_after_hours": stale_after_hours,
            "evidence_state": "invalid",
            "evidence_at": evidence_at.replace(microsecond=0).isoformat(),
        }
    age_hours = round(max(0.0, (now - evidence_at).total_seconds() / 3600), 2)
    return {
        "state": "measurement_stale" if age_hours > stale_after_hours else "fresh",
        "available": True,
        "generated_at": generated_at,
        "age_hours": age_hours,
        "stale_after_hours": stale_after_hours,
        "evidence_state": "present",
        "evidence_at": evidence_at.replace(microsecond=0).isoformat(),
    }


def _effective_publication_performance_status(
    summary: dict[str, Any] | None,
    persisted_status: dict[str, Any] | None,
    *,
    now: datetime,
    load_error_state: str | None = None,
    load_error_type: str | None = None,
) -> dict[str, Any]:
    if load_error_state in {"corrupt", "degraded"}:
        return linkedin_performance_ledger_service.build_projection_status(
            None,
            now=now,
            state_override=load_error_state,
            error_type=load_error_type,
            source="workspace_snapshot_read",
        )

    computed = linkedin_performance_ledger_service.build_projection_status(
        summary,
        now=now,
        source="persisted_projection",
    )
    if not isinstance(persisted_status, dict) or persisted_status.get("state") not in {"corrupt", "degraded"}:
        return computed

    status_checked_at = _status_timestamp(persisted_status.get("checked_at"))
    summary_generated_at = _status_timestamp((summary or {}).get("generated_at"))
    if summary_generated_at is not None and status_checked_at is not None and status_checked_at < summary_generated_at:
        return computed

    projected = {
        **computed,
        "state": persisted_status.get("state"),
        "availability": persisted_status.get("availability") or computed.get("availability"),
        "source": str(persisted_status.get("source") or "persisted_status")[:80],
        "error_type": str(persisted_status.get("error_type") or "")[:120] or None,
    }
    return projected


def _build_workspace_editorial_status(
    *,
    weekly_plan: dict[str, Any] | None,
    reaction_queue: dict[str, Any] | None,
    social_feed: dict[str, Any] | None,
    feedback_summary: dict[str, Any] | None,
    source_assets: dict[str, Any] | None,
    content_reservoir: dict[str, Any] | None,
    persona_review_summary: dict[str, Any] | None,
    long_form_routes: dict[str, Any] | None,
    publication_performance_status: dict[str, Any],
    refresh_status: dict[str, Any] | None,
    load_errors: dict[str, dict[str, str]],
    now: datetime | None = None,
) -> dict[str, Any]:
    checked_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    payloads = {
        SNAPSHOT_WEEKLY_PLAN: weekly_plan,
        SNAPSHOT_REACTION_QUEUE: reaction_queue,
        SNAPSHOT_SOCIAL_FEED: social_feed,
        SNAPSHOT_FEEDBACK_SUMMARY: feedback_summary,
        SNAPSHOT_SOURCE_ASSETS: source_assets,
        SNAPSHOT_CONTENT_RESERVOIR: content_reservoir,
        SNAPSHOT_PERSONA_REVIEW_SUMMARY: persona_review_summary,
        SNAPSHOT_LONG_FORM_ROUTES: long_form_routes,
    }
    sections = {}
    for key, payload in payloads.items():
        if key == SNAPSHOT_FEEDBACK_SUMMARY:
            sections[key] = _feedback_section_status(payload, now=checked_at)
        else:
            sections[key] = _editorial_section_status(key, payload, now=checked_at)
    sections[SNAPSHOT_PUBLICATION_PERFORMANCE] = {
        "state": publication_performance_status.get("state"),
        "available": publication_performance_status.get("availability") == "available",
        "generated_at": publication_performance_status.get("projection_generated_at"),
        "age_hours": publication_performance_status.get("projection_age_hours"),
        "stale_after_hours": publication_performance_status.get("stale_after_hours"),
        "evidence_state": ((publication_performance_status.get("evidence") or {}).get("state")),
    }

    reasons = [
        f"{key}_{section.get('state')}"
        for key, section in sections.items()
        if section.get("state") != "fresh"
    ]
    if ((publication_performance_status.get("evidence") or {}).get("state")) == "empty":
        reasons.append("publication_performance_evidence_empty")
    refresh = refresh_status if isinstance(refresh_status, dict) else {}
    refresh_started_at = _status_timestamp(refresh.get("started_at"))
    persisted_feed_generated_at = _status_timestamp((social_feed or {}).get("generated_at"))
    refresh_error_is_newer = bool(
        refresh.get("error")
        and (
            refresh_started_at is None
            or persisted_feed_generated_at is None
            or refresh_started_at >= persisted_feed_generated_at
        )
    )
    if refresh_error_is_newer:
        reasons.append("social_feed_refresh_failed")
    for snapshot_type, error in sorted(load_errors.items()):
        reasons.append(f"{snapshot_type}_{error.get('state') or 'degraded'}")
    reasons = list(dict.fromkeys(reasons))

    section_states = {str(section.get("state") or "missing") for section in sections.values()}
    if "corrupt" in section_states or any(item.get("state") == "corrupt" for item in load_errors.values()):
        state, severity = "corrupt", "red"
    elif "degraded" in section_states or refresh_error_is_newer or load_errors:
        state, severity = "degraded", "red"
    elif any(
        sections[snapshot_type].get("state") == "stale"
        for snapshot_type in (
            SNAPSHOT_WEEKLY_PLAN,
            SNAPSHOT_REACTION_QUEUE,
            SNAPSHOT_SOCIAL_FEED,
            SNAPSHOT_SOURCE_ASSETS,
            SNAPSHOT_CONTENT_RESERVOIR,
            SNAPSHOT_LONG_FORM_ROUTES,
        )
    ):
        state, severity = "stale", "yellow"
    elif section_states & {
        "missing",
        "stale",
        "not_measured",
        "measurement_stale",
        "measurement_unverifiable",
    } or "publication_performance_evidence_empty" in reasons:
        state, severity = "incomplete", "yellow"
    else:
        state, severity = "current", "green"

    return {
        "schema_version": WORKSPACE_SNAPSHOT_STATUS_SCHEMA,
        "checked_at": checked_at.replace(microsecond=0).isoformat(),
        "http_available": True,
        "editorial_state": state,
        "severity": severity,
        "sections": sections,
        "reason_codes": reasons,
        "data_policy": {
            "status_only": True,
            "raw_error_messages_included": False,
            "http_success_implies_editorial_health": False,
        },
    }


class WorkspaceSnapshotService:
    def recompute_and_persist_persona_review_summary(
        self,
        *,
        request_generated_at: str,
    ) -> dict[str, Any]:
        """Recompute the private persona summary from Railway-owned DB state.

        This command path deliberately does not accept a caller-provided
        summary and does not run the filesystem-backed long-form synchronizer.
        One advisory-locked transaction reads an exact DB aggregate and stores
        it with a server observation timestamp through a monotonic compare-and-
        set.  The caller timestamp binds the receipt but never orders the DB
        observation.  Any read, completeness, or storage failure propagates.
        """

        _validated_persona_refresh_request_generated_at(request_generated_at)
        pool = get_pool()
        with pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (PERSONA_REVIEW_REFRESH_LOCK_KEY,),
                )
                payload, observation_generated_at = _load_exact_persona_review_summary(cursor)
                requested_hash = _snapshot_payload_sha256(payload)
                stored_snapshot, stored = _upsert_persona_review_summary_monotonic(
                    cursor,
                    payload,
                    observation_generated_at=observation_generated_at,
                    request_generated_at=request_generated_at,
                )
                if not isinstance(stored_snapshot, dict):
                    raise RuntimeError("Persona review summary storage is unavailable.")
                if (
                    stored_snapshot.get("workspace_key") != WORKSPACE_KEY
                    or stored_snapshot.get("snapshot_type") != SNAPSHOT_PERSONA_REVIEW_SUMMARY
                ):
                    raise RuntimeError("Persona review summary storage returned the wrong snapshot identity.")

                stored_payload = stored_snapshot.get("payload")
                if not isinstance(stored_payload, dict) or _browser_status_timestamp(
                    stored_payload.get("generated_at")
                ) is None:
                    raise RuntimeError("Persona review summary storage returned an invalid observation.")
                stored_hash = _snapshot_payload_sha256(stored_payload)
                if stored and stored_hash != requested_hash:
                    raise RuntimeError("Persona review summary storage did not acknowledge the recomputed payload.")

                snapshot_id = str(stored_snapshot.get("id") or "").strip()
                updated_at = stored_snapshot.get("updated_at")
                if not snapshot_id or not updated_at:
                    raise RuntimeError("Persona review summary storage receipt is incomplete.")
                receipt = {
                    "workspace_key": WORKSPACE_KEY,
                    "stored": stored,
                    "disposition": (
                        "stored"
                        if stored
                        else "idempotent_same_observation"
                        if stored_hash == requested_hash
                        else "retained_newer"
                    ),
                    "snapshot_type": SNAPSHOT_PERSONA_REVIEW_SUMMARY,
                    "payload_sha256": stored_hash,
                    "snapshot_id": snapshot_id,
                    "updated_at": updated_at,
                    "request_generated_at": request_generated_at,
                }
            conn.commit()
        return receipt

    def redact_persisted_private_inventories(self) -> dict[str, int]:
        """Replace exact legacy file snapshots with aggregate-only projections.

        The local files remain untouched.  Only the two derivative Postgres
        rows that previously fed the browser are rewritten.
        """

        checked = redacted = already_safe = 0
        for snapshot_type in (SNAPSHOT_WORKSPACE_FILES, SNAPSHOT_DOC_ENTRIES):
            persisted = get_snapshot_payload(WORKSPACE_KEY, snapshot_type)
            if not isinstance(persisted, dict):
                continue
            checked += 1
            safe_payload = _privacy_safe_inventory_payload(snapshot_type, persisted)
            if persisted == safe_payload:
                already_safe += 1
                continue
            stored = upsert_snapshot(
                WORKSPACE_KEY,
                snapshot_type,
                safe_payload,
                metadata={
                    "source": "startup_privacy_redaction",
                    "payload_generated_at": safe_payload.get("generated_at"),
                },
            )
            if stored is None:
                raise RuntimeError(f"Unable to redact persisted {snapshot_type} snapshot.")
            redacted += 1
        return {"checked": checked, "redacted": redacted, "already_safe": already_safe}

    def refresh_persisted_source_grounding_state(self) -> dict[str, Any]:
        """Refresh the bounded, no-fetch source projections used by FEEZIE."""

        refreshed: dict[str, Any] = {}
        source_assets = _runtime_snapshot_payload(SNAPSHOT_SOURCE_ASSETS)
        if source_assets:
            persisted_source_assets = get_snapshot_payload(WORKSPACE_KEY, SNAPSHOT_SOURCE_ASSETS)
            if not _should_preserve_persisted_source_assets(persisted_source_assets, source_assets):
                refreshed[SNAPSHOT_SOURCE_ASSETS] = _persist_snapshot(
                    SNAPSHOT_SOURCE_ASSETS,
                    source_assets,
                    "source_grounding_refresh",
                )

        content_reservoir = _runtime_snapshot_payload(SNAPSHOT_CONTENT_RESERVOIR)
        if content_reservoir:
            persisted_content_reservoir = get_snapshot_payload(WORKSPACE_KEY, SNAPSHOT_CONTENT_RESERVOIR)
            if not _should_preserve_nonempty_snapshot(
                SNAPSHOT_CONTENT_RESERVOIR,
                persisted_content_reservoir,
                content_reservoir,
            ):
                refreshed[SNAPSHOT_CONTENT_RESERVOIR] = _persist_snapshot(
                    SNAPSHOT_CONTENT_RESERVOIR,
                    content_reservoir,
                    "source_grounding_refresh",
                )

        long_form_routes = _runtime_snapshot_payload(SNAPSHOT_LONG_FORM_ROUTES)
        if long_form_routes:
            persisted_long_form_routes = get_snapshot_payload(WORKSPACE_KEY, SNAPSHOT_LONG_FORM_ROUTES)
            if not _should_preserve_nonempty_snapshot(
                SNAPSHOT_LONG_FORM_ROUTES,
                persisted_long_form_routes,
                long_form_routes,
            ):
                refreshed[SNAPSHOT_LONG_FORM_ROUTES] = _persist_snapshot(
                    SNAPSHOT_LONG_FORM_ROUTES,
                    long_form_routes,
                    "source_grounding_refresh",
                )

        return refreshed

    def get_source_grounding_status(self) -> dict[str, Any]:
        """Return aggregate persisted-vs-runtime grounding truth only."""

        rows: dict[str, dict[str, Any]] = {}
        for snapshot_type in (
            SNAPSHOT_SOURCE_ASSETS,
            SNAPSHOT_CONTENT_RESERVOIR,
            SNAPSHOT_CONTENT_SAFE_OPERATOR_LESSONS,
            SNAPSHOT_LONG_FORM_ROUTES,
        ):
            persisted = get_snapshot_payload(WORKSPACE_KEY, snapshot_type)
            try:
                runtime = _runtime_snapshot_payload(snapshot_type)
            except Exception as exc:
                rows[snapshot_type] = {
                    "persisted_count": _source_assets_count(persisted),
                    "runtime_count": 0,
                    "runtime_available": False,
                    "synchronized": False,
                    "error_type": type(exc).__name__,
                }
                continue

            persisted_count = _snapshot_item_count(snapshot_type, persisted)
            runtime_count = _snapshot_item_count(snapshot_type, runtime)
            row = {
                "persisted_count": persisted_count,
                "runtime_count": runtime_count,
                "runtime_available": isinstance(runtime, dict),
                "synchronized": persisted_count == runtime_count,
            }
            if snapshot_type == SNAPSHOT_SOURCE_ASSETS:
                row["runtime_fallback"] = bool((runtime or {}).get("backfill_source"))
            rows[snapshot_type] = row

        source_assets = rows[SNAPSHOT_SOURCE_ASSETS]
        return {
            "schema_version": "feezie_source_grounding_status/v1",
            "ready": bool(
                all(
                    row.get("runtime_available")
                    and row.get("synchronized")
                    and int(row.get("runtime_count") or 0) > 0
                    for row in rows.values()
                )
                and not source_assets.get("runtime_fallback")
            ),
            "snapshots": rows,
            "data_policy": {
                "aggregate_counts_only": True,
                "raw_source_content_included": False,
                "source_paths_included": False,
            },
        }

    def refresh_persisted_social_feed_state(self) -> dict[str, Any]:
        """Refresh only the cloud-safe feed, reaction, and source projections."""

        refreshed = self.refresh_persisted_source_grounding_state()
        for snapshot_type in (SNAPSHOT_REACTION_QUEUE, SNAPSHOT_SOCIAL_FEED):
            payload = _runtime_snapshot_payload(snapshot_type)
            if payload:
                refreshed[snapshot_type] = _persist_snapshot(snapshot_type, payload, "social_feed_refresh")
        return refreshed

    def refresh_persisted_linkedin_os_state(
        self,
        *,
        include_persona_review: bool = False,
    ) -> dict[str, Any]:
        refreshed: dict[str, Any] = {}
        for snapshot_type in (SNAPSHOT_WORKSPACE_FILES, SNAPSHOT_DOC_ENTRIES):
            payload = _runtime_snapshot_payload(snapshot_type)
            if payload and _snapshot_is_usable(snapshot_type, payload):
                refreshed[snapshot_type] = _persist_snapshot(snapshot_type, payload, "refresh")

        refreshed.update(self.refresh_persisted_social_feed_state())

        long_form_routes = refreshed.get(SNAPSHOT_LONG_FORM_ROUTES) or get_snapshot_payload(
            WORKSPACE_KEY,
            SNAPSHOT_LONG_FORM_ROUTES,
        )
        weekly_plan = _runtime_snapshot_payload(SNAPSHOT_WEEKLY_PLAN)
        weekly_plan = _augment_weekly_plan_payload(weekly_plan, long_form_routes)
        if weekly_plan:
            refreshed[SNAPSHOT_WEEKLY_PLAN] = _persist_snapshot(SNAPSHOT_WEEKLY_PLAN, weekly_plan, "refresh")

        operator_story_signals = _runtime_snapshot_payload(SNAPSHOT_OPERATOR_STORY_SIGNALS)
        if operator_story_signals:
            refreshed[SNAPSHOT_OPERATOR_STORY_SIGNALS] = _persist_snapshot(
                SNAPSHOT_OPERATOR_STORY_SIGNALS,
                operator_story_signals,
                "refresh",
            )

        content_safe_operator_lessons = _runtime_snapshot_payload(SNAPSHOT_CONTENT_SAFE_OPERATOR_LESSONS)
        if content_safe_operator_lessons:
            persisted_safe_lessons = get_snapshot_payload(WORKSPACE_KEY, SNAPSHOT_CONTENT_SAFE_OPERATOR_LESSONS)
            if not _should_preserve_nonempty_snapshot(
                SNAPSHOT_CONTENT_SAFE_OPERATOR_LESSONS,
                persisted_safe_lessons,
                content_safe_operator_lessons,
            ):
                refreshed[SNAPSHOT_CONTENT_SAFE_OPERATOR_LESSONS] = _persist_snapshot(
                    SNAPSHOT_CONTENT_SAFE_OPERATOR_LESSONS,
                    content_safe_operator_lessons,
                    "refresh",
                )

        if include_persona_review:
            persona_review_summary = _runtime_snapshot_payload(SNAPSHOT_PERSONA_REVIEW_SUMMARY)
            if persona_review_summary:
                refreshed[SNAPSHOT_PERSONA_REVIEW_SUMMARY] = _persist_snapshot(
                    SNAPSHOT_PERSONA_REVIEW_SUMMARY,
                    persona_review_summary,
                    "explicit_persona_refresh",
                )

        try:
            publication_performance = _runtime_snapshot_payload(SNAPSHOT_PUBLICATION_PERFORMANCE)
        except LinkedinPerformanceLedgerCorruption as exc:
            publication_status = linkedin_performance_ledger_service.build_projection_status(
                None,
                state_override="corrupt",
                error_type=type(exc).__name__,
                source="local_ledger_refresh",
            )
        except Exception as exc:
            publication_status = linkedin_performance_ledger_service.build_projection_status(
                None,
                state_override="degraded",
                error_type=type(exc).__name__,
                source="local_ledger_refresh",
            )
        else:
            if publication_performance:
                refreshed[SNAPSHOT_PUBLICATION_PERFORMANCE] = _persist_snapshot(
                    SNAPSHOT_PUBLICATION_PERFORMANCE,
                    publication_performance,
                    "refresh",
                )
            publication_status = linkedin_performance_ledger_service.build_projection_status(
                publication_performance,
                source="local_ledger_refresh",
            )

        refreshed[SNAPSHOT_PUBLICATION_PERFORMANCE_STATUS] = _persist_snapshot(
            SNAPSHOT_PUBLICATION_PERFORMANCE_STATUS,
            publication_status,
            "refresh",
        )
        return refreshed

    def get_linkedin_os_snapshot(
        self,
        *,
        persisted_only: bool = False,
        include_workspace_files: bool = True,
        include_doc_entries: bool = True,
    ) -> dict[str, Any]:
        persisted_payloads = list_snapshot_payloads(WORKSPACE_KEY) if persisted_only else None
        load_snapshot = (
            lambda snapshot_type: _load_persisted_snapshot(snapshot_type, persisted_payloads=persisted_payloads)
            if persisted_only
            else _load_snapshot(snapshot_type)
        )
        load_errors: dict[str, dict[str, str]] = {}

        def safe_load_snapshot(snapshot_type: str) -> dict[str, Any] | list[Any] | None:
            try:
                return load_snapshot(snapshot_type)
            except KeyError:
                return None
            except LinkedinPerformanceLedgerCorruption as exc:
                load_errors[snapshot_type] = {"state": "corrupt", "error_type": type(exc).__name__}
                return None
            except Exception as exc:
                load_errors[snapshot_type] = {"state": "degraded", "error_type": type(exc).__name__}
                return None

        workspace_files_payload = safe_load_snapshot(SNAPSHOT_WORKSPACE_FILES) if include_workspace_files else None
        doc_entries_payload = safe_load_snapshot(SNAPSHOT_DOC_ENTRIES) if include_doc_entries else None
        if isinstance(workspace_files_payload, dict):
            workspace_files_payload = _privacy_safe_inventory_payload(
                SNAPSHOT_WORKSPACE_FILES,
                workspace_files_payload,
            )
        if isinstance(doc_entries_payload, dict):
            doc_entries_payload = _privacy_safe_inventory_payload(
                SNAPSHOT_DOC_ENTRIES,
                doc_entries_payload,
            )
        source_assets = safe_load_snapshot(SNAPSHOT_SOURCE_ASSETS)
        content_reservoir = safe_load_snapshot(SNAPSHOT_CONTENT_RESERVOIR)
        long_form_routes = safe_load_snapshot(SNAPSHOT_LONG_FORM_ROUTES)
        weekly_plan = safe_load_snapshot(SNAPSHOT_WEEKLY_PLAN)
        weekly_plan = _augment_weekly_plan_payload(weekly_plan, long_form_routes)
        weekly_plan = _project_weekly_plan_strategy_contract_freshness(weekly_plan)
        # Browser-derived state must share the weekly-plan trust boundary.  If
        # lifecycle/activity builders consume legacy rows first, those rows can
        # survive even though the weekly-plan field is redacted at route time.
        browser_weekly_plan = _browser_weekly_plan_projection(weekly_plan)
        persona_review_summary = safe_load_snapshot(SNAPSHOT_PERSONA_REVIEW_SUMMARY)
        reaction_queue = safe_load_snapshot(SNAPSHOT_REACTION_QUEUE)
        social_feed = safe_load_snapshot(SNAPSHOT_SOCIAL_FEED)
        feedback_summary = safe_load_snapshot(SNAPSHOT_FEEDBACK_SUMMARY)
        publication_performance = safe_load_snapshot(SNAPSHOT_PUBLICATION_PERFORMANCE)
        persisted_publication_status = safe_load_snapshot(SNAPSHOT_PUBLICATION_PERFORMANCE_STATUS)
        performance_load_error = load_errors.get(SNAPSHOT_PUBLICATION_PERFORMANCE) or load_errors.get(
            SNAPSHOT_PUBLICATION_PERFORMANCE_STATUS
        )
        publication_performance_status = _effective_publication_performance_status(
            publication_performance if isinstance(publication_performance, dict) else None,
            persisted_publication_status if isinstance(persisted_publication_status, dict) else None,
            now=datetime.now(timezone.utc),
            load_error_state=(performance_load_error or {}).get("state"),
            load_error_type=(performance_load_error or {}).get("error_type"),
        )
        try:
            source_lifecycle = build_source_lifecycle(
                linkedin_root=_discover_linkedin_root(),
                social_feed=social_feed if isinstance(social_feed, dict) else None,
                reaction_queue=reaction_queue if isinstance(reaction_queue, dict) else None,
                weekly_plan=browser_weekly_plan,
                publication_records=(
                    publication_performance.get("publication_lifecycle_index")
                    if isinstance(publication_performance, dict)
                    and isinstance(publication_performance.get("publication_lifecycle_index"), list)
                    else None
                ),
            )
        except Exception:
            source_lifecycle = {
                "schema_version": "source_lifecycle/v1",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "workspace": WORKSPACE_KEY,
                "counts": {"total": 0, "by_stage": {}, "by_visibility": {}, "needs_decision": 0, "in_workflow": 0},
                "items": [],
                "error_type": "source_lifecycle_build_error",
                "reason_codes": ["source_lifecycle_build_failed"],
            }
        operator_story_signals = safe_load_snapshot(SNAPSHOT_OPERATOR_STORY_SIGNALS)
        content_safe_operator_lessons = safe_load_snapshot(SNAPSHOT_CONTENT_SAFE_OPERATOR_LESSONS)
        activity_feed = _build_activity_feed_payload(
            social_feed=social_feed if isinstance(social_feed, dict) else None,
            weekly_plan=browser_weekly_plan,
            reaction_queue=reaction_queue if isinstance(reaction_queue, dict) else None,
        )
        refresh_status = social_feed_refresh_service.get_status()
        snapshot_status = _build_workspace_editorial_status(
            weekly_plan=weekly_plan if isinstance(weekly_plan, dict) else None,
            reaction_queue=reaction_queue if isinstance(reaction_queue, dict) else None,
            social_feed=social_feed if isinstance(social_feed, dict) else None,
            feedback_summary=feedback_summary if isinstance(feedback_summary, dict) else None,
            source_assets=source_assets if isinstance(source_assets, dict) else None,
            content_reservoir=content_reservoir if isinstance(content_reservoir, dict) else None,
            persona_review_summary=persona_review_summary if isinstance(persona_review_summary, dict) else None,
            long_form_routes=long_form_routes if isinstance(long_form_routes, dict) else None,
            publication_performance_status=publication_performance_status,
            refresh_status=refresh_status,
            load_errors=load_errors,
        )
        private_runtime_context_status = build_feezie_private_runtime_context_status()
        return {
            "workspace_files": (workspace_files_payload or {}).get("items") if isinstance(workspace_files_payload, dict) else [],
            "doc_entries": (doc_entries_payload or {}).get("items") if isinstance(doc_entries_payload, dict) else [],
            "workspace_file_summary": workspace_files_payload if isinstance(workspace_files_payload, dict) else None,
            "doc_entry_summary": doc_entries_payload if isinstance(doc_entries_payload, dict) else None,
            "weekly_plan": weekly_plan,
            "reaction_queue": reaction_queue,
            "social_feed": social_feed,
            "source_lifecycle": source_lifecycle,
            "activity_feed": activity_feed,
            "feedback_summary": feedback_summary,
            "publication_performance_summary": publication_performance,
            "publication_performance_status": publication_performance_status,
            "source_assets": source_assets,
            "content_reservoir": content_reservoir,
            "operator_story_signals": operator_story_signals,
            "content_safe_operator_lessons": content_safe_operator_lessons,
            "persona_review_summary": persona_review_summary,
            "long_form_routes": long_form_routes,
            "refresh_status": refresh_status,
            "snapshot_status": snapshot_status,
            "private_runtime_context_status": private_runtime_context_status,
        }


workspace_snapshot_service = WorkspaceSnapshotService()
