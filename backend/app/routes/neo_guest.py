from __future__ import annotations

import time
from collections import defaultdict, deque
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool

from app.models.neo_guest import (
    NeoGuestAccess,
    NeoGuestMessageCreate,
    NeoGuestMessageLegacyCreate,
    NeoInviteCreate,
    NeoMeetingDecision,
    NeoMeetingRequestCreate,
    NeoMeetingRequestLegacyCreate,
    NeoWorkerClaim,
    NeoWorkerComplete,
    NeoWorkerFail,
    NeoWorkerProgress,
)
from app.services import neo_guest_service as service
from app.services import neo_public_knowledge_service


router = APIRouter(tags=["Neo Guest"], prefix="/api/neo")
_access_attempts: dict[str, deque[float]] = defaultdict(deque)
ACCESS_WINDOW_SECONDS = 15 * 60
ACCESS_ATTEMPT_LIMIT = 8


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store, max-age=0"


def _guest_token(authorization: str | None) -> str:
    value = str(authorization or "").strip()
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return ""


async def _session(authorization: str | None) -> dict:
    try:
        return await run_in_threadpool(service.authenticate_session, _guest_token(authorization))
    except service.NeoGuestUnauthorized as exc:
        raise HTTPException(status_code=401, detail=str(exc))


def _check_access_rate(request: Request) -> None:
    forwarded = str(request.headers.get("x-forwarded-for") or "").split(",", 1)[0].strip()
    key = forwarded or (request.client.host if request.client else "unknown")
    now = time.monotonic()
    attempts = _access_attempts[key]
    while attempts and now - attempts[0] > ACCESS_WINDOW_SECONDS:
        attempts.popleft()
    if len(attempts) >= ACCESS_ATTEMPT_LIMIT:
        raise HTTPException(status_code=429, detail="Too many invite attempts. Try again later.", headers={"Retry-After": "900"})
    attempts.append(now)


@router.get("/admin/knowledge-status")
async def public_knowledge_status(response: Response) -> dict:
    _no_store(response)
    return await run_in_threadpool(
        neo_public_knowledge_service.build_public_knowledge_status
    )


@router.post("/guest/access")
async def guest_access(payload: NeoGuestAccess, request: Request, response: Response) -> dict:
    _no_store(response)
    _check_access_rate(request)
    try:
        return await run_in_threadpool(service.exchange_passcode, payload.passcode)
    except service.NeoGuestUnauthorized as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except service.NeoGuestError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


async def _enqueue_guest_message(
    *,
    session_id: str,
    content: str,
    client_request_id: str,
) -> dict:
    try:
        return await run_in_threadpool(
            service.enqueue_message,
            session_id,
            content,
            client_request_id,
        )
    except service.NeoGuestValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except service.NeoGuestConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except service.NeoGuestUnauthorized as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except service.NeoGuestError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/guest/messages")
async def guest_message(
    payload: NeoGuestMessageLegacyCreate,
    response: Response,
    authorization: str | None = Header(default=None),
) -> dict:
    _no_store(response)
    session = await _session(authorization)
    return await _enqueue_guest_message(
        session_id=str(session["id"]),
        content=payload.content,
        client_request_id=str(payload.client_request_id or uuid4()),
    )


@router.post("/guest/v2/messages")
async def guest_message_v2(
    payload: NeoGuestMessageCreate,
    response: Response,
    authorization: str | None = Header(default=None),
) -> dict:
    _no_store(response)
    session = await _session(authorization)
    return await _enqueue_guest_message(
        session_id=str(session["id"]),
        content=payload.content,
        client_request_id=str(payload.client_request_id),
    )


@router.get("/guest/session")
async def guest_session(
    response: Response,
    authorization: str | None = Header(default=None),
) -> dict:
    _no_store(response)
    session = await _session(authorization)
    try:
        return await run_in_threadpool(
            service.get_session_bootstrap,
            str(session["id"]),
        )
    except service.NeoGuestUnauthorized as exc:
        raise HTTPException(status_code=401, detail=str(exc))


