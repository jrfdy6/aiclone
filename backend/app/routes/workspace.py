from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import tempfile

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, Response, UploadFile
from starlette.concurrency import run_in_threadpool
from runtime_paths import workspace_state_path

from app.models import (
    IngestSignalRequest,
    LinkedinOwnerReviewDecisionRequest,
    LinkedinPerformanceLocalActionRequest,
    CanonicalDecisionActionRequest,
    CanonicalDecisionCreateRequest,
    IntegratedContentVariantRequest,
    IntegratedOwnerPostRequest,
    IntegratedContentManualEditRequest,
    IntegratedContentLearningRequest,
    IntegratedPersonaReversalRequest,
    RefreshSocialFeedRequest,
)
from app.services.brain_local_action_queue_service import (
    enqueue_brain_local_action,
    get_linkedin_performance_record_job,
    get_integrated_content_variant_job,
    get_integrated_owner_post_job,
    get_integrated_content_owner_action_job,
    get_integrated_persona_action_job,
    get_canonical_decision_job,
    validate_owner_mutable_canonical_decision_type,
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
from app.services.workspace_registry_service import workspace_registry_payload
from app.services.social_feed_preview_service import social_feed_preview_service
from app.services.social_feed_refresh import InvalidRefreshState, RefreshStatusStoreUnavailable
from app.services.workspace_snapshot_service import (
    project_linkedin_os_snapshot_for_browser,
    workspace_snapshot_service,
)
from app.services.workspace_snapshot_store import get_snapshot_payload
from app.services.integrated_content_projection_service import (
    SNAPSHOT_TYPE as INTEGRATED_CONTENT_SNAPSHOT_TYPE,
    WORKSPACE_KEY as INTEGRATED_CONTENT_WORKSPACE_KEY,
    apply_current_controller_readiness,
    build_integrated_content_projection,
    unavailable_integrated_content_projection,
    validate_integrated_content_projection,
)
from app.services.integrated_controller_readiness_service import (
    CONTROLLER_DATABASE_UNAVAILABLE,
    CONTROLLER_QUEUE_UNAVAILABLE,
    READINESS_MESSAGES as CONTROLLER_READINESS_MESSAGES,
    integrated_controller_queue_readiness,
)
from app.services.integrated_variant_generation_service import (
    VARIANT_POST_ALREADY_PUBLISHED,
    VARIANT_GENERATION_MESSAGES,
)
from app.services.ops_standup_projection_service import (
    SNAPSHOT_TYPE as OPS_STANDUP_SNAPSHOT_TYPE,
    WORKSPACE_KEY as OPS_STANDUP_WORKSPACE_KEY,
    build_ops_standup_projection,
    unavailable_ops_standup_projection,
    validate_ops_standup_projection,
)
from app.services.ops_workspace_goal_projection_service import (
    SNAPSHOT_TYPE as OPS_WORKSPACE_GOAL_SNAPSHOT_TYPE,
    WORKSPACE_KEY as OPS_WORKSPACE_GOAL_WORKSPACE_KEY,
    build_ops_workspace_goal_projection,
    unavailable_ops_workspace_goal_projection,
    validate_ops_workspace_goal_projection,
)
router = APIRouter(tags=["Workspace"], prefix="/api/workspace")

WORKSPACE_IMAGE_CONTENT_TYPES = {"image/png", "image/jpeg", "image/webp"}
WORKSPACE_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
WORKSPACE_IMAGE_MAX_BYTES = 10 * 1024 * 1024
WORKSPACE_IMAGE_WORKSPACE_KEY = "feezie-os"
WORKSPACE_IMAGE_LOGICAL_ROOT = Path("workspaces/linkedin-content-os")
INTEGRATED_OWNER_ACTION_ERROR_SCHEMA = "integrated_owner_action_error/v1"
_OWNER_ACTION_ERROR_MESSAGES = {
    **CONTROLLER_READINESS_MESSAGES,
    **VARIANT_GENERATION_MESSAGES,
    "invalid_owner_action_request": "The owner action request is invalid.",
    "variant_parent_not_found": "The requested parent revision is not available.",
    "variant_parent_readiness_unavailable": (
        "Variant generation is unavailable until current revision safety can be verified."
    ),
    "canonical_decision_owner_authority_unverified": (
        "This record is not verified as an owner decision on both canonical views. No owner action was queued."
    ),
}


def _owner_action_http_error(reason_code: str, *, status_code: int) -> HTTPException:
    message = _OWNER_ACTION_ERROR_MESSAGES.get(
        reason_code,
        CONTROLLER_READINESS_MESSAGES[CONTROLLER_QUEUE_UNAVAILABLE],
    )
    return HTTPException(
        status_code=status_code,
        detail={
            "schema_version": INTEGRATED_OWNER_ACTION_ERROR_SCHEMA,
            "reason_code": reason_code,
            "message": message,
        },
        headers={"Cache-Control": "no-store, max-age=0"},
    )


def _enqueue_integrated_owner_action(action: str, parameters: dict):
    try:
        readiness = integrated_controller_queue_readiness(action)
        reason_code = str(readiness.get("reason_code") or "")
    except Exception:
        readiness = {"ready": False}
        reason_code = CONTROLLER_QUEUE_UNAVAILABLE
    if readiness.get("ready") is not True:
        if reason_code not in CONTROLLER_READINESS_MESSAGES:
            reason_code = CONTROLLER_QUEUE_UNAVAILABLE
        raise _owner_action_http_error(reason_code, status_code=503)
    try:
        return enqueue_brain_local_action(action, parameters)
    except ValueError as exc:
        raise _owner_action_http_error(
            "invalid_owner_action_request",
            status_code=400,
        ) from exc
    except Exception as exc:
        try:
            readiness = integrated_controller_queue_readiness(action)
            reason_code = str(readiness.get("reason_code") or "")
        except Exception:
            reason_code = CONTROLLER_QUEUE_UNAVAILABLE
        if reason_code not in CONTROLLER_READINESS_MESSAGES:
            reason_code = CONTROLLER_QUEUE_UNAVAILABLE
        raise _owner_action_http_error(reason_code, status_code=503) from exc


def _projected_variant_parent_eligibility(
    *, post_id: str, parent_revision_id: str
) -> dict:
    try:
        projection = get_snapshot_payload(
            INTEGRATED_CONTENT_WORKSPACE_KEY,
            INTEGRATED_CONTENT_SNAPSHOT_TYPE,
        )
    except Exception as exc:
        raise _owner_action_http_error(
            CONTROLLER_DATABASE_UNAVAILABLE,
            status_code=503,
        ) from exc
    if projection is None and _local_canonical_projection_enabled():
        try:
            projection = build_integrated_content_projection()
        except Exception as exc:
            raise _owner_action_http_error(
                "variant_parent_readiness_unavailable",
                status_code=503,
            ) from exc
    if projection is None:
        raise _owner_action_http_error(
            "variant_parent_readiness_unavailable",
            status_code=503,
        )
    try:
        projection = validate_integrated_content_projection(projection)
    except Exception as exc:
        if not _local_canonical_projection_enabled():
            raise _owner_action_http_error(
                "variant_parent_readiness_unavailable",
                status_code=503,
            ) from exc
        try:
            projection = build_integrated_content_projection()
        except Exception as fallback_exc:
            raise _owner_action_http_error(
                "variant_parent_readiness_unavailable",
                status_code=503,
            ) from fallback_exc
    post = next(
        (item for item in projection["posts"] if item.get("post_id") == post_id),
        None,
    )
    revision = next(
        (
            item
            for item in (post or {}).get("revisions", [])
            if item.get("revision_id") == parent_revision_id
        ),
        None,
    )
    if revision is None:
        raise _owner_action_http_error("variant_parent_not_found", status_code=404)
    if post.get("status") == "published":
        raise _owner_action_http_error(
            VARIANT_POST_ALREADY_PUBLISHED,
            status_code=409,
        )
    eligibility = revision["variant_generation"]
    if eligibility.get("eligible") is not True:
        raise _owner_action_http_error(
            str(eligibility["reason_code"]),
            status_code=409,
        )
    return eligibility


def _projected_owner_mutable_canonical_decision_type(
    *, decision_id: str, expected_version: int
) -> str:
    """Verify one owner decision against both bounded canonical projections."""

    try:
        content = get_snapshot_payload(
            INTEGRATED_CONTENT_WORKSPACE_KEY,
            INTEGRATED_CONTENT_SNAPSHOT_TYPE,
        )
        ops = get_snapshot_payload(OPS_STANDUP_WORKSPACE_KEY, OPS_STANDUP_SNAPSHOT_TYPE)
        if _local_canonical_projection_enabled():
            content = content or build_integrated_content_projection()
            ops = ops or build_ops_standup_projection()
        if content is None or ops is None:
            raise ValueError("canonical decision projections are unavailable")
        content = validate_integrated_content_projection(content)
        ops = validate_ops_standup_projection(ops)
        content_rows = (
            ((content.get("activity_summary") or {}).get("decisions") or {}).get("recent")
            or []
        )
        ops_rows = ops.get("canonical_decisions") or []
        matches: list[dict] = []
        for rows in (content_rows, ops_rows):
            candidates = [
                item
                for item in rows
                if isinstance(item, dict)
                and str(item.get("decision_id") or "").strip() == decision_id
            ]
            if len(candidates) != 1:
                raise ValueError("canonical decision is not exact on both projections")
            matches.append(candidates[0])
        content_decision, ops_decision = matches
        content_type = validate_owner_mutable_canonical_decision_type(
            content_decision.get("decision_type")
        )
        ops_type = validate_owner_mutable_canonical_decision_type(
            ops_decision.get("decision_type")
        )
        if content_type != ops_type:
            raise ValueError("canonical decision types conflict")
        for item in matches:
            state_version = item.get("state_version")
            if (
                not isinstance(state_version, int)
                or isinstance(state_version, bool)
                or state_version != expected_version
            ):
                raise ValueError("canonical decision version is not current")
        if content_decision.get("status") != ops_decision.get("status"):
            raise ValueError("canonical decision states conflict")
        return content_type
    except HTTPException:
        raise
    except Exception as exc:
        raise _owner_action_http_error(
            "canonical_decision_owner_authority_unverified",
            status_code=409,
        ) from exc


def _local_canonical_projection_enabled() -> bool:
    """Permit direct canonical reads only in an explicitly enabled local runtime."""

    return str(os.getenv("AI_CLONE_LOCAL_CANONICAL_PROJECTION") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


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


def _workspace_image_upload_available() -> bool:
    """Uploads are local-only until Railway has a durable Mac handoff."""

    return not any(
        str(os.getenv(name) or "").strip()
        for name in (
            "RAILWAY_DEPLOYMENT_ID",
            "RAILWAY_ENVIRONMENT",
            "RAILWAY_ENVIRONMENT_ID",
            "RAILWAY_PROJECT_ID",
            "RAILWAY_SERVICE_ID",
        )
    )


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
    try:
        relative = candidate.relative_to(WORKSPACE_IMAGE_LOGICAL_ROOT)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Artifact path must stay inside the LinkedIn content workspace.",
        ) from exc
    if relative == Path("."):
        raise HTTPException(status_code=400, detail="Artifact path must name an image.")
    try:
        target = workspace_state_path(WORKSPACE_IMAGE_WORKSPACE_KEY, relative)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Artifact path is invalid.") from exc
    return normalized, target


def _workspace_image_signature(payload: bytes) -> str | None:
    if len(payload) >= 24 and payload.startswith(b"\x89PNG\r\n\x1a\n") and payload[12:16] == b"IHDR":
        return "image/png"
    if len(payload) >= 4 and payload.startswith(b"\xff\xd8\xff") and payload.endswith(b"\xff\xd9"):
        return "image/jpeg"
    if len(payload) >= 12 and payload.startswith(b"RIFF") and payload[8:12] == b"WEBP":
        return "image/webp"
    return None


def _persist_workspace_image(target: Path, payload: bytes, digest: str) -> bool:
    """Atomically create a private artifact; exact replay is idempotent."""

    if target.exists():
        if target.is_symlink() or not target.is_file():
            raise HTTPException(status_code=409, detail="Artifact target is not a regular file.")
        if hashlib.sha256(target.read_bytes()).hexdigest() == digest:
            return True
        raise HTTPException(status_code=409, detail="Artifact path already contains different bytes.")

    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary_raw = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".upload",
        dir=str(target.parent),
    )
    temporary = Path(temporary_raw)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, target)
            return False
        except FileExistsError:
            if target.is_file() and not target.is_symlink():
                if hashlib.sha256(target.read_bytes()).hexdigest() == digest:
                    return True
            raise HTTPException(status_code=409, detail="Artifact path already contains different bytes.")
    finally:
        temporary.unlink(missing_ok=True)


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


