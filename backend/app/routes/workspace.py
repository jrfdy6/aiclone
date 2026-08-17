from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, Response, UploadFile
from starlette.concurrency import run_in_threadpool

from app.models import (
    IngestSignalRequest,
    LinkedinOwnerReviewDecisionRequest,
    LinkedinPerformanceLocalActionRequest,
    RefreshSocialFeedRequest,
)
from app.services.brain_local_action_queue_service import (
    enqueue_brain_local_action,
    get_linkedin_performance_record_job,
)
from app.services import social_feed_refresh_service
from app.services.linkedin_owner_review_service import (
    LinkedinOwnerReviewConflictError,
    LinkedinOwnerReviewNotFoundError,
    list_owner_review_items,
    record_owner_decision,
)
from app.services.linkedin_performance_ledger_service import (
    CANONICAL_WORKSPACE_KEY,
    LIFECYCLE_PROJECTION_SCHEMA,
    LIFECYCLE_PROJECTION_WORKSPACE_KEY,
    SNAPSHOT_TYPE,
    STATUS_SNAPSHOT_TYPE,
    build_browser_performance_summary,
    linkedin_performance_identity_token,
    linkedin_performance_lifecycle_snapshot_type,
    linkedin_performance_ledger_service,
)
from app.services.workspace_registry_service import WORKSPACES_ROOT, workspace_registry_payload
from app.services.social_feed_preview_service import social_feed_preview_service
from app.services.social_feed_refresh import InvalidRefreshState
from app.services.workspace_snapshot_service import (
    project_linkedin_os_snapshot_for_browser,
    workspace_snapshot_service,
)
from app.services.workspace_snapshot_store import get_snapshot_payload
router = APIRouter(tags=["Workspace"], prefix="/api/workspace")

WORKSPACE_IMAGE_CONTENT_TYPES = {"image/png", "image/jpeg", "image/webp"}
WORKSPACE_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
WORKSPACE_IMAGE_MAX_BYTES = 10 * 1024 * 1024


def _browser_refresh_status(status: dict) -> dict:
    """Project refresh telemetry without forwarding raw failure text."""

    projected: dict[str, None | bool | str | list[str]] = {
        "running": status.get("running") is True,
        "state": "idle",
        "run_id": None,
        "queued_at": None,
        "last_run": None,
        "started_at": None,
        "completed_at": None,
        "error_type": None,
        "reason_codes": [],
    }
    raw_state = str(status.get("state") or "").strip().lower()
    if raw_state in {"idle", "queued", "running", "succeeded", "failed"}:
        projected["state"] = raw_state
    elif status.get("error"):
        projected["state"] = "failed"
    elif status.get("running") is True:
        projected["state"] = "running"
    elif status.get("last_run"):
        projected["state"] = "succeeded"

    run_id = str(status.get("run_id") or "").strip()
    if run_id:
        projected["run_id"] = run_id

    for key in ("queued_at", "last_run", "started_at", "completed_at"):
        value = status.get(key)
        if isinstance(value, datetime):
            if value.tzinfo is not None:
                projected[key] = value.astimezone(timezone.utc).isoformat()
            continue
        if not isinstance(value, str) or not value.strip():
            continue
        text = value.strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            continue
        if parsed.tzinfo is not None:
            projected[key] = parsed.astimezone(timezone.utc).isoformat()
    if status.get("error"):
        projected["error_type"] = "social_feed_refresh_error"
        projected["reason_codes"] = ["social_feed_refresh_failed"]
    return projected