@router.get("/guest/jobs/{job_id}")
async def guest_job(job_id: str, response: Response, authorization: str | None = Header(default=None)) -> dict:
    _no_store(response)
    session = await _session(authorization)
    job = await run_in_threadpool(service.get_job, str(session["id"]), job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Conversation response not found.")
    return job


async def _create_guest_meeting(
    *,
    session_id: str,
    payload: dict,
) -> dict:
    try:
        return await run_in_threadpool(
            service.create_meeting_request,
            session_id,
            payload,
        )
    except service.NeoGuestValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except service.NeoGuestUnauthorized as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except service.NeoGuestConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/guest/meeting-requests")
async def guest_meeting(
    payload: NeoMeetingRequestLegacyCreate,
    response: Response,
    authorization: str | None = Header(default=None),
) -> dict:
    _no_store(response)
    session = await _session(authorization)
    meeting_payload = payload.model_dump()
    meeting_payload["client_request_id"] = payload.client_request_id or uuid4()
    return await _create_guest_meeting(
        session_id=str(session["id"]),
        payload=meeting_payload,
    )


@router.post("/guest/v2/meeting-requests")
async def guest_meeting_v2(
    payload: NeoMeetingRequestCreate,
    response: Response,
    authorization: str | None = Header(default=None),
) -> dict:
    _no_store(response)
    session = await _session(authorization)
    return await _create_guest_meeting(
        session_id=str(session["id"]),
        payload=payload.model_dump(),
    )


@router.post("/worker/capabilities")
async def worker_capabilities(response: Response) -> dict:
    _no_store(response)
    return service.worker_capabilities()


@router.post("/worker/jobs/claim-next")
async def worker_claim(payload: NeoWorkerClaim, response: Response) -> dict:
    _no_store(response)
    job = await run_in_threadpool(service.claim_next_job, payload.worker_id)
    return {"job_available": bool(job), "job": job}


@router.post("/worker/v2/jobs/claim-next")
async def worker_claim_v2(payload: NeoWorkerClaim, response: Response) -> dict:
    _no_store(response)
    job = await run_in_threadpool(service.claim_next_job, payload.worker_id)
    return {
        **service.worker_capabilities(),
        "job_available": bool(job),
        "job": job,
    }


@router.post("/worker/jobs/{job_id}/complete")
async def worker_complete(job_id: str, payload: NeoWorkerComplete, response: Response) -> dict:
    _no_store(response)
    try:
        return await run_in_threadpool(service.complete_job, job_id, payload.worker_id, payload.response)
    except service.NeoGuestConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/worker/jobs/{job_id}/progress")
async def worker_progress(job_id: str, payload: NeoWorkerProgress, response: Response) -> dict:
    _no_store(response)
    try:
        return await run_in_threadpool(service.progress_job, job_id, payload.worker_id, payload.partial_response)
    except service.NeoGuestConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/worker/jobs/{job_id}/fail")
async def worker_fail(job_id: str, payload: NeoWorkerFail, response: Response) -> dict:
    _no_store(response)
    try:
        return await run_in_threadpool(service.fail_job, job_id, payload.worker_id, payload.error)
    except service.NeoGuestConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/operator/inbox")
async def operator_inbox(response: Response) -> dict:
    _no_store(response)
    return await run_in_threadpool(service.operator_inbox)


@router.get("/operator/invites")
async def operator_invites(response: Response) -> dict:
    _no_store(response)
    return {"items": await run_in_threadpool(service.list_invites)}


@router.post("/operator/invites")
async def operator_create_invite(payload: NeoInviteCreate, response: Response) -> dict:
    _no_store(response)
    try:
        return await run_in_threadpool(service.create_invite, label=payload.label, passcode=payload.passcode, expires_at=payload.expires_at)
    except service.NeoGuestConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except service.NeoGuestError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/operator/invites/{invite_id}/revoke")
async def operator_revoke_invite(invite_id: str, response: Response) -> dict:
    _no_store(response)
    try:
        return await run_in_threadpool(service.revoke_invite, invite_id)
    except service.NeoGuestConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.patch("/operator/meeting-requests/{request_id}")
async def operator_decide_meeting(request_id: str, payload: NeoMeetingDecision, response: Response) -> dict:
    _no_store(response)
    try:
        return await run_in_threadpool(service.decide_meeting, request_id, payload.status, payload.owner_notes)
    except service.NeoGuestConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))