@router.get("/integrated-content")
def get_integrated_content_projection(response: Response):
    response.headers["Cache-Control"] = "no-store, max-age=0"
    try:
        payload = get_snapshot_payload(INTEGRATED_CONTENT_WORKSPACE_KEY, INTEGRATED_CONTENT_SNAPSHOT_TYPE)
    except Exception:
        if _local_canonical_projection_enabled():
            return build_integrated_content_projection()
        return unavailable_integrated_content_projection("projection_storage_unavailable")
    if payload is None:
        if _local_canonical_projection_enabled():
            return build_integrated_content_projection()
        return unavailable_integrated_content_projection("projection_not_synced")
    try:
        validated = validate_integrated_content_projection(payload)
        return apply_current_controller_readiness(validated)
    except Exception:
        if _local_canonical_projection_enabled():
            try:
                return build_integrated_content_projection()
            except Exception:
                pass
        return unavailable_integrated_content_projection("projection_invalid")


@router.get("/ops-standup")
def get_ops_standup_projection(response: Response):
    response.headers["Cache-Control"] = "no-store, max-age=0"
    try:
        payload = get_snapshot_payload(OPS_STANDUP_WORKSPACE_KEY, OPS_STANDUP_SNAPSHOT_TYPE)
    except Exception:
        if _local_canonical_projection_enabled():
            return build_ops_standup_projection()
        return unavailable_ops_standup_projection("projection_storage_unavailable")
    if payload is None:
        if _local_canonical_projection_enabled():
            return build_ops_standup_projection()
        return unavailable_ops_standup_projection("projection_not_synced")
    try:
        return validate_ops_standup_projection(payload)
    except Exception:
        return unavailable_ops_standup_projection("projection_invalid")


