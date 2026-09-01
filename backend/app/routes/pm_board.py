from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from app.models import (
    ExecutionQueueEntry,
    LinkedinOwnerReviewDecisionRequest,
    PMCard,
    PMCardActionRequest,
    PMCardActionResult,
    PMCardCreate,
    PMCardDispatchRequest,
    PMCardDispatchResult,
    PMExecutionClaimRequest,
    PMExecutionClaimResult,
    PMExecutionGateBackfillRequest,
    PMExecutionGateBackfillResult,
    PMExecutionClaimFailureRequest,
    PMExecutionClaimFailureResult,
    PMExecutionResultCommitRequest,
    PMExecutionResultCommitResult,
    PMStaleExecutionClaimRecoveryRequest,
    PMStaleExecutionClaimRecoveryResult,
    PMHostActionRunRequest,
    PMCardUpdate,
    PMWorkRequestCreate,
    PMWorkRequestResult,
)
from app.services import pm_card_service
from app.services.linkedin_owner_review_service import (
    LinkedinOwnerReviewConflictError,
    LinkedinOwnerReviewNotFoundError,
    record_owner_decision_for_pm_card,
    sync_owner_review_pm_cards,
)
from app.services.pm_loop_canary_service import pm_loop_canary_audit
from app.services.pm_worker_readiness_service import (
    PMWorkerHeartbeatRequest,
    PMWorkerHeartbeatReceipt,
    PMWorkerHeartbeatStorageUnavailable,
    integrated_action_worker_readiness,
    record_pm_worker_heartbeat,
)
from app.services.pm_work_request_service import enqueue_work_request

router = APIRouter(tags=["PM Board"], prefix="/api/pm")

_LEGACY_OWNER_REVIEW_SOURCES = {
    "codex_native:workspace-owner-review",
    "openclaw:workspace-owner-review",
}


def _is_legacy_owner_review_card_like(card: PMCard | PMCardCreate | PMCardUpdate) -> bool:
    payload = getattr(card, "payload", None)
    return bool(
        str(getattr(card, "source", None) or "").strip() in _LEGACY_OWNER_REVIEW_SOURCES
        or str(getattr(card, "link_type", None) or "").strip() == "owner_review"
        or (isinstance(payload, dict) and isinstance(payload.get("owner_review"), dict))
        or (isinstance(payload, dict) and payload.get("legacy_owner_review_compatibility") is True)
    )


def _has_legacy_owner_review_marker(card: PMCard | PMCardCreate | PMCardUpdate) -> bool:
    payload = getattr(card, "payload", None)
    return isinstance(payload, dict) and payload.get("legacy_owner_review_compatibility") is True


def _require_legacy_owner_review_mutation(
    card: PMCard | PMCardCreate | PMCardUpdate,
    *,
    legacy_compatibility: bool,
) -> None:
    if (
        _is_legacy_owner_review_card_like(card)
        and legacy_compatibility is not True
        and not _has_legacy_owner_review_marker(card)
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Historical owner-review PM rows are read-only by default; use the canonical "
                "integrated-content lifecycle or explicitly enable rollback-only compatibility."
            ),
        )


def _legacy_mutation_card(card_id: UUID, *, legacy_compatibility: bool) -> PMCard | None:
    card = pm_card_service.get_card(str(card_id))
    if card is not None:
        _require_legacy_owner_review_mutation(card, legacy_compatibility=legacy_compatibility)
    return card


@router.get("/cards", response_model=List[PMCard])
async def list_cards(
    status: Optional[str] = None,
    owner: Optional[str] = None,
    workspace_key: Optional[str] = None,
    limit: int = 100,
):
    return pm_card_service.decorate_cards_for_client(
        pm_card_service.list_cards(limit=limit, status=status, owner=owner, workspace_key=workspace_key)
    )


@router.get("/cards/{card_id}/execution-source", response_model=PMCard)
async def get_execution_source_card(card_id: UUID):
    card = pm_card_service.get_card(str(card_id))
    if not card:
        raise HTTPException(status_code=404, detail="PM card not found")
    return card


