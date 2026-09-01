from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from functools import partial
from typing import Any

from fastapi import APIRouter, HTTPException, Response

from app.models import (
    BrainCanonicalMemorySyncStatusRequest,
    BrainContentSafeOperatorLessonsSyncRequest,
    BrainLongFormIngestRequest,
    BrainOperatorStorySignalsSyncRequest,
    BrainPersonaReviewCandidateSyncRequest,
    BrainPersonaReviewRequest,
    BrainPersonaReviewSkipRequest,
    BrainPersonaRerouteRequest,
    BrainSignal,
    BrainSignalCreateRequest,
    BrainSignalReviewRequest,
    BrainSignalRouteEffectRequest,
    BrainSignalRouteRequest,
    BrainSignalSnapshotChunkRequest,
    BrainSignalSnapshotCommitRequest,
    BrainSignalSnapshotRequest,
    BrainSystemRouteRequest,
    BrainYouTubeWatchlistIngestRequest,
    BrainYouTubeWatchlistSnapshotRequest,
    BrainWorkspaceSnapshotSyncRequest,
    IntegratedContentProjectionSyncRequest,
    OpsStandupProjectionSyncRequest,
    PersonaDelta,
)
from app.services import persona_delta_service
from app.services.brain_local_action_queue_service import (
    authorize_brain_local_action_card,
    enqueue_brain_local_action,
    get_feezie_workspace_refresh_job,
    list_youtube_ingest_jobs,
)
from app.services.brain_response_privacy_service import sanitize_brain_payload
from app.services.brain_signal_service import build_signal_route_effect, get_signal, list_signals
from app.services.brain_system_route_service import route_delta_signal
from app.services.brain_control_plane_service import build_brain_control_plane
from app.services.decision_snapshot_service import build_decision_snapshot
from app.services.donor_repo_boundary_service import build_donor_repo_boundary_report
from app.services.fallback_policy_service import build_fallback_policy_report
from app.services.feezie_runtime_context_service import (
    FeezieRuntimeContextError,
    FEEZIE_RUNTIME_CONTEXT_SNAPSHOT_TYPE,
    FEEZIE_RUNTIME_CONTEXT_WORKSPACE_KEY,
    require_current_feezie_runtime_context_bundle,
)
from app.services.portfolio_workspace_snapshot_service import build_portfolio_workspace_snapshot
from app.services.repo_surface_registry_service import build_repo_surface_registry
from app.services.truth_lane_cleanup_service import build_truth_lane_cleanup_report
from app.services.persona_promotion_service import build_committed_persona_overlay, promote_delta_to_canon, reroute_delta_promotion
from app.services.persona_review_queue_service import annotate_for_brain_queue
from app.services.social_belief_engine import load_persona_truth
from app.services.source_sharing_policy_service import credential_free_public_url
from app.services.work_lifecycle_service import build_work_lifecycle_report
from app.services.workspace_snapshot_store import (
    delete_snapshot_types,
    get_snapshot_payload,
    list_snapshot_payloads,
    upsert_snapshot,
    upsert_snapshot_monotonic,
)
from app.services.integrated_content_projection_service import (
    SNAPSHOT_TYPE as INTEGRATED_CONTENT_SNAPSHOT_TYPE,
    WORKSPACE_KEY as INTEGRATED_CONTENT_WORKSPACE_KEY,
    validate_integrated_content_projection,
)
from app.services.ops_standup_projection_service import (
    LEGACY_PROJECTION_SCHEMA as OPS_STANDUP_LEGACY_SCHEMA,
    MAX_BYTES as OPS_STANDUP_MAX_BYTES,
    OpsStandupProjectionError,
    PRE_CLOCK_PROJECTION_SCHEMA as OPS_STANDUP_PRE_CLOCK_SCHEMA,
    SNAPSHOT_TYPE as OPS_STANDUP_SNAPSHOT_TYPE,
    WORKSPACE_KEY as OPS_STANDUP_WORKSPACE_KEY,
    ops_projection_semantic_sha256,
    validate_ops_standup_projection,
)
from app.services.workspace_snapshot_service import SNAPSHOT_WEEKLY_PLAN, workspace_snapshot_service
from app.services.youtube_watchlist_service import build_persisted_youtube_watchlist_payload

router = APIRouter(tags=["Brain"], prefix="/api/brain")
logger = logging.getLogger(__name__)


def _bounded_timeout_setting(name: str, default: float, maximum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(0.1, min(maximum, value))


def _bounded_int_setting(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


BRAIN_READ_TIMEOUT_SECONDS = _bounded_timeout_setting("BRAIN_READ_TIMEOUT_SECONDS", 5.0, 10.0)
PORTFOLIO_SNAPSHOT_READ_TIMEOUT_SECONDS = _bounded_timeout_setting(
    "PORTFOLIO_SNAPSHOT_READ_TIMEOUT_SECONDS",
    10.0,
    20.0,
)
YOUTUBE_WATCHLIST_READ_TIMEOUT_SECONDS = _bounded_timeout_setting(
    "YOUTUBE_WATCHLIST_READ_TIMEOUT_SECONDS",
    4.0,
    8.0,
)
BRAIN_SIGNAL_CHUNK_MAX_BYTES = 512 * 1024
BRAIN_SIGNAL_CHUNK_PREFIX = "brain_signals_chunk_"
BRAIN_WORKSPACE_PREVIEW_TYPES = {
    "source_assets": "brain_source_assets_preview",
    "content_reservoir": "brain_content_reservoir_summary",
    "long_form_routes": "brain_long_form_routes_summary",
    "publication_performance_summary": "publication_performance_summary",
    "publication_performance_status": "publication_performance_status",
}

# v1 was the original bounded Ops mirror. v2 added workspace recursion but
# still predated the canonical clock/attempt receipt. These exact top-level
# writer shapes are the only legacy rows that may take the one-time, same-
# observation migration to canonical attempt 2. Read compatibility remains
# broader and sanitizing; write migration is intentionally narrower.
_OPS_STANDUP_LEGACY_V1_FIELDS = (
    "schema_version",
    "generated_at",
    "state",
    "reason_codes",
    "ops_conclusion_id",
    "portfolio_cycle_id",
    "cycle_date",
    "observed_at",
    "status",
    "workspace_updates",
    "workspace_cycle_evaluations",
    "ai_clone_process_updates",
    "endpoint_and_subsystem_health",
    "work_underway",
    "completed_work",
    "blockers",
    "urgent_escalations",
    "workspace_decisions",
    "ops_decisions",
    "owner_calls",
    "canonical_decisions",
    "decision_readiness",
    "degraded_system_warnings",
    "supporting_evidence_links",
    "recommended_next_actions",
    "data_policy",
)
_OPS_STANDUP_LEGACY_MIGRATION_SCHEMAS = {
    OPS_STANDUP_LEGACY_SCHEMA: _OPS_STANDUP_LEGACY_V1_FIELDS,
    OPS_STANDUP_PRE_CLOCK_SCHEMA: (
        *_OPS_STANDUP_LEGACY_V1_FIELDS,
        "workspace_recursion",
    ),
}
_OPS_STANDUP_DATA_POLICY = {
    "canonical_authority": "mac_local_sql",
    "railway_role": "authenticated_bounded_ops_projection",
    "private_bodies_included": False,
}
_OPS_STANDUP_LEGACY_UTC_TIMESTAMP_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)"
)
_OPS_STANDUP_LEGACY_PROCESS_KEYS = {
    "memory_readiness",
    "morning_brief_ref",
}
_OPS_STANDUP_LEGACY_MEMORY_READINESS_KEYS = {
    "attempt_number",
    "consolidation",
    "consolidation_id",
    "cycle_id",
    "degraded_policy",
    "failed_component",
    "failure_reason",
    "last_verified_memory_at",
    "recall_probes",
    "receipt_payload_sha256",
    "retrieval_readiness",
    "retrieval_refresh",
    "schema_version",
    "status",
    "supersedes_status",
    "trusted_consolidation_id",
}
_OPS_STANDUP_LEGACY_HEALTH_KEYS = {
    "backup_recovery",
    "content_drafting",
    "control_plane_standup_read",
    "feezie_dream_context",
    "memory_readiness",
    "morning_brief",
    "persona_promotion",
    "source_content_intelligence",
    "workspace_standup_execution",
}