@router.get("/ops-workspace-goals")
def get_ops_workspace_goal_projection(response: Response):
    response.headers["Cache-Control"] = "no-store, max-age=0"
    try:
        payload = get_snapshot_payload(
            OPS_WORKSPACE_GOAL_WORKSPACE_KEY,
            OPS_WORKSPACE_GOAL_SNAPSHOT_TYPE,
        )
    except Exception:
        if _local_canonical_projection_enabled():
            try:
                return build_ops_workspace_goal_projection()
            except Exception:
                pass
        return unavailable_ops_workspace_goal_projection(
            "workspace_goal_projection_storage_unavailable"
        )
    if payload is None:
        if _local_canonical_projection_enabled():
            try:
                return build_ops_workspace_goal_projection()
            except Exception:
                pass
        return unavailable_ops_workspace_goal_projection(
            "workspace_goal_projection_not_synced"
        )
    try:
        return validate_ops_workspace_goal_projection(payload)
    except Exception:
        return unavailable_ops_workspace_goal_projection(
            "workspace_goal_projection_invalid"
        )


@router.post("/integrated-content/variants")
def request_integrated_content_variant(payload: IntegratedContentVariantRequest):
    _projected_variant_parent_eligibility(
        post_id=payload.post_id,
        parent_revision_id=payload.parent_revision_id,
    )
    card, disposition = _enqueue_integrated_owner_action(
        "integrated_content_variant",
        {"request": payload.model_dump(mode="json")},
    )
    return {
        "queued": True, "status": "queued", "disposition": disposition,
        "job_id": card.id, "card_id": card.id,
        "created_at": card.created_at, "updated_at": card.updated_at,
    }