def _resolve_workspace_image_target(raw_path: str) -> tuple[str, Path]:
    text = str(raw_path or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Artifact path is required.")
    candidate = Path(text)
    if candidate.is_absolute():
        raise HTTPException(status_code=400, detail="Artifact path must be repo-relative.")
    if any(part in {"..", ""} for part in candidate.parts):
        raise HTTPException(status_code=400, detail="Artifact path must stay inside the workspaces tree.")
    if not candidate.parts or candidate.parts[0] != "workspaces":
        raise HTTPException(status_code=400, detail="Artifact path must start with `workspaces/`.")
    normalized = candidate.as_posix()
    if Path(normalized).suffix.lower() not in WORKSPACE_IMAGE_SUFFIXES:
        raise HTTPException(status_code=400, detail="Only .png, .jpg, .jpeg, or .webp workspace images are allowed.")
    workspaces_root = WORKSPACES_ROOT.resolve()
    target = (workspaces_root.parent / normalized).resolve()
    if target != workspaces_root and workspaces_root not in target.parents:
        raise HTTPException(status_code=400, detail="Artifact path must resolve inside the repo workspaces root.")
    return normalized, target


def _redact_publication_evidence_from_source_lifecycle(value):
    """Keep source workflow state while removing exact publication evidence."""

    if isinstance(value, dict):
        if value.get("stage") == "published":
            return None
        result = {}
        publication_confirmation = value.get("source_kind") == "publication_confirmation"
        for raw_key, item in value.items():
            key = str(raw_key)
            if key in {"error", "error_message", "exception", "traceback", "error_type"}:
                continue
            if key in {"publication_url", "publication_id"}:
                continue
            if publication_confirmation and key in {"source_url", "evidence", "match_keys"}:
                continue
            redacted = _redact_publication_evidence_from_source_lifecycle(item)
            if redacted is not None:
                result[key] = redacted
        return result
    if isinstance(value, list):
        return [
            redacted
            for item in value
            if (redacted := _redact_publication_evidence_from_source_lifecycle(item)) is not None
        ]
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered.startswith((
            "https://linkedin.com/posts/",
            "https://www.linkedin.com/posts/",
            "https://linkedin.com/feed/update/",
            "https://www.linkedin.com/feed/update/",
            "url:https://linkedin.com/posts/",
            "url:https://www.linkedin.com/posts/",
            "url:https://linkedin.com/feed/update/",
            "url:https://www.linkedin.com/feed/update/",
        )):
            return None
    return value


def _browser_source_lifecycle(value: dict) -> dict:
    failure_present = any(
        value.get(key)
        for key in ("error", "error_message", "exception", "traceback", "error_type")
    )
    projected = _redact_publication_evidence_from_source_lifecycle(value)
    if not isinstance(projected, dict):
        projected = {}
    if failure_present:
        projected["error_type"] = "source_lifecycle_build_error"
        projected["reason_codes"] = ["source_lifecycle_build_failed"]
    return projected


def _exact_lifecycle_response(
    *,
    content_id: str,
    content_version_sha256: str,
    projection: dict | None,
    verification_state: str,
) -> dict:
    approval_completed = False
    publication_confirmed = False
    published_at = None
    if projection is not None:
        approval_completed = projection.get("approval_completed") is True
        publication_confirmed = projection.get("publication_confirmed") is True
        published_at = projection.get("published_at") if publication_confirmed else None
    return {
        "schema_version": LIFECYCLE_PROJECTION_SCHEMA,
        "verification_state": verification_state,
        "content_id": content_id,
        "content_version_sha256": content_version_sha256,
        "approval_completed": approval_completed,
        "publication_confirmed": publication_confirmed,
        "published_at": published_at,
        "data_policy": {
            "exact_identity_query": True,
            "global_lifecycle_rows_included": False,
            "external_post_link_included": False,
            "raw_metrics_included": False,
            "private_notes_included": False,
            "audience_identities_included": False,
            "raw_copy_included": False,
        },
    }


@router.get("/registry")
async def get_workspace_registry(response: Response, include_executive: bool = True):
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return workspace_registry_payload(include_executive=include_executive)


@router.get("/refresh-social-feed")
async def get_social_feed_refresh_status():
    status = social_feed_refresh_service.get_status()
    projected = _browser_refresh_status(status)
    if projected.get("error_type"):
        projected["error"] = "Social feed refresh failed."
    return projected


@router.get("/linkedin-os-snapshot")
async def get_linkedin_os_snapshot(response: Response):
    response.headers["Cache-Control"] = "no-store, max-age=0"
    try:
        snapshot = await run_in_threadpool(
            workspace_snapshot_service.get_linkedin_os_snapshot,
            persisted_only=True,
        )
        snapshot = project_linkedin_os_snapshot_for_browser(snapshot)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "schema_version": "workspace_snapshot_error/v1",
                "error_type": "workspace_snapshot_read_error",
                "reason_codes": ["workspace_snapshot_unavailable"],
            },
            headers={"Cache-Control": "no-store, max-age=0"},
        ) from exc
    # The browser contract is aggregate-only even if a legacy or mocked
    # snapshot source still carries file rows.  Full bodies, snippets, names,
    # and paths remain local and must never cross this route boundary.
    snapshot["workspace_files"] = []
    snapshot["doc_entries"] = []
    snapshot["publication_performance_summary"] = build_browser_performance_summary(
        snapshot.get("publication_performance_summary")
    )
    if isinstance(snapshot.get("source_lifecycle"), dict):
        snapshot["source_lifecycle"] = _browser_source_lifecycle(
            snapshot["source_lifecycle"]
        )
    refresh_status = snapshot.get("refresh_status")
    if isinstance(refresh_status, dict):
        snapshot["refresh_status"] = _browser_refresh_status(refresh_status)
    return snapshot


