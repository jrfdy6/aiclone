from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response

from app.models.social_assist import SocialEngagementActionRequest, SocialEngagementOpportunityCreate
from app.services.social_engagement_assist_service import (
    ProhibitedSocialMutation,
    RemoteSocialAssistAuthorityUnavailable,
    SocialEngagementAssistError,
    SocialEngagementConflict,
    SocialEngagementOpportunityNotFound,
    default_social_engagement_assist_service,
)


router = APIRouter(tags=["Social Assist"], prefix="/api/workspace/social-assist")
NO_STORE_HEADERS = {"Cache-Control": "no-store, max-age=0"}
REMOTE_AUTHORITY_UNAVAILABLE = (
    "Remote social assistance is temporarily unavailable while its signed local-authority queue is inactive."
)


@router.get("/opportunities")
def list_social_engagement_opportunities(response: Response, limit: int = Query(50, ge=1, le=100)):
    response.headers["Cache-Control"] = "no-store, max-age=0"
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