@router.post("/cards", response_model=PMCard)
async def create_card(payload: PMCardCreate, legacy_compatibility: bool = False):
    _require_legacy_owner_review_mutation(payload, legacy_compatibility=legacy_compatibility)
    if _is_legacy_owner_review_card_like(payload) and legacy_compatibility is True:
        payload = payload.model_copy(
            update={
                "payload": {
                    **dict(payload.payload or {}),
                    "legacy_owner_review_compatibility": True,
                }
            }
        )
    try:
        card = pm_card_service.create_card(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return pm_card_service.decorate_card_for_client(card)


@router.post("/request-work", response_model=PMWorkRequestResult)
async def request_work(payload: PMWorkRequestCreate):
    try:
        return enqueue_work_request(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/owner-review/sync")
async def sync_owner_review_cards(legacy_compatibility: bool = False):
    try:
        return sync_owner_review_pm_cards(legacy_compatibility=legacy_compatibility)
    except LinkedinOwnerReviewConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/review-hygiene/auto-resolve")
async def auto_resolve_review_hygiene(legacy_compatibility: bool = False):
    return pm_card_service.auto_resolve_review_cards(
        legacy_owner_review_compatibility=legacy_compatibility,
    )


@router.post("/review-hygiene/auto-progress")
async def auto_progress_review_hygiene(limit: int = 250, legacy_compatibility: bool = False):
    return pm_card_service.auto_progress_review_cards(
        limit=limit,
        legacy_owner_review_compatibility=legacy_compatibility,
    )


@router.get("/review-hygiene/audit")
async def review_hygiene_audit(limit: int = 12, hours: int = 24):
    return pm_card_service.review_hygiene_audit(limit=limit, hours=hours)


@router.get("/canary-audit")
async def canary_audit(limit: int = 500):
    return pm_loop_canary_audit(limit=limit)


@router.get("/execution-queue", response_model=List[ExecutionQueueEntry])
async def list_execution_queue(
    target_agent: Optional[str] = None,
    manager_agent: Optional[str] = None,
    workspace_key: Optional[str] = None,
    execution_state: Optional[str] = None,
    limit: int = 100,
    legacy_compatibility: bool = False,
):
    return pm_card_service.list_execution_queue(
        limit=limit,
        target_agent=target_agent,
        manager_agent=manager_agent,
        workspace_key=workspace_key,
        execution_state=execution_state,
        legacy_owner_review_compatibility=legacy_compatibility,
    )


@router.post("/worker-heartbeat", response_model=PMWorkerHeartbeatReceipt)
async def record_worker_heartbeat(payload: PMWorkerHeartbeatRequest):
    try:
        return await run_in_threadpool(record_pm_worker_heartbeat, payload)
    except PMWorkerHeartbeatStorageUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail="PM worker heartbeat storage is unavailable.",
        ) from exc


@router.get("/worker-readiness")
async def get_worker_readiness(action: str):
    try:
        return await run_in_threadpool(integrated_action_worker_readiness, action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/admin/execution-gates/backfill",
    response_model=PMExecutionGateBackfillResult,
)
async def backfill_execution_gates(payload: PMExecutionGateBackfillRequest, legacy_compatibility: bool = False):
    try:
        compatibility_kwargs = (
            {"legacy_owner_review_compatibility": True} if legacy_compatibility is True else {}
        )
        return await run_in_threadpool(
            pm_card_service.backfill_execution_gates,
            payload,
            **compatibility_kwargs,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/cards/{card_id}/dispatch", response_model=PMCardDispatchResult)
async def dispatch_card(card_id: UUID, payload: PMCardDispatchRequest, legacy_compatibility: bool = False):
    _legacy_mutation_card(card_id, legacy_compatibility=legacy_compatibility)
    try:
        compatibility_kwargs = (
            {"legacy_owner_review_compatibility": True} if legacy_compatibility is True else {}
        )
        result = pm_card_service.dispatch_card(str(card_id), payload, **compatibility_kwargs)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not result:
        raise HTTPException(status_code=404, detail="PM card not found")
    return PMCardDispatchResult(
        card=pm_card_service.decorate_card_for_client(result.card) or result.card,
        queue_entry=result.queue_entry,
    )


@router.post("/cards/{card_id}/execution-result", response_model=PMExecutionResultCommitResult)
async def commit_execution_result(
    card_id: UUID,
    payload: PMExecutionResultCommitRequest,
    legacy_compatibility: bool = False,
):
    try:
        compatibility_kwargs = (
            {"legacy_owner_review_compatibility": True} if legacy_compatibility is True else {}
        )
        committed = pm_card_service.commit_execution_result(str(card_id), payload, **compatibility_kwargs)
    except pm_card_service.PMExecutionResultCommitConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if committed is None:
        raise HTTPException(status_code=404, detail="PM card not found")

    card, disposition = committed
    legacy_mutation_allowed = legacy_compatibility is True or _has_legacy_owner_review_marker(card)
    auto_progressed = False
    if payload.status == "review":
        try:
            progression = pm_card_service.auto_progress_card(
                str(card_id),
                record_audit=False,
                legacy_owner_review_compatibility=legacy_mutation_allowed,
            )
        except Exception:
            progression = None
        if isinstance(progression, dict):
            auto_progressed = bool(progression.get("processed"))
            progressed_card = progression.get("card")
            if isinstance(progressed_card, dict) and progressed_card.get("id"):
                card = PMCard.model_validate(progressed_card)
    return PMExecutionResultCommitResult(
        card=card,
        disposition=disposition,
        auto_progressed=auto_progressed,
    )


@router.post("/cards/{card_id}/claim-execution", response_model=PMExecutionClaimResult)
async def claim_execution(card_id: UUID, payload: PMExecutionClaimRequest, legacy_compatibility: bool = False):
    try:
        compatibility_kwargs = (
            {"legacy_owner_review_compatibility": True} if legacy_compatibility is True else {}
        )
        claimed = pm_card_service.claim_execution(str(card_id), payload, **compatibility_kwargs)
    except pm_card_service.PMExecutionClaimConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if claimed is None:
        raise HTTPException(status_code=404, detail="PM card not found")
    card, disposition = claimed
    return PMExecutionClaimResult(card=card, disposition=disposition)


@router.post("/cards/{card_id}/fail-execution-claim", response_model=PMExecutionClaimFailureResult)
async def fail_execution_claim(
    card_id: UUID,
    payload: PMExecutionClaimFailureRequest,
    legacy_compatibility: bool = False,
):
    try:
        compatibility_kwargs = (
            {"legacy_owner_review_compatibility": True} if legacy_compatibility is True else {}
        )
        failed = pm_card_service.fail_execution_claim(str(card_id), payload, **compatibility_kwargs)
    except pm_card_service.PMExecutionClaimFailureConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if failed is None:
        raise HTTPException(status_code=404, detail="PM card not found")
    card, disposition = failed
    return PMExecutionClaimFailureResult(card=card, disposition=disposition)


@router.post("/execution-claims/recover-stale", response_model=PMStaleExecutionClaimRecoveryResult)
async def recover_stale_execution_claims(
    payload: PMStaleExecutionClaimRecoveryRequest,
    legacy_compatibility: bool = False,
):
    compatibility_kwargs = (
        {"legacy_owner_review_compatibility": True} if legacy_compatibility is True else {}
    )
    return pm_card_service.recover_stale_execution_claims(payload, **compatibility_kwargs)


@router.post("/cards/{card_id}/actions", response_model=PMCardActionResult)
async def act_on_card(card_id: UUID, payload: PMCardActionRequest, legacy_compatibility: bool = False):
    _legacy_mutation_card(card_id, legacy_compatibility=legacy_compatibility)
    try:
        compatibility_kwargs = (
            {"legacy_owner_review_compatibility": True} if legacy_compatibility is True else {}
        )
        result = pm_card_service.act_on_card(str(card_id), payload, **compatibility_kwargs)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not result:
        raise HTTPException(status_code=404, detail="PM card not found")
    return PMCardActionResult(
        card=pm_card_service.decorate_card_for_client(result.card) or result.card,
        queue_entry=result.queue_entry,
        successor_card=pm_card_service.decorate_card_for_client(result.successor_card) if result.successor_card else None,
    )


@router.post("/cards/{card_id}/auto-progress")
async def auto_progress_card(
    card_id: UUID,
    limit: int = 250,
    record_audit: bool = False,
    legacy_compatibility: bool = False,
):
    return pm_card_service.auto_progress_card(
        str(card_id),
        limit=limit,
        record_audit=record_audit,
        legacy_owner_review_compatibility=legacy_compatibility,
    )


@router.post("/cards/{card_id}/host-action/run", response_model=PMCardActionResult)
async def run_host_action(card_id: UUID, payload: PMHostActionRunRequest, legacy_compatibility: bool = False):
    _legacy_mutation_card(card_id, legacy_compatibility=legacy_compatibility)
    try:
        compatibility_kwargs = (
            {"legacy_owner_review_compatibility": True} if legacy_compatibility is True else {}
        )
        result = pm_card_service.queue_host_action_automation(
            str(card_id),
            **compatibility_kwargs,
            requested_by=payload.requested_by,
            reason=payload.reason,
            proof_items=payload.proof_items,
            proof_field_values=[entry.model_dump() for entry in payload.proof_field_values],
            scheduled_at=payload.scheduled_at,
            asset_decision=payload.asset_decision,
            confirmation_path=payload.confirmation_path,
            queue_id=payload.queue_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not result:
        raise HTTPException(status_code=404, detail="PM card not found")
    return PMCardActionResult(
        card=pm_card_service.decorate_card_for_client(result.card) or result.card,
        queue_entry=result.queue_entry,
        successor_card=pm_card_service.decorate_card_for_client(result.successor_card) if result.successor_card else None,
    )


@router.post("/cards/{card_id}/owner-review")
async def act_on_owner_review_card(
    card_id: UUID,
    payload: LinkedinOwnerReviewDecisionRequest,
    legacy_compatibility: bool = False,
):
    try:
        return record_owner_decision_for_pm_card(
            str(card_id),
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


@router.patch("/cards/{card_id}", response_model=PMCard)
async def update_card(card_id: UUID, payload: PMCardUpdate, legacy_compatibility: bool = False):
    _legacy_mutation_card(card_id, legacy_compatibility=legacy_compatibility)
    _require_legacy_owner_review_mutation(payload, legacy_compatibility=legacy_compatibility)
    if _is_legacy_owner_review_card_like(payload) and legacy_compatibility is True and payload.payload is not None:
        payload = payload.model_copy(
            update={
                "payload": {
                    **dict(payload.payload or {}),
                    "legacy_owner_review_compatibility": True,
                }
            }
        )
    try:
        card = pm_card_service.update_card(str(card_id), payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not card:
        raise HTTPException(status_code=404, detail="PM card not found")
    return pm_card_service.decorate_card_for_client(card)