@router.get("/linkedin-source-grounding-status")
async def get_linkedin_source_grounding_status(response: Response):
    response.headers["Cache-Control"] = "no-store, max-age=0"
    try:
        return await run_in_threadpool(workspace_snapshot_service.get_source_grounding_status)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=type(exc).__name__) from exc


@router.get("/linkedin-os-owner-review")
async def get_linkedin_os_owner_review(include_resolved: bool = False):
    try:
        return list_owner_review_items(include_resolved=include_resolved)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/linkedin-os-owner-review/{queue_id}")
async def post_linkedin_os_owner_review(queue_id: str, payload: LinkedinOwnerReviewDecisionRequest):
    try:
        return record_owner_decision(queue_id, payload.decision, payload.notes)
    except LinkedinOwnerReviewNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except LinkedinOwnerReviewConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/linkedin-performance/events")
def post_linkedin_performance_event(payload: LinkedinPerformanceLocalActionRequest):
    """Queue privacy-minimized evidence for the canonical local FEEZIE ledger."""

    try:
        card, disposition = enqueue_brain_local_action(
            "linkedin_performance_record",
            {"request": payload.model_dump(mode="json", exclude_none=True)},
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "queued": True,
        "status": "queued",
        "disposition": disposition,
        "job_id": card.id,
        "card_id": card.id,
        "created_at": card.created_at,
        "updated_at": card.updated_at,
        "data_policy": {
            "canonical_writer": "private feezie-os append-only ledger",
            "railway_role": "signed transport and privacy-minimized projection only",
            "raw_copy_accepted": False,
            "private_notes_accepted": False,
        },
    }


