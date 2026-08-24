from __future__ import annotations

import json
import os
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Response

from app.models.social_assist import (
    SocialEngagementActionRequest,
    SocialEngagementOpportunityCreate,
    SocialEngagementProjectionSyncRequest,
)
from app.services.brain_local_action_queue_service import (
    enqueue_brain_local_action,
    get_social_engagement_job,
)
from app.services.social_engagement_assist_service import (
    ALLOWED_ASSISTED_ACTIONS,
    PROHIBITED_PLATFORM_MUTATIONS,
    ProhibitedSocialMutation,
    RemoteSocialAssistAuthorityUnavailable,
    SocialEngagementAssistError,
    SocialEngagementConflict,
    SocialEngagementOpportunityNotFound,
    default_social_engagement_assist_service,
)
from app.services.social_engagement_projection_service import (
    PROJECTION_SCHEMA,
    SNAPSHOT_TYPE,
    SYNC_SCHEMA,
    WORKSPACE_KEY,
    projection_sha256,
    validate_social_engagement_projection,
)
from app.services.workspace_snapshot_store import get_snapshot_payload, upsert_snapshot_monotonic


router = APIRouter(tags=["Social Assist"], prefix="/api/workspace/social-assist")
NO_STORE_HEADERS = {"Cache-Control": "no-store, max-age=0"}
REMOTE_AUTHORITY_UNAVAILABLE = (
    "Remote social assistance is temporarily unavailable while its signed local-authority queue is inactive."
)


def _is_remote_runtime() -> bool:
    return any(
        str(os.getenv(name) or "").strip()
        for name in (
            "RAILWAY_PROJECT_ID",
            "RAILWAY_ENVIRONMENT",
            "RAILWAY_ENVIRONMENT_ID",
            "RAILWAY_SERVICE_ID",
        )
    )


def _queue_local_social_action(action: str, parameters: dict) -> dict:
    try:
        card, disposition = enqueue_brain_local_action(action, parameters)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc), headers=NO_STORE_HEADERS) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=REMOTE_AUTHORITY_UNAVAILABLE, headers=NO_STORE_HEADERS) from exc
    return {
        "schema_version": "social_engagement_queue_receipt/v1",
        "queued": True,
        "state": "queued",
        "disposition": disposition,
        "action": action,
        "job_id": card.id,
        "card_id": card.id,
        "owner_execution_required": True,
        "external_mutation_performed": False,
    }


@router.get("/opportunities")
def list_social_engagement_opportunities(response: Response, limit: int = Query(50, ge=1, le=100)):
    response.headers["Cache-Control"] = "no-store, max-age=0"
    if _is_remote_runtime():
        try:
            projection = get_snapshot_payload(WORKSPACE_KEY, SNAPSHOT_TYPE)
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail="Assisted social opportunities are temporarily unavailable.",
                headers=NO_STORE_HEADERS,
            ) from exc
        if projection is None:
            raise HTTPException(
                status_code=503,
                detail="Assisted social opportunities have not been synchronized from the local authority.",
                headers=NO_STORE_HEADERS,
            )
        try:
            validated = validate_social_engagement_projection(projection)
        except SocialEngagementAssistError as exc:
            raise HTTPException(
                status_code=503,
                detail="Assisted social opportunities failed integrity validation.",
                headers=NO_STORE_HEADERS,
            ) from exc
        return {
            "schema_version": "social_engagement_opportunity_list/v1",
            "opportunities": validated["opportunities"][:limit],
            "owner_execution_required": True,
            "automatic_platform_mutation": False,
            "authority": validated["authority"],
            "generated_at": validated["generated_at"],
        }
    try:
        opportunities = default_social_engagement_assist_service().list_opportunities(limit=limit)
    except RemoteSocialAssistAuthorityUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail=REMOTE_AUTHORITY_UNAVAILABLE,
            headers=NO_STORE_HEADERS,
        ) from exc
    except SocialEngagementAssistError as exc:
        raise HTTPException(
            status_code=503,
            detail="Assisted social opportunities are unavailable.",
            headers=NO_STORE_HEADERS,
        ) from exc
    return {
        "schema_version": "social_engagement_opportunity_list/v1",
        "opportunities": opportunities,
        "owner_execution_required": True,
        "automatic_platform_mutation": False,
    }


@router.post("/opportunities", status_code=201)
def create_social_engagement_opportunity(payload: SocialEngagementOpportunityCreate, response: Response):
    response.headers["Cache-Control"] = "no-store, max-age=0"
    if _is_remote_runtime():
        response.status_code = 202
        return _queue_local_social_action(
            "social_engagement_capture",
            {"request": payload.model_dump(mode="json", exclude_none=True)},
        )
    try:
        opportunity = default_social_engagement_assist_service().capture_opportunity(**payload.model_dump())
    except RemoteSocialAssistAuthorityUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail=REMOTE_AUTHORITY_UNAVAILABLE,
            headers=NO_STORE_HEADERS,
        ) from exc
    except SocialEngagementConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc), headers=NO_STORE_HEADERS) from exc
    except SocialEngagementAssistError as exc:
        raise HTTPException(status_code=400, detail=str(exc), headers=NO_STORE_HEADERS) from exc
    return opportunity