def _validated_ops_legacy_migration_candidate(
    payload: Any,
    *,
    target_projection: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Admit only an exact, bounded v1/v2 writer payload for migration.

    The normal projection validator deliberately keeps old Railway rows
    readable by sanitizing and upgrading them. That lossy read path is not a
    write authority: a malformed nested value could otherwise be discarded
    during validation and the raw row still receive the one-time revision
    bypass. Migration therefore requires the exact historical top-level
    writer shape and a lossless field-for-field upgrade of every data-bearing
    value. The returned JSON copy is later compared atomically with the row
    inside the monotonic upsert.
    """

    if not isinstance(payload, dict):
        return None
    schema = payload.get("schema_version")
    expected_fields = _OPS_STANDUP_LEGACY_MIGRATION_SCHEMAS.get(schema)
    if expected_fields is None:
        return None
    payload_fields = set(payload)
    expected_field_set = set(expected_fields)
    if payload_fields not in (
        expected_field_set,
        expected_field_set - {"observed_at"},
    ):
        return None
    try:
        serialized = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError):
        return None
    if len(serialized.encode("utf-8")) > OPS_STANDUP_MAX_BYTES:
        return None
    exact_payload = json.loads(serialized)
    if exact_payload.get("data_policy") != _OPS_STANDUP_DATA_POLICY:
        return None

    for identity_field in ("ops_conclusion_id", "portfolio_cycle_id"):
        identity = exact_payload.get(identity_field)
        if (
            not isinstance(identity, str)
            or not identity
            or identity != identity.strip()
            or len(identity) > 200
        ):
            return None
    cycle_date = exact_payload.get("cycle_date")
    if (
        not isinstance(cycle_date, str)
        or cycle_date != cycle_date.strip()
        or len(cycle_date) != 10
    ):
        return None
    parsed_times: dict[str, datetime] = {}
    for timestamp_field in ("generated_at", "observed_at"):
        timestamp = exact_payload.get(timestamp_field)
        if timestamp_field == "observed_at" and timestamp is None:
            target = target_projection if isinstance(target_projection, dict) else {}
            target_timestamp = target.get("observed_at")
            try:
                target_observed = datetime.fromisoformat(
                    str(target_timestamp or "").replace("Z", "+00:00")
                )
            except ValueError:
                return None
            if (
                target.get("ops_conclusion_attempt_number") != 2
                or target.get("ops_conclusion_id")
                != exact_payload.get("ops_conclusion_id")
                or target.get("portfolio_cycle_id")
                != exact_payload.get("portfolio_cycle_id")
                or target_observed.tzinfo is None
                or target_observed.utcoffset() != timedelta(0)
                or target_observed.date().isoformat() != cycle_date
            ):
                return None
            parsed_times[timestamp_field] = target_observed.astimezone(timezone.utc)
            continue
        if (
            not isinstance(timestamp, str)
            or not timestamp
            or timestamp != timestamp.strip()
            or len(timestamp) > 100
            or _OPS_STANDUP_LEGACY_UTC_TIMESTAMP_RE.fullmatch(timestamp) is None
        ):
            return None
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            return None
        if (
            parsed.tzinfo is None
            or parsed.utcoffset() is None
            or parsed.utcoffset() != timedelta(0)
        ):
            return None
        parsed_times[timestamp_field] = parsed.astimezone(timezone.utc)
    if parsed_times["observed_at"].date().isoformat() != cycle_date:
        return None
    state = exact_payload.get("state")
    status = exact_payload.get("status")
    raw_reason_codes = exact_payload.get("reason_codes")
    if (
        state not in {"ready", "degraded"}
        or status not in {"complete", "degraded"}
        or not isinstance(raw_reason_codes, list)
        or len(raw_reason_codes) > 20
        or any(
            not isinstance(item, str)
            or not item
            or item != item.strip()
            or len(item) > 200
            for item in raw_reason_codes
        )
        or (state == "ready" and (status != "complete" or raw_reason_codes))
        or (state == "degraded" and not raw_reason_codes)
    ):
        return None

    try:
        upgraded = validate_ops_standup_projection(exact_payload)
    except OpsStandupProjectionError:
        return None

    # These fields were already bounded by the historical writer. Requiring
    # exact equality with the compatibility upgrade proves that no unknown
    # nested field, private material, type confusion, truncation, or
    # normalization was hidden by the read path.
    lossless_fields = (
        "generated_at",
        "ops_conclusion_id",
        "portfolio_cycle_id",
        "cycle_date",
        "status",
        "workspace_updates",
        "workspace_cycle_evaluations",
        "work_underway",
        "completed_work",
        "blockers",
        "urgent_escalations",
        "workspace_decisions",
        "ops_decisions",
        "owner_calls",
        "canonical_decisions",
        "decision_readiness",
        "degraded_system_warnings",
        "supporting_evidence_links",
        "data_policy",
    )
    if any(upgraded.get(field) != exact_payload.get(field) for field in lossless_fields):
        return None
    raw_process_updates = exact_payload.get("ai_clone_process_updates")
    upgraded_process_updates = upgraded.get("ai_clone_process_updates")
    if raw_process_updates != upgraded_process_updates:
        if (
            not isinstance(raw_process_updates, dict)
            or set(raw_process_updates) != _OPS_STANDUP_LEGACY_PROCESS_KEYS
            or not isinstance(raw_process_updates.get("memory_readiness"), dict)
            or set(raw_process_updates["memory_readiness"])
            != _OPS_STANDUP_LEGACY_MEMORY_READINESS_KEYS
            or not isinstance(raw_process_updates.get("morning_brief_ref"), str)
            or not isinstance(upgraded_process_updates, dict)
            or set(upgraded_process_updates) != set(raw_process_updates)
        ):
            return None
    raw_health = exact_payload.get("endpoint_and_subsystem_health")
    upgraded_health = upgraded.get("endpoint_and_subsystem_health")
    if raw_health != upgraded_health:
        if (
            not isinstance(raw_health, dict)
            or set(raw_health) != _OPS_STANDUP_LEGACY_HEALTH_KEYS
            or any(
                not isinstance(value, str) or len(value) > 1000
                for value in raw_health.values()
            )
            or not isinstance(upgraded_health, dict)
            or set(upgraded_health) != set(raw_health)
        ):
            return None
    if schema == OPS_STANDUP_PRE_CLOCK_SCHEMA and (
        upgraded.get("workspace_recursion")
        != exact_payload.get("workspace_recursion")
    ):
        return None
    if upgraded.get("reason_codes", [])[: len(raw_reason_codes)] != raw_reason_codes:
        return None
    expected_recommendations: list[dict[str, Any]] = []
    raw_recommendations = exact_payload.get("recommended_next_actions")
    if not isinstance(raw_recommendations, list):
        return None
    for item in raw_recommendations:
        if isinstance(item, str) and item and item == item.strip() and len(item) <= 1000:
            expected_recommendations.append({"summary": item})
        elif isinstance(item, dict):
            expected_recommendations.append(item)
        else:
            return None
    if upgraded.get("recommended_next_actions") != expected_recommendations:
        return None
    return exact_payload


def _parse_generated_at(value: str) -> datetime:
    try:
        generated_at = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="generated_at must be a timezone-aware ISO-8601 timestamp.") from exc
    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise HTTPException(status_code=400, detail="generated_at must be a timezone-aware ISO-8601 timestamp.")
    generated_at = generated_at.astimezone(timezone.utc)
    if generated_at > datetime.now(timezone.utc) + timedelta(hours=1):
        raise HTTPException(status_code=400, detail="generated_at is too far in the future.")
    return generated_at


def _current_snapshot_payload_sha256(snapshot: dict[str, Any]) -> str | None:
    current_payload = snapshot.get("payload")
    if not isinstance(current_payload, dict):
        return None
    declared = str(current_payload.get("payload_sha256") or "").strip().lower()
    if len(declared) == 64 and all(character in "0123456789abcdef" for character in declared):
        return declared
    try:
        canonical = json.dumps(
            current_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError):
        return None
    return hashlib.sha256(canonical).hexdigest()


def _brain_signal_chunk_type(snapshot_id: str, chunk_index: int) -> str:
    normalized_id = str(snapshot_id).replace("-", "")
    return f"{BRAIN_SIGNAL_CHUNK_PREFIX}{normalized_id}_{chunk_index:03d}"


def _delete_snapshot_types_in_batches(workspace_key: str, snapshot_types: list[str]) -> None:
    for offset in range(0, len(snapshot_types), 100):
        delete_snapshot_types(workspace_key, snapshot_types[offset : offset + 100])


async def _run_bounded_read(
    operation: Callable[[], Any],
    *,
    timeout_seconds: float,
    label: str,
) -> Any:
    try:
        payload = await asyncio.wait_for(asyncio.to_thread(operation), timeout=timeout_seconds)
        return sanitize_brain_payload(payload)
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail=f"{label} timed out.") from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"{label} is unavailable.") from exc


def _queue_local_action(action: str, parameters: dict[str, Any], *, message: str, job_alias: bool = False) -> dict[str, Any]:
    try:
        card, disposition = enqueue_brain_local_action(action, parameters)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    response = {
        "message": message,
        "queued": True,
        "state": "queued",
        "disposition": disposition,
        "action": action,
        "card_id": card.id,
        "card": {
            "id": card.id,
            "title": card.title,
            "status": card.status,
            "created_at": card.created_at,
            "updated_at": card.updated_at,
        },
    }
    if job_alias:
        response["job_id"] = card.id
        response["job"] = {
            "job_id": card.id,
            "card_id": card.id,
            "status": "queued",
            "created_at": card.created_at,
            "updated_at": card.updated_at,
        }
    return response


@router.get("/control-plane")
async def get_brain_control_plane(response: Response):
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return await _run_bounded_read(
        build_brain_control_plane,
        timeout_seconds=BRAIN_READ_TIMEOUT_SECONDS,
        label="Brain control plane",
    )


@router.get("/portfolio-snapshot")
async def get_portfolio_snapshot(response: Response):
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return await _run_bounded_read(
        build_portfolio_workspace_snapshot,
        timeout_seconds=PORTFOLIO_SNAPSHOT_READ_TIMEOUT_SECONDS,
        label="Brain portfolio snapshot",
    )


@router.get("/decision-snapshot")
async def get_decision_snapshot(response: Response):
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return await _run_bounded_read(
        build_decision_snapshot,
        timeout_seconds=BRAIN_READ_TIMEOUT_SECONDS,
        label="Brain decision snapshot",
    )


@router.get("/repo-surface-registry")
async def get_repo_surface_registry(response: Response):
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return await _run_bounded_read(
        build_repo_surface_registry,
        timeout_seconds=BRAIN_READ_TIMEOUT_SECONDS,
        label="Brain repository surface registry",
    )


@router.get("/fallback-policy")
async def get_fallback_policy(response: Response):
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return await _run_bounded_read(
        build_fallback_policy_report,
        timeout_seconds=BRAIN_READ_TIMEOUT_SECONDS,
        label="Brain fallback policy",
    )


@router.get("/truth-lanes")
async def get_truth_lanes(response: Response):
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return await _run_bounded_read(
        build_truth_lane_cleanup_report,
        timeout_seconds=BRAIN_READ_TIMEOUT_SECONDS,
        label="Brain truth lanes",
    )


@router.get("/lifecycle")
async def get_lifecycle(response: Response):
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return await _run_bounded_read(
        build_work_lifecycle_report,
        timeout_seconds=BRAIN_READ_TIMEOUT_SECONDS,
        label="Brain work lifecycle",
    )


@router.get("/donor-boundary")
async def get_donor_boundary(response: Response):
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return await _run_bounded_read(
        build_donor_repo_boundary_report,
        timeout_seconds=BRAIN_READ_TIMEOUT_SECONDS,
        label="Brain donor boundary",
    )


@router.get("/signals", response_model=list[BrainSignal])
async def get_brain_signals(
    response: Response,
    limit: int = 50,
    review_status: str | None = None,
    workspace_key: str | None = None,
):
    response.headers["Cache-Control"] = "no-store, max-age=0"
    operation = partial(list_signals, limit=limit, review_status=review_status, workspace_key=workspace_key)
    return await _run_bounded_read(
        operation,
        timeout_seconds=BRAIN_READ_TIMEOUT_SECONDS,
        label="Brain signals",
    )


@router.post("/signals")
def post_brain_signal(payload: BrainSignalCreateRequest):
    return _queue_local_action(
        "signal_create",
        {"signal": payload.model_dump(mode="json", exclude_none=True)},
        message="Brain signal creation queued for the signed local runner.",
    )


@router.post("/signals/intake")
def post_brain_signal_intake(
    include_source_intelligence: bool = False,
    include_workspace_attention: bool = True,
    include_automation_outputs: bool = True,
    source_limit: int | None = None,
    include_quiet_automation: bool = False,
):
    return _queue_local_action(
        "signal_intake",
        {
            "include_source_intelligence": include_source_intelligence,
            "include_workspace_attention": include_workspace_attention,
            "include_automation_outputs": include_automation_outputs,
            "source_limit": source_limit,
            "include_quiet_automation": include_quiet_automation,
        },
        message="Brain signal intake queued for the signed local runner.",
    )


@router.post("/signals/snapshot")
def publish_brain_signal_snapshot(payload: BrainSignalSnapshotRequest):
    if len(payload.model_dump_json().encode("utf-8")) > 2 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Brain signal snapshot exceeds the 2 MB limit.")
    generated_at = _parse_generated_at(payload.generated_at)
    try:
        snapshot, stored = upsert_snapshot_monotonic(
            "shared_ops",
            "brain_signals",
            payload.model_dump(mode="json"),
            generated_at=generated_at,
            metadata={
                "source": payload.source,
                "signal_count": payload.count,
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Brain signal snapshot could not be stored.") from exc
    if snapshot is None:
        raise HTTPException(status_code=503, detail="Brain signal snapshot storage is unavailable.")
    return {
        "message": "Brain signal snapshot stored." if stored else "Brain signal snapshot was already current or newer.",
        "stored": stored,
        "disposition": "stored" if stored else "stale_or_equal_ignored",
        "snapshot_id": snapshot.get("id"),
        "updated_at": snapshot.get("updated_at"),
        "count": payload.count,
    }


@router.post("/signals/snapshot/chunk")
def publish_brain_signal_snapshot_chunk(payload: BrainSignalSnapshotChunkRequest):
    if len(payload.model_dump_json().encode("utf-8")) > BRAIN_SIGNAL_CHUNK_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Brain signal snapshot chunk exceeds the 512 KB limit.")
    generated_at = _parse_generated_at(payload.generated_at)
    snapshot_type = _brain_signal_chunk_type(payload.snapshot_id, payload.chunk_index)
    try:
        snapshot, stored = upsert_snapshot_monotonic(
            "shared_ops",
            snapshot_type,
            payload.model_dump(mode="json"),
            generated_at=generated_at,
            metadata={
                "source": payload.source,
                "brain_signal_snapshot_id": payload.snapshot_id,
                "chunk_index": payload.chunk_index,
                "chunk_count": payload.chunk_count,
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Brain signal snapshot chunk could not be stored.") from exc
    if snapshot is None:
        raise HTTPException(status_code=503, detail="Brain signal snapshot chunk storage is unavailable.")
    return {
        "message": "Brain signal snapshot chunk stored." if stored else "Brain signal snapshot chunk was already current.",
        "stored": stored,
        "disposition": "stored" if stored else "stale_or_equal_ignored",
        "snapshot_id": snapshot.get("id"),
        "signal_snapshot_id": payload.snapshot_id,
        "chunk_index": payload.chunk_index,
        "chunk_count": payload.chunk_count,
        "count": len(payload.signals),
    }


@router.post("/signals/snapshot/commit")
def commit_brain_signal_snapshot(payload: BrainSignalSnapshotCommitRequest):
    generated_at = _parse_generated_at(payload.generated_at)
    expected_types = [_brain_signal_chunk_type(payload.snapshot_id, index) for index in range(payload.chunk_count)]
    try:
        persisted = list_snapshot_payloads("shared_ops")
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Brain signal snapshot chunks are unavailable.") from exc

    chunks: list[dict[str, Any]] = []
    observed_total = 0
    for index, snapshot_type in enumerate(expected_types):
        chunk = persisted.get(snapshot_type)
        if not isinstance(chunk, dict):
            raise HTTPException(status_code=409, detail=f"Brain signal snapshot chunk {index} is missing.")
        if (
            chunk.get("schema_version") != "brain_signals_chunk/v1"
            or chunk.get("snapshot_id") != payload.snapshot_id
            or chunk.get("generated_at") != payload.generated_at
            or chunk.get("source") != payload.source
            or chunk.get("chunk_index") != index
            or chunk.get("chunk_count") != payload.chunk_count
            or chunk.get("total_count") != payload.total_count
            or not isinstance(chunk.get("signals"), list)
        ):
            raise HTTPException(status_code=409, detail=f"Brain signal snapshot chunk {index} does not match the manifest.")
        count = len(chunk["signals"])
        observed_total += count
        chunks.append({"snapshot_type": snapshot_type, "chunk_index": index, "count": count})
    if observed_total != payload.total_count:
        raise HTTPException(status_code=409, detail="Brain signal snapshot chunks do not match total_count.")

    manifest = {
        **payload.model_dump(mode="json"),
        "chunks": chunks,
    }
    try:
        snapshot, stored = upsert_snapshot_monotonic(
            "shared_ops",
            "brain_signals",
            manifest,
            generated_at=generated_at,
            metadata={
                "source": payload.source,
                "signal_count": payload.total_count,
                "chunk_count": payload.chunk_count,
                "brain_signal_snapshot_id": payload.snapshot_id,
            },
        )
        if snapshot is None:
            raise HTTPException(status_code=503, detail="Brain signal snapshot storage is unavailable.")
        current_payload = snapshot.get("payload") if isinstance(snapshot, dict) else None
        current_snapshot_id = current_payload.get("snapshot_id") if isinstance(current_payload, dict) else None
        if stored:
            cleanup_types = [
                snapshot_type
                for snapshot_type in persisted
                if snapshot_type.startswith(BRAIN_SIGNAL_CHUNK_PREFIX) and snapshot_type not in expected_types
            ]
        elif current_snapshot_id != payload.snapshot_id:
            cleanup_types = expected_types
        else:
            cleanup_types = []
        _delete_snapshot_types_in_batches("shared_ops", cleanup_types)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Brain signal snapshot manifest could not be stored.") from exc
    return {
        "message": "Brain signal snapshot committed." if stored else "Brain signal snapshot was already current or newer.",
        "stored": stored,
        "disposition": "stored" if stored else "stale_or_equal_ignored",
        "snapshot_id": snapshot.get("id"),
        "signal_snapshot_id": payload.snapshot_id,
        "updated_at": snapshot.get("updated_at"),
        "count": payload.total_count,
        "chunk_count": payload.chunk_count,
    }


@router.get("/signals/{signal_id}", response_model=BrainSignal)
async def get_brain_signal(signal_id: str):
    signal = await _run_bounded_read(
        partial(get_signal, signal_id),
        timeout_seconds=BRAIN_READ_TIMEOUT_SECONDS,
        label="Brain signal",
    )
    if signal is None:
        raise HTTPException(status_code=404, detail="Brain signal not found")
    return signal


@router.patch("/signals/{signal_id}")
def patch_brain_signal(signal_id: str, payload: BrainSignalReviewRequest):
    if get_signal(signal_id) is None:
        raise HTTPException(status_code=404, detail="Brain signal not found")
    return _queue_local_action(
        "signal_review",
        {"signal_id": signal_id, "review": payload.model_dump(mode="json", exclude_none=True)},
        message="Brain signal review queued for the signed local runner.",
    )


@router.post("/signals/{signal_id}/review")
def post_brain_signal_review(signal_id: str, payload: BrainSignalReviewRequest):
    if get_signal(signal_id) is None:
        raise HTTPException(status_code=404, detail="Brain signal not found")
    return _queue_local_action(
        "signal_review",
        {"signal_id": signal_id, "review": payload.model_dump(mode="json", exclude_none=True)},
        message="Brain signal review queued for the signed local runner.",
    )


@router.post("/signals/{signal_id}/route")
def post_brain_signal_route(signal_id: str, payload: BrainSignalRouteRequest):
    signal = get_signal(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Brain signal not found")
    return _queue_local_action(
        "signal_route",
        {
            "signal_id": signal_id,
            "signal": signal.model_dump(mode="json"),
            "route": payload.model_dump(mode="json", exclude_none=True),
        },
        message="Brain signal route queued for the signed local runner.",
    )


@router.post("/signals/{signal_id}/route-effect")
def commit_brain_signal_route_effect(signal_id: str, payload: BrainSignalRouteEffectRequest):
    if payload.signal.id != signal_id:
        raise HTTPException(status_code=400, detail="Brain signal route-effect id does not match the route.")
    try:
        _, action = authorize_brain_local_action_card(payload.card_id, "signal_route")
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    parameters = action["parameters"]
    if parameters.get("signal_id") != signal_id:
        raise HTTPException(status_code=403, detail="Signed Brain local action does not authorize this signal.")
    if parameters.get("signal") != payload.signal.model_dump(mode="json"):
        raise HTTPException(status_code=403, detail="Signed Brain local action does not authorize this signal payload.")
    if parameters.get("route") != payload.route.model_dump(mode="json", exclude_none=True):
        raise HTTPException(status_code=403, detail="Signed Brain local action does not authorize this route payload.")
    try:
        return build_signal_route_effect(payload.signal, payload.route, action_card_id=payload.card_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Brain signal route effect could not be committed.") from exc


@router.post("/ingest-long-form")
def ingest_long_form(payload: BrainLongFormIngestRequest):
    return _queue_local_action(
        "long_form_ingest",
        {"request": payload.model_dump(mode="json", exclude_none=True)},
        message="Long-form source ingest queued for the signed local runner.",
        job_alias=True,
    )


@router.get("/youtube-watchlist")
async def get_youtube_watchlist():
    return await _run_bounded_read(
        build_persisted_youtube_watchlist_payload,
        timeout_seconds=YOUTUBE_WATCHLIST_READ_TIMEOUT_SECONDS,
        label="YouTube watchlist",
    )


@router.get("/youtube-watchlist/jobs")
async def get_youtube_watchlist_jobs():
    jobs = await _run_bounded_read(
        list_youtube_ingest_jobs,
        timeout_seconds=YOUTUBE_WATCHLIST_READ_TIMEOUT_SECONDS,
        label="YouTube ingest jobs",
    )
    return {"jobs": jobs}


@router.post("/youtube-watchlist/snapshot")
def publish_youtube_watchlist_snapshot(payload: BrainYouTubeWatchlistSnapshotRequest):
    if len(payload.model_dump_json().encode("utf-8")) > 2 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="YouTube watchlist snapshot exceeds the 2 MB limit.")
    snapshot_payload = payload.model_dump(mode="json")
    try:
        snapshot, stored = upsert_snapshot_monotonic(
            "linkedin-content-os",
            "youtube_watchlist",
            snapshot_payload,
            generated_at=_parse_generated_at(payload.generated_at),
            metadata={
                "source": "codex_launchd_youtube_watchlist",
                "channel_count": len(payload.channels),
                "playlist_count": len(payload.designated_playlists),
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail="YouTube watchlist snapshot could not be stored.") from exc
    if snapshot is None:
        raise HTTPException(status_code=503, detail="YouTube watchlist snapshot storage is unavailable.")
    return {
        "message": "YouTube watchlist snapshot stored." if stored else "YouTube watchlist snapshot was already current or newer.",
        "stored": stored,
        "disposition": "stored" if stored else "stale_or_equal_ignored",
        "snapshot_id": snapshot.get("id"),
        "updated_at": snapshot.get("updated_at"),
        "channel_count": len(payload.channels),
        "playlist_count": len(payload.designated_playlists),
        "video_count": sum(
            len(channel.get("videos") or [])
            for channel in [*payload.channels, *payload.designated_playlists]
            if isinstance(channel.get("videos"), list)
        ),
    }


@router.post("/youtube-watchlist/ingest")
def queue_youtube_watchlist_ingest(payload: BrainYouTubeWatchlistIngestRequest):
    return _queue_local_action(
        "youtube_watchlist_ingest",
        {"request": payload.model_dump(mode="json", exclude_none=True)},
        message="YouTube watchlist ingest queued for the signed local runner.",
        job_alias=True,
    )


@router.post("/workspace-snapshots/sync")
def publish_brain_workspace_snapshots(payload: BrainWorkspaceSnapshotSyncRequest):
    if len(payload.model_dump_json().encode("utf-8")) > 2 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Brain workspace snapshot bundle exceeds the 2 MB limit.")
    generated_at = _parse_generated_at(payload.generated_at)
    snapshots = {
        key: value
        for key, value in {
            "source_assets": payload.source_assets,
            "content_reservoir": payload.content_reservoir,
            "long_form_routes": payload.long_form_routes,
            "publication_performance_summary": payload.publication_performance_summary,
            "publication_performance_status": payload.publication_performance_status,
            "publication_performance_lifecycle": payload.publication_performance_lifecycle,
            "feezie_runtime_context": payload.feezie_runtime_context,
            "weekly_plan": payload.weekly_plan,
        }.items()
        if isinstance(value, dict)
    }
    if payload.persona_review_refresh == "recompute_db_owned":
        # Defense in depth for callers that bypass Pydantic construction: the
        # DB-owned recompute is a single-purpose capability, never an option on
        # a multi-snapshot write request.
        if snapshots:
            raise HTTPException(
                status_code=400,
                detail="persona_review_refresh cannot be mixed with workspace snapshots.",
            )
        try:
            receipt = workspace_snapshot_service.recompute_and_persist_persona_review_summary(
                request_generated_at=payload.generated_at,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail="Brain workspace snapshot storage is unavailable.",
            ) from exc
        return {
            "message": "Brain persona review summary recomputed from database-owned state.",
            "stored": bool(receipt.get("stored")),
            "snapshots": {"persona_review_summary": receipt},
        }

    results: dict[str, dict[str, Any]] = {}
    try:
        for response_key, snapshot_payload in snapshots.items():
            if response_key == "publication_performance_lifecycle":
                identity_token = str(snapshot_payload.get("identity_token") or "").strip().lower()
                snapshot_type = f"publication_performance_lifecycle:{identity_token}"
            elif response_key == "feezie_runtime_context":
                snapshot_type = FEEZIE_RUNTIME_CONTEXT_SNAPSHOT_TYPE
            elif response_key == "weekly_plan":
                snapshot_type = SNAPSHOT_WEEKLY_PLAN
            else:
                snapshot_type = BRAIN_WORKSPACE_PREVIEW_TYPES[response_key]
            normalized_snapshot_payload = {**snapshot_payload, "generated_at": payload.generated_at}
            if response_key == "publication_performance_lifecycle":
                target_workspace = "feezie-performance-lifecycle"
            elif response_key == "feezie_runtime_context":
                target_workspace = FEEZIE_RUNTIME_CONTEXT_WORKSPACE_KEY
            elif response_key in {"publication_performance_summary", "publication_performance_status"}:
                target_workspace = "feezie-os"
            else:
                target_workspace = payload.workspace
            stored_snapshot, stored = upsert_snapshot_monotonic(
                target_workspace,
                snapshot_type,
                normalized_snapshot_payload,
                generated_at=generated_at,
                metadata={"source": payload.source, "brain_preview_key": response_key},
            )
            if stored_snapshot is None:
                raise RuntimeError(f"{response_key} storage is unavailable")
            disposition = "stored" if stored else "stale_or_equal_ignored"
            if response_key == "feezie_runtime_context":
                requested_runtime = require_current_feezie_runtime_context_bundle(
                    normalized_snapshot_payload
                )
                requested_hash = str(requested_runtime["payload_sha256"])
                current_payload = stored_snapshot.get("payload")
                try:
                    current_runtime = require_current_feezie_runtime_context_bundle(
                        current_payload
                    )
                except FeezieRuntimeContextError:
                    if stored:
                        raise RuntimeError(
                            "feezie_runtime_context storage did not return the exact current runtime payload"
                        )
                    recovered_snapshot = upsert_snapshot(
                        FEEZIE_RUNTIME_CONTEXT_WORKSPACE_KEY,
                        FEEZIE_RUNTIME_CONTEXT_SNAPSHOT_TYPE,
                        requested_runtime,
                        metadata={
                            "source": payload.source,
                            "brain_preview_key": response_key,
                            "runtime_context_recovery": "invalid_persisted_row",
                        },
                    )
                    if recovered_snapshot is None:
                        raise RuntimeError("feezie_runtime_context recovery storage is unavailable")
                    stored_snapshot = recovered_snapshot
                    stored = True
                    disposition = "recovered_invalid_runtime"
                    current_runtime = require_current_feezie_runtime_context_bundle(
                        stored_snapshot.get("payload")
                    )

                current_hash = str(current_runtime["payload_sha256"])
                if stored and current_hash != requested_hash:
                    raise RuntimeError(
                        "feezie_runtime_context storage did not acknowledge the requested payload hash"
                    )
                if not stored:
                    disposition = (
                        "idempotent_same_hash"
                        if current_hash == requested_hash
                        else "retained_newer"
                    )
            elif response_key == "weekly_plan":
                requested_hash = hashlib.sha256(
                    json.dumps(
                        normalized_snapshot_payload,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=True,
                        allow_nan=False,
                    ).encode("utf-8")
                ).hexdigest()
                current_hash = _current_snapshot_payload_sha256(stored_snapshot)
                if stored and current_hash != requested_hash:
                    raise RuntimeError(
                        "weekly_plan storage did not acknowledge the requested payload hash"
                    )
                if not stored:
                    disposition = (
                        "idempotent_same_hash"
                        if current_hash == requested_hash
                        else "retained_newer"
                    )
            else:
                current_hash = _current_snapshot_payload_sha256(stored_snapshot)
            results[response_key] = {
                "workspace_key": target_workspace,
                "stored": stored,
                "disposition": disposition,
                "snapshot_type": snapshot_type,
                "payload_sha256": current_hash,
                "snapshot_id": stored_snapshot.get("id"),
                "updated_at": stored_snapshot.get("updated_at"),
            }
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Brain workspace snapshot storage is unavailable.") from exc
    return {
        "message": "Brain workspace snapshots synchronized from the local runner.",
        "stored": any(item["stored"] for item in results.values()),
        "snapshots": results,
    }


@router.post("/integrated-content/sync")
def publish_integrated_content_projection(payload: IntegratedContentProjectionSyncRequest):
    projection = validate_integrated_content_projection(payload.projection)
    try:
        stored_snapshot, stored = upsert_snapshot_monotonic(
            INTEGRATED_CONTENT_WORKSPACE_KEY,
            INTEGRATED_CONTENT_SNAPSHOT_TYPE,
            projection,
            generated_at=_parse_generated_at(payload.generated_at),
            metadata={"source": "codex_local_runner", "projection": "integrated_content"},
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Integrated content projection storage is unavailable.") from exc
    if stored_snapshot is None:
        raise HTTPException(status_code=503, detail="Integrated content projection storage is unavailable.")
    current = validate_integrated_content_projection(stored_snapshot.get("payload"))
    requested_hash = hashlib.sha256(
        json.dumps(projection, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    current_hash = hashlib.sha256(
        json.dumps(current, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return {
        "stored": stored,
        "disposition": "stored" if stored else ("idempotent_same_hash" if current_hash == requested_hash else "retained_newer"),
        "workspace_key": INTEGRATED_CONTENT_WORKSPACE_KEY,
        "snapshot_type": INTEGRATED_CONTENT_SNAPSHOT_TYPE,
        "payload_sha256": current_hash,
        "updated_at": stored_snapshot.get("updated_at"),
    }


@router.post("/ops-standup/sync")
def publish_ops_standup_projection(payload: OpsStandupProjectionSyncRequest):
    try:
        projection = validate_ops_standup_projection(payload.projection)
    except OpsStandupProjectionError as exc:
        raise HTTPException(
            status_code=422,
            detail="Ops standup projection clock or bounded contract is invalid.",
        ) from exc
    request_generated_at = _parse_generated_at(payload.generated_at)
    projection_generated_at = _parse_generated_at(str(projection["generated_at"]))
    if request_generated_at != projection_generated_at:
        raise HTTPException(
            status_code=422,
            detail="Ops standup projection receipt time does not match its envelope.",
        )
    semantic_observed_at = (
        _parse_generated_at(str(projection["observed_at"]))
        if projection.get("observed_at") is not None
        else None
    )
    semantic_attempt_number = projection.get("ops_conclusion_attempt_number")
    if semantic_observed_at is not None and not isinstance(
        semantic_attempt_number, int
    ):
        raise HTTPException(
            status_code=422,
            detail="Ops standup projection is missing its canonical conclusion attempt.",
        )
    legacy_candidate = None
    if semantic_observed_at is not None and semantic_attempt_number == 2:
        try:
            legacy_snapshot_payload = get_snapshot_payload(
                OPS_STANDUP_WORKSPACE_KEY,
                OPS_STANDUP_SNAPSHOT_TYPE,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail="Ops standup projection storage is unavailable.",
            ) from exc
        legacy_candidate = _validated_ops_legacy_migration_candidate(
            legacy_snapshot_payload,
            target_projection=projection,
        )
    legacy_migration_kwargs = {}
    if legacy_candidate is not None:
        legacy_migration_schemas = dict(_OPS_STANDUP_LEGACY_MIGRATION_SCHEMAS)
        legacy_schema = legacy_candidate.get("schema_version")
        if isinstance(legacy_schema, str):
            legacy_migration_schemas[legacy_schema] = tuple(legacy_candidate)
        legacy_migration_kwargs = {
            "semantic_legacy_migration_revision": 2,
            "semantic_legacy_migration_schemas": legacy_migration_schemas,
            "semantic_legacy_migration_required_values": {
                "data_policy": _OPS_STANDUP_DATA_POLICY,
            },
            "semantic_legacy_migration_max_bytes": OPS_STANDUP_MAX_BYTES,
            "semantic_legacy_migration_expected_payload": legacy_candidate,
        }
    try:
        stored_snapshot, stored = upsert_snapshot_monotonic(
            OPS_STANDUP_WORKSPACE_KEY,
            OPS_STANDUP_SNAPSHOT_TYPE,
            projection,
            generated_at=request_generated_at,
            semantic_observed_at=semantic_observed_at,
            semantic_order_required=True,
            semantic_revision=semantic_attempt_number,
            semantic_revision_field=(
                "ops_conclusion_attempt_number"
                if semantic_attempt_number is not None
                else None
            ),
            semantic_revision_required=semantic_observed_at is not None,
            semantic_revision_strict_increment=semantic_observed_at is not None,
            semantic_identity_fields=(
                ("ops_conclusion_id", "portfolio_cycle_id")
                if semantic_observed_at is not None
                else ()
            ),
            **legacy_migration_kwargs,
            metadata={"source": "codex_local_runner", "projection": "ops_standup"},
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Ops standup projection storage is unavailable.") from exc
    if stored_snapshot is None:
        raise HTTPException(status_code=503, detail="Ops standup projection storage is unavailable.")
    current = validate_ops_standup_projection(stored_snapshot.get("payload"))
    requested_hash = hashlib.sha256(json.dumps(projection, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
    current_hash = hashlib.sha256(json.dumps(current, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
    disposition = "stored"
    if not stored:
        current_observed_at = (
            _parse_generated_at(str(current["observed_at"]))
            if current.get("observed_at") is not None
            else None
        )
        current_attempt_number = current.get("ops_conclusion_attempt_number")
        if current_hash == requested_hash:
            disposition = "idempotent_same_hash"
        elif (
            semantic_observed_at is not None
            and current_observed_at == semantic_observed_at
        ):
            if current_attempt_number == semantic_attempt_number:
                if (
                    current.get("ops_conclusion_id")
                    == projection.get("ops_conclusion_id")
                    and current.get("portfolio_cycle_id")
                    == projection.get("portfolio_cycle_id")
                    and current.get("ops_conclusion_attempt_id")
                    == projection.get("ops_conclusion_attempt_id")
                    and current.get("ops_conclusion_attempt_number")
                    == projection.get("ops_conclusion_attempt_number")
                    and current.get("ops_conclusion_attempt_payload_sha256")
                    == projection.get("ops_conclusion_attempt_payload_sha256")
                    and ops_projection_semantic_sha256(current)
                    == ops_projection_semantic_sha256(projection)
                ):
                    disposition = "idempotent_same_canonical_attempt"
                else:
                    raise HTTPException(
                        status_code=409,
                        detail="The same canonical Ops attempt has conflicting semantic content.",
                    )
            elif (
                isinstance(current_attempt_number, int)
                and isinstance(semantic_attempt_number, int)
                and semantic_attempt_number <= current_attempt_number
            ):
                raise HTTPException(
                    status_code=409,
                    detail="A stale or lower canonical Ops attempt cannot replace the current attempt.",
                )
            else:
                raise HTTPException(
                    status_code=409,
                    detail="A canonical Ops attempt cannot skip the next append-only attempt.",
                )
        elif (
            current_observed_at is not None
            and semantic_observed_at is not None
            and current_observed_at > semantic_observed_at
        ):
            disposition = "retained_newer_semantic_observation"
        else:
            raise HTTPException(
                status_code=409,
                detail="Ops projection semantic ordering could not be established.",
            )
    return {
        "stored": stored,
        "disposition": disposition,
        "workspace_key": OPS_STANDUP_WORKSPACE_KEY,
        "snapshot_type": OPS_STANDUP_SNAPSHOT_TYPE,
        "payload_sha256": current_hash,
        "semantic_payload_sha256": ops_projection_semantic_sha256(current),
        "ops_conclusion_attempt_id": current.get("ops_conclusion_attempt_id"),
        "ops_conclusion_attempt_number": current.get(
            "ops_conclusion_attempt_number"
        ),
        "ops_conclusion_attempt_payload_sha256": current.get(
            "ops_conclusion_attempt_payload_sha256"
        ),
        "updated_at": stored_snapshot.get("updated_at"),
    }


@router.post("/persona-review/candidates/sync")
def sync_canonical_persona_review_candidates(
    payload: BrainPersonaReviewCandidateSyncRequest,
):
    encoded_size = len(payload.model_dump_json().encode("utf-8"))
    if encoded_size > 256 * 1024:
        raise HTTPException(
            status_code=413,
            detail="Persona review candidate projection exceeds the 256 KB limit.",
        )
    try:
        for item in payload.items:
            source_url = (item.source_url or "").strip()
            if item.source_attribution_kind == "attributed_external" and not source_url:
                raise ValueError("Attributed external Persona candidates require a public source URL.")
            if source_url:
                credential_free_public_url(source_url)
        result = persona_delta_service.sync_projected_review_candidates(
            [item.model_dump(mode="json") for item in payload.items],
            active_source_limit=_bounded_int_setting(
                "PERSONA_REVIEW_ACTIVE_SOURCE_LIMIT",
                8,
                1,
                20,
            ),
        )
        summary_receipt = workspace_snapshot_service.recompute_and_persist_persona_review_summary(
            request_generated_at=payload.generated_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Canonical Persona review candidate sync failed")
        raise HTTPException(
            status_code=503,
            detail="Canonical Persona review candidates could not be stored.",
        ) from exc
    return {
        "schema_version": "canonical_persona_review_projection_receipt/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "request_generated_at": payload.generated_at,
        "projection_bytes": encoded_size,
        **result,
        "persona_review_summary": summary_receipt,
    }


@router.post("/persona-review/{delta_id}/skip")
def skip_persona_review(delta_id: str, payload: BrainPersonaReviewSkipRequest):
    try:
        result = persona_delta_service.skip_brain_review(delta_id, scope=payload.scope)
        if result is None:
            raise HTTPException(status_code=404, detail="Persona delta not found")
        summary_receipt = workspace_snapshot_service.recompute_and_persist_persona_review_summary(
            request_generated_at=datetime.now(timezone.utc).isoformat(),
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Persona review skip failed for delta %s", delta_id)
        raise HTTPException(status_code=503, detail="Persona review could not be skipped.") from exc
    return {
        "message": (
            "Source removed from the review queue without creating owner evidence."
            if payload.scope == "source"
            else "Claim removed from the review queue without creating owner evidence."
        ),
        **result,
        "persona_review_summary": summary_receipt,
    }


@router.post("/persona-review/{delta_id}", response_model=PersonaDelta)
def submit_brain_persona_review(delta_id: str, payload: BrainPersonaReviewRequest):
    try:
        updated = persona_delta_service.apply_brain_review(
            delta_id,
            mode=payload.mode,
            response_kind=payload.response_kind,
            reflection_excerpt=payload.reflection_excerpt,
            resolution_capture_id=payload.resolution_capture_id,
            selected_promotion_items=[item.model_dump(exclude_none=True) for item in payload.selected_promotion_items],
            complete_review=payload.complete_review,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Brain persona review failed for delta %s", delta_id)
        raise HTTPException(status_code=500, detail="Persona review could not be saved.") from exc

    if not updated:
        raise HTTPException(status_code=404, detail="Persona delta not found")

    return annotate_for_brain_queue(updated)


@router.post("/persona-promote/{delta_id}")
def promote_brain_persona_delta(delta_id: str):
    try:
        updated = promote_delta_to_canon(delta_id)
        load_persona_truth.cache_clear()
        overlay = build_committed_persona_overlay()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Brain persona promotion failed for delta %s", delta_id)
        raise HTTPException(status_code=500, detail="Persona promotion could not be committed.") from exc

    if not updated:
        raise HTTPException(status_code=404, detail="Persona delta not found")

    return {
        "message": "Persona promotion committed. Local bundle sync queued.",
        "delta": annotate_for_brain_queue(updated),
        "overlay_counts": overlay.get("counts") if isinstance(overlay, dict) else {},
        "committed_target_files": (updated.metadata or {}).get("committed_target_files") or [],
        "bundle_written_files": (updated.metadata or {}).get("bundle_written_files") or [],
    }


@router.post("/persona-reroute/{delta_id}")
def reroute_brain_persona_delta(delta_id: str, payload: BrainPersonaRerouteRequest):
    try:
        updated = reroute_delta_promotion(delta_id, target_file=payload.target_file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Brain persona reroute failed for delta %s", delta_id)
        raise HTTPException(status_code=500, detail="Persona promotion could not be rerouted.") from exc

    if not updated:
        raise HTTPException(status_code=404, detail="Persona delta not found")

    return {
        "message": f"Queued promotion rerouted to {payload.target_file}. Ready for canon commit.",
        "delta": annotate_for_brain_queue(updated),
        "target_file": payload.target_file,
    }


@router.post("/system-route/{delta_id}")
def route_brain_signal(delta_id: str, payload: BrainSystemRouteRequest):
    try:
        updated, canonical_targets, standup, pm_card, route_results = route_delta_signal(
            delta_id,
            reflection_excerpt=payload.reflection_excerpt,
            selected_promotion_items=[item.model_dump(exclude_none=True) for item in payload.selected_promotion_items],
            workspace_key=payload.workspace_key,
            workspace_keys=payload.workspace_keys,
            canonical_memory_targets=payload.canonical_memory_targets,
            route_to_standup=payload.route_to_standup,
            standup_kind=payload.standup_kind,
            route_to_pm=payload.route_to_pm,
            pm_title=payload.pm_title,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Brain system route failed for delta %s", delta_id)
        raise HTTPException(status_code=500, detail="Brain system route could not be completed.") from exc

    return {
        "message": "Brain triage routed the reviewed signal.",
        "delta": annotate_for_brain_queue(updated),
        "canonical_memory_targets_queued": canonical_targets,
        "standup": standup,
        "pm_card": pm_card,
        "routes": route_results,
    }


@router.post("/memory-sync-status")
def publish_brain_memory_sync_status(payload: BrainCanonicalMemorySyncStatusRequest):
    try:
        snapshot = upsert_snapshot(
            "shared_ops",
            "brain_memory_sync",
            payload.model_dump(),
            metadata={
                "source": payload.source,
                "payload_generated_at": payload.generated_at,
            },
        )
    except Exception as exc:
        logger.exception("Brain memory-sync status persistence failed")
        raise HTTPException(status_code=500, detail="Brain memory-sync status could not be stored.") from exc

    return {
        "message": "Brain canonical-memory sync status stored.",
        "snapshot": snapshot,
    }


@router.post("/operator-story-signals/sync")
def publish_operator_story_signals(payload: BrainOperatorStorySignalsSyncRequest):
    try:
        snapshot = upsert_snapshot(
            payload.workspace_key,
            "operator_story_signals",
            payload.model_dump(),
            metadata={
                "source": payload.source,
                "payload_generated_at": payload.generated_at,
                "signal_count": payload.signal_count,
            },
        )
    except Exception as exc:
        logger.exception("Brain operator-story signal persistence failed")
        raise HTTPException(status_code=500, detail="Operator-story signals could not be stored.") from exc

    return {
        "message": "Operator story signals stored.",
        "snapshot": snapshot,
    }


@router.post("/content-safe-operator-lessons/sync")
def publish_content_safe_operator_lessons(payload: BrainContentSafeOperatorLessonsSyncRequest):
    try:
        snapshot = upsert_snapshot(
            payload.workspace_key,
            "content_safe_operator_lessons",
            payload.model_dump(),
            metadata={
                "source": payload.source,
                "payload_generated_at": payload.generated_at,
                "lesson_count": payload.lesson_count,
                "source_snapshot_type": payload.source_snapshot_type,
            },
        )
    except Exception as exc:
        logger.exception("Brain content-safe lesson persistence failed")
        raise HTTPException(status_code=500, detail="Content-safe operator lessons could not be stored.") from exc

    return {
        "message": "Content-safe operator lessons stored.",
        "snapshot": snapshot,
    }


@router.post("/refresh-persona-review")
def refresh_brain_persona_review():
    return _queue_local_action(
        "refresh_persona_review",
        {},
        message="Brain persona review refresh queued for the signed local runner.",
        job_alias=True,
    )


@router.post("/refresh-feezie-workspace")
def refresh_feezie_workspace():
    return _queue_local_action(
        "refresh_feezie_workspace",
        {},
        message="FEEZIE workspace refresh queued for the signed local runner.",
        job_alias=True,
    )


@router.get("/refresh-feezie-workspace/{card_id}")
def get_feezie_workspace_refresh_status(card_id: str, response: Response):
    response.headers["Cache-Control"] = "no-store, max-age=0"
    try:
        return get_feezie_workspace_refresh_job(card_id)
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 403
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("FEEZIE workspace refresh status is unavailable for card %s", card_id)
        raise HTTPException(
            status_code=503,
            detail="FEEZIE workspace refresh status is unavailable.",
        ) from exc