@router.get("/integrated-content/variants/{card_id}")
def get_integrated_content_variant_status(card_id: str):
    try:
        return get_integrated_content_variant_job(card_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/integrated-content/owner-posts")
def request_integrated_owner_post(payload: IntegratedOwnerPostRequest):
    card, disposition = _enqueue_integrated_owner_action(
        "integrated_owner_post",
        {"request": payload.model_dump(mode="json")},
    )
    return {"queued": True, "status": "queued", "disposition": disposition, "job_id": card.id, "card_id": card.id, "created_at": card.created_at, "updated_at": card.updated_at}


@router.get("/integrated-content/owner-posts/{card_id}")
def get_integrated_owner_post_status(card_id: str):
    try:
        return get_integrated_owner_post_job(card_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/integrated-content/manual-edits")
def request_integrated_content_manual_edit(payload: IntegratedContentManualEditRequest):
    card, disposition = _enqueue_integrated_owner_action(
        "integrated_content_manual_edit",
        {"request": payload.model_dump(mode="json")},
    )
    return {
        "queued": True,
        "status": "queued",
        "disposition": disposition,
        "job_id": card.id,
        "card_id": card.id,
        "created_at": card.created_at,
        "updated_at": card.updated_at,
    }


@router.post("/integrated-content/learning-actions")
def request_integrated_content_learning_action(payload: IntegratedContentLearningRequest):
    card, disposition = _enqueue_integrated_owner_action(
        "integrated_content_learning",
        {"request": payload.model_dump(mode="json", exclude_none=True)},
    )
    return {
        "queued": True,
        "status": "queued",
        "disposition": disposition,
        "job_id": card.id,
        "card_id": card.id,
        "created_at": card.created_at,
        "updated_at": card.updated_at,
    }


@router.get("/integrated-content/owner-actions/{card_id}")
def get_integrated_content_owner_action_status(card_id: str):
    try:
        return get_integrated_content_owner_action_job(card_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/integrated-content/persona-reversals")
def request_integrated_persona_reversal(payload: IntegratedPersonaReversalRequest):
    card, disposition = _enqueue_integrated_owner_action(
        "integrated_persona_reversal",
        {"request": payload.model_dump(mode="json")},
    )
    return {
        "queued": True,
        "status": "queued",
        "disposition": disposition,
        "job_id": card.id,
        "card_id": card.id,
        "created_at": card.created_at,
        "updated_at": card.updated_at,
    }


@router.get("/integrated-content/persona-actions/{card_id}")
def get_integrated_persona_action_status(card_id: str):
    try:
        return get_integrated_persona_action_job(card_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/decisions")
def request_canonical_decision(payload: CanonicalDecisionCreateRequest):
    """Queue one compact, signed mutation for the canonical local decision store."""

    card, disposition = _enqueue_integrated_owner_action(
        "canonical_decision_create",
        {"request": payload.model_dump(mode="json", exclude_none=True)},
    )
    return {
        "queued": True,
        "status": "queued",
        "disposition": disposition,
        "job_id": card.id,
        "card_id": card.id,
        "created_at": card.created_at,
        "updated_at": card.updated_at,
    }


@router.post("/decisions/{decision_id}/actions")
def request_canonical_decision_action(
    decision_id: str,
    payload: CanonicalDecisionActionRequest,
):
    """Queue an optimistic transition; the local runner revalidates before write."""

    if not decision_id.strip() or len(decision_id) > 128:
        raise _owner_action_http_error(
            "invalid_owner_action_request",
            status_code=400,
        )
    normalized_decision_id = decision_id.strip()
    expected_decision_type = _projected_owner_mutable_canonical_decision_type(
        decision_id=normalized_decision_id,
        expected_version=payload.expected_version,
    )
    card, disposition = _enqueue_integrated_owner_action(
        "canonical_decision_transition",
        {
            "decision_id": normalized_decision_id,
            "expected_decision_type": expected_decision_type,
            "request": payload.model_dump(mode="json", exclude_none=True),
        },
    )
    return {
        "queued": True,
        "status": "queued",
        "disposition": disposition,
        "job_id": card.id,
        "card_id": card.id,
        "created_at": card.created_at,
        "updated_at": card.updated_at,
    }


@router.get("/decisions/jobs/{card_id}")
def get_canonical_decision_status(card_id: str):
    try:
        return get_canonical_decision_job(card_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/linkedin-os-owner-review")
async def get_linkedin_os_owner_review(include_resolved: bool = False):
    try:
        return list_owner_review_items(include_resolved=include_resolved)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail="LinkedIn owner-review items are temporarily unavailable."
        ) from exc


@router.post("/linkedin-os-owner-review/{queue_id}")
async def post_linkedin_os_owner_review(
    queue_id: str,
    payload: LinkedinOwnerReviewDecisionRequest,
    legacy_compatibility: bool = False,
):
    try:
        return record_owner_decision(
            queue_id,
            payload.decision,
            payload.notes,
            legacy_compatibility=legacy_compatibility,
        )
    except LinkedinOwnerReviewNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except LinkedinOwnerReviewConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail="LinkedIn owner-review decision could not be recorded."
        ) from exc


@router.post("/linkedin-performance/events")
def post_linkedin_performance_event(
    payload: LinkedinPerformanceLocalActionRequest,
    legacy_compatibility: bool = False,
):
    """Queue a rollback-only write to the historical private JSONL ledger.

    Canonical posts use ``/integrated-content/learning-actions``.  Requiring an
    explicit query switch keeps old banked-post tooling recoverable without
    leaving its JSONL ledger as a second default writable authority.
    """

    if not legacy_compatibility:
        raise HTTPException(
            status_code=409,
            detail=(
                "The legacy LinkedIn performance writer is disabled by default; "
                "use canonical integrated-content learning actions or explicitly "
                "enable the rollback-only compatibility path."
            ),
        )

    try:
        card, disposition = enqueue_brain_local_action(
            "linkedin_performance_record",
            {
                "legacy_compatibility": True,
                "request": payload.model_dump(mode="json", exclude_none=True),
            },
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
            "writer": "private feezie-os JSONL compatibility ledger",
            "authority": "rollback_only",
            "canonical_writer": "integrated local SQL learning events",
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
    except RefreshStatusStoreUnavailable:
        raise HTTPException(status_code=503, detail="Social feed refresh status is unavailable.")
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
        raise HTTPException(status_code=500, detail="Signal preview generation failed.") from exc
    return {
        "message": "Signal preview generated",
        "preview_item": preview_item,
    }


@router.post("/artifacts/upload-image")
async def upload_workspace_image(path: str = Form(...), image: UploadFile = File(...)):
    if not _workspace_image_upload_available():
        raise HTTPException(
            status_code=503,
            detail="Screenshot upload is unavailable until durable local artifact handoff is configured.",
        )
    content_type = str(image.content_type or "").strip().lower()
    if content_type not in WORKSPACE_IMAGE_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Only PNG, JPEG, or WEBP images can be uploaded to workspace artifacts.")
    normalized_path, target_path = _resolve_workspace_image_target(path)
    payload = await image.read(WORKSPACE_IMAGE_MAX_BYTES + 1)
    if not payload:
        raise HTTPException(status_code=400, detail="Uploaded image was empty.")
    if len(payload) > WORKSPACE_IMAGE_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded image exceeds the 10 MB workspace artifact limit.")
    detected_type = _workspace_image_signature(payload)
    if detected_type != content_type:
        raise HTTPException(status_code=400, detail="Uploaded bytes do not match the declared image type.")
    expected_type = "image/jpeg" if target_path.suffix.lower() in {".jpg", ".jpeg"} else f"image/{target_path.suffix.lower()[1:]}"
    if detected_type != expected_type:
        raise HTTPException(status_code=400, detail="Uploaded bytes do not match the artifact extension.")
    digest = hashlib.sha256(payload).hexdigest()
    reused = await run_in_threadpool(_persist_workspace_image, target_path, payload, digest)
    return {
        "path": normalized_path,
        "artifact_id": f"sha256:{digest}",
        "sha256": digest,
        "content_type": content_type,
        "bytes_written": len(payload),
        "reused": reused,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
