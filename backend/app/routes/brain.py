from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
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
    BrainPersonaReviewRequest,
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
    PersonaDelta,
)
from app.services import persona_delta_service
from app.services.brain_local_action_queue_service import (
    authorize_brain_local_action_card,
    enqueue_brain_local_action,
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
from app.services.work_lifecycle_service import build_work_lifecycle_report
from app.services.workspace_snapshot_store import (
    delete_snapshot_types,
    list_snapshot_payloads,
    upsert_snapshot,
    upsert_snapshot_monotonic,
)
from app.services.youtube_watchlist_service import build_persisted_youtube_watchlist_payload

router = APIRouter(tags=["Brain"], prefix="/api/brain")
logger = logging.getLogger(__name__)


def _bounded_timeout_setting(name: str, default: float, maximum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(0.1, min(maximum, value))


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
    include_source_intelligence: bool = True,
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
        "video_count": sum(
            len(channel.get("videos") or [])
            for channel in payload.channels
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
        }.items()
        if isinstance(value, dict)
    }
    results: dict[str, dict[str, Any]] = {}
    try:
        for response_key, snapshot_payload in snapshots.items():
            if response_key == "publication_performance_lifecycle":
                identity_token = str(snapshot_payload.get("identity_token") or "").strip().lower()
                snapshot_type = f"publication_performance_lifecycle:{identity_token}"
            elif response_key == "feezie_runtime_context":
                snapshot_type = FEEZIE_RUNTIME_CONTEXT_SNAPSHOT_TYPE
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