@router.post("/opportunities/{opportunity_id}/actions")
def prepare_social_engagement_action(
    opportunity_id: str,
    payload: SocialEngagementActionRequest,
    response: Response,
):
    response.headers["Cache-Control"] = "no-store, max-age=0"
    normalized_action = str(payload.action or "").strip().lower()
    if normalized_action in PROHIBITED_PLATFORM_MUTATIONS:
        raise HTTPException(
            status_code=403,
            detail=f"{normalized_action} is owner-executed only; backend social mutation is prohibited",
            headers=NO_STORE_HEADERS,
        )
    if normalized_action not in ALLOWED_ASSISTED_ACTIONS:
        raise HTTPException(
            status_code=400,
            detail="action must be prepare_copy or open_native_surface",
            headers=NO_STORE_HEADERS,
        )
    if _is_remote_runtime():
        return _queue_local_social_action(
            "social_engagement_action",
            {
                "opportunity_id": opportunity_id,
                "request": payload.model_dump(mode="json", exclude_none=True),
            },
        )
    try:
        return default_social_engagement_assist_service().prepare_action(
            opportunity_id=opportunity_id,
            action=payload.action,
            request_id=payload.request_id,
        )
    except RemoteSocialAssistAuthorityUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail=REMOTE_AUTHORITY_UNAVAILABLE,
            headers=NO_STORE_HEADERS,
        ) from exc
    except ProhibitedSocialMutation as exc:
        raise HTTPException(status_code=403, detail=str(exc), headers=NO_STORE_HEADERS) from exc
    except SocialEngagementConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc), headers=NO_STORE_HEADERS) from exc
    except SocialEngagementOpportunityNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc), headers=NO_STORE_HEADERS) from exc
    except SocialEngagementAssistError as exc:
        raise HTTPException(status_code=400, detail=str(exc), headers=NO_STORE_HEADERS) from exc


@router.get("/jobs/{card_id}")
def get_social_engagement_action_job(card_id: str, response: Response):
    response.headers["Cache-Control"] = "no-store, max-age=0"
    try:
        return get_social_engagement_job(card_id)
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 403
        raise HTTPException(status_code=status_code, detail=str(exc), headers=NO_STORE_HEADERS) from exc


@router.post("/projection/sync")
def sync_social_engagement_projection(
    payload: SocialEngagementProjectionSyncRequest,
    response: Response,
):
    response.headers["Cache-Control"] = "no-store, max-age=0"
    if payload.schema_version != SYNC_SCHEMA:
        raise HTTPException(status_code=400, detail="Unsupported social engagement projection sync schema.")
    try:
        projection = validate_social_engagement_projection(payload.projection)
        if payload.generated_at != projection["generated_at"]:
            raise SocialEngagementAssistError("projection sync timestamp does not match its payload")
        generated_at = datetime.fromisoformat(projection["generated_at"])
        encoded = json.dumps(
            projection,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        digest = projection_sha256(projection)
        snapshot, stored = upsert_snapshot_monotonic(
            WORKSPACE_KEY,
            SNAPSHOT_TYPE,
            projection,
            generated_at=generated_at,
            metadata={
                "authority": "local_sql",
                "projection_schema": PROJECTION_SCHEMA,
                "projection_sha256": digest,
                "projection_bytes": len(encoded),
                "item_count": projection["counts"]["opportunities"],
                "remote_role": "bounded_owner_review_projection",
            },
        )
    except SocialEngagementAssistError as exc:
        raise HTTPException(status_code=400, detail=str(exc), headers=NO_STORE_HEADERS) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Social engagement projection storage is unavailable.",
            headers=NO_STORE_HEADERS,
        ) from exc
    if snapshot is None:
        raise HTTPException(
            status_code=503,
            detail="Social engagement projection storage is unavailable.",
            headers=NO_STORE_HEADERS,
        )
    current_payload = snapshot.get("payload") if isinstance(snapshot, dict) else None
    current_sha256 = projection_sha256(current_payload) if isinstance(current_payload, dict) else None
    disposition = "stored" if stored else "idempotent_same_hash" if current_sha256 == digest else "stale_ignored"
    return {
        "schema_version": "social_engagement_assist_projection_sync_receipt/v1",
        "disposition": disposition,
        "payload_sha256": digest,
        "projection_bytes": len(encoded),
        "item_count": projection["counts"]["opportunities"],
        "snapshot_id": snapshot.get("id"),
        "updated_at": snapshot.get("updated_at"),
    }