@router.get("/linkedin-performance/lifecycle")
def get_linkedin_performance_lifecycle(
    response: Response,
    content_id: str = Query(
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$",
    ),
    content_version_sha256: str = Query(
        min_length=64,
        max_length=71,
        pattern=r"^(?:sha256:)?[A-Fa-f0-9]{64}$",
    ),
):
    """Return verified lifecycle state for one exact ID + digest, never a list."""

    response.headers["Cache-Control"] = "no-store, max-age=0"
    normalized_content_id = " ".join(content_id.split()).strip()
    try:
        identity_token = linkedin_performance_identity_token(
            normalized_content_id,
            content_version_sha256,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    normalized_digest = content_version_sha256.strip().lower()
    if normalized_digest.startswith("sha256:"):
        normalized_digest = normalized_digest[len("sha256:"):]
    snapshot_type = linkedin_performance_lifecycle_snapshot_type(identity_token)
    try:
        projection = get_snapshot_payload(LIFECYCLE_PROJECTION_WORKSPACE_KEY, snapshot_type)
        status_projection = get_snapshot_payload(CANONICAL_WORKSPACE_KEY, STATUS_SNAPSHOT_TYPE)
        summary_projection = get_snapshot_payload(CANONICAL_WORKSPACE_KEY, SNAPSHOT_TYPE)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Lifecycle verification storage is unavailable.") from exc

    if projection is not None:
        if (
            projection.get("schema_version") != LIFECYCLE_PROJECTION_SCHEMA
            or projection.get("workspace_key") != CANONICAL_WORKSPACE_KEY
            or projection.get("identity_token") != identity_token
            or not isinstance(projection.get("approval_completed"), bool)
            or not isinstance(projection.get("publication_confirmed"), bool)
            or (
                projection.get("publication_confirmed") is True
                and (
                    projection.get("approval_completed") is not True
                    or not isinstance(projection.get("published_at"), str)
                )
            )
        ):
            raise HTTPException(status_code=500, detail="Exact lifecycle projection is invalid.")
        return _exact_lifecycle_response(
            content_id=normalized_content_id,
            content_version_sha256=normalized_digest,
            projection=projection,
            verification_state="verified",
        )

    # A persisted aggregate status proves the projection store was reached;
    # absence of this exact opaque key then means no lifecycle evidence exists.
    if isinstance(status_projection, dict) or isinstance(summary_projection, dict):
        return _exact_lifecycle_response(
            content_id=normalized_content_id,
            content_version_sha256=normalized_digest,
            projection=None,
            verification_state="not_recorded",
        )

    # Local development may have the canonical ledger without Postgres.  Use
    # it only for this exact identity and never return rows or event details.
    try:
        local_projection = linkedin_performance_ledger_service.build_lifecycle_projection(
            normalized_content_id,
            normalized_digest,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Lifecycle verification is unavailable.") from exc
    if local_projection.get("approval_completed") or local_projection.get("publication_confirmed"):
        return _exact_lifecycle_response(
            content_id=normalized_content_id,
            content_version_sha256=normalized_digest,
            projection=local_projection,
            verification_state="verified_local",
        )
    return _exact_lifecycle_response(
        content_id=normalized_content_id,
        content_version_sha256=normalized_digest,
        projection=None,
        verification_state="unavailable",
    )


@router.get("/linkedin-performance/jobs/{card_id}")
def get_linkedin_performance_job(card_id: str, response: Response):
    response.headers["Cache-Control"] = "no-store, max-age=0"
    try:
        return get_linkedin_performance_record_job(card_id)
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 403
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post("/refresh-social-feed")
async def refresh_social_feed(payload: RefreshSocialFeedRequest, background_tasks: BackgroundTasks):
    try:
        queued = social_feed_refresh_service.queue_refresh()
    except InvalidRefreshState:
        raise HTTPException(status_code=409, detail="Social feed refresh already running.")
    run_id = str(queued.get("run_id") or "")
    background_tasks.add_task(
        social_feed_refresh_service.run_refresh_background,
        run_id,
        payload.skip_fetch,
        payload.sources,
    )
    queued_status = _browser_refresh_status(queued)
    return {
        "status": "queued",
        "state": queued_status.get("state"),
        "run_id": run_id,
        "skip_fetch": payload.skip_fetch,
        "sources": payload.sources,
        "queued_at": queued_status.get("queued_at"),
        # Kept for the already-deployed frontend while the run-id client rolls out.
        "started_at": queued_status.get("queued_at"),
    }


@router.post("/ingest-signal")
async def ingest_signal(payload: IngestSignalRequest):
    try:
        preview_item = social_feed_preview_service.generate_preview(
            url=payload.url,
            text=payload.text,
            title=payload.title,
            priority_lane=payload.priority_lane,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {
        "message": "Signal preview generated",
        "preview_item": preview_item,
    }


@router.post("/artifacts/upload-image")
async def upload_workspace_image(path: str = Form(...), image: UploadFile = File(...)):
    content_type = str(image.content_type or "").strip().lower()
    if content_type not in WORKSPACE_IMAGE_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Only PNG, JPEG, or WEBP images can be uploaded to workspace artifacts.")
    normalized_path, target_path = _resolve_workspace_image_target(path)
    payload = await image.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Uploaded image was empty.")
    if len(payload) > WORKSPACE_IMAGE_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded image exceeds the 10 MB workspace artifact limit.")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(payload)
    return {
        "path": normalized_path,
        "content_type": content_type,
        "bytes_written": len(payload),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
