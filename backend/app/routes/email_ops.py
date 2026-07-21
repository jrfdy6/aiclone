from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Response

from app.models import (
    EmailProviderStatusResponse,
    EmailSyncResponse,
    EmailThread,
    EmailThreadDraftRequest,
    EmailThreadDraftResponse,
    EmailThreadDraftLifecycleRequest,
    EmailThreadDraftLifecycleResponse,
    EmailThreadEscalateRequest,
    EmailThreadEscalateResponse,
    EmailThreadListResponse,
    EmailThreadRouteRequest,
    EmailThreadSaveDraftRequest,
    EmailThreadSaveDraftResponse,
)
from app.services.gmail_inbox_service import gmail_connection_status
from app.services.email_draft_canary_service import build_email_draft_canary_report
from app.services.email_ops_service import (
    escalate_thread,
    generate_draft,
    get_thread,
    list_threads,
    reroute_thread,
    restore_auto_route,
    save_thread_draft,
    sync_threads,
    update_thread_draft_lifecycle,
)

router = APIRouter(tags=["Email Ops"], prefix="/api/email")


@router.get("/google/status", response_model=EmailProviderStatusResponse)
async def get_gmail_provider_status():
    try:
        return EmailProviderStatusResponse(**gmail_connection_status())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/canary")
async def get_email_draft_canary(response: Response):
    try:
        response.headers["Cache-Control"] = "no-store, max-age=0"
        return build_email_draft_canary_report()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/threads", response_model=EmailThreadListResponse)
async def get_email_threads(
    workspace_key: Optional[str] = None,
    lane: Optional[str] = None,
    needs_human: Optional[bool] = None,
    high_value: Optional[bool] = None,
    limit: int = 100,
):
    try:
        return list_threads(
            workspace_key=workspace_key,
            lane=lane,
            needs_human=needs_human,
            high_value=high_value,
            limit=limit,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/threads/{thread_id}", response_model=EmailThread)
async def get_email_thread(thread_id: str):
    thread = get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Email thread not found")
    return thread


@router.post("/sync", response_model=EmailSyncResponse)
async def post_email_sync():
    try:
        return sync_threads()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/threads/{thread_id}/route", response_model=EmailThread)
async def post_email_route(thread_id: str, payload: EmailThreadRouteRequest):
    try:
        return reroute_thread(thread_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/threads/{thread_id}/route/reset", response_model=EmailThread)
async def post_email_route_reset(thread_id: str):
    try:
        return restore_auto_route(thread_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/threads/{thread_id}/draft", response_model=EmailThreadDraftResponse)
async def post_email_draft(thread_id: str, payload: EmailThreadDraftRequest):
    try:
        return await generate_draft(thread_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/threads/{thread_id}/draft/save", response_model=EmailThreadSaveDraftResponse)
async def post_email_draft_save(thread_id: str, payload: EmailThreadSaveDraftRequest):
    try:
        return save_thread_draft(thread_id, overwrite_existing=payload.overwrite_existing)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/threads/{thread_id}/draft/lifecycle", response_model=EmailThreadDraftLifecycleResponse)
async def post_email_draft_lifecycle(thread_id: str, payload: EmailThreadDraftLifecycleRequest):
    try:
        thread, message = update_thread_draft_lifecycle(thread_id, action=payload.action)
        return EmailThreadDraftLifecycleResponse(
            thread=thread,
            action=payload.action,
            message=message,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/threads/{thread_id}/escalate", response_model=EmailThreadEscalateResponse)
async def post_email_escalate(thread_id: str, payload: EmailThreadEscalateRequest):
    try:
        return escalate_thread(thread_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
