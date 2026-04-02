from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException

from app.models import (
    ExecutionQueueEntry,
    PMCard,
    PMCardActionRequest,
    PMCardActionResult,
    PMCardCreate,
    PMCardDispatchRequest,
    PMCardDispatchResult,
    PMCardUpdate,
)
from app.services import pm_card_service

router = APIRouter(tags=["PM Board"], prefix="/api/pm")


@router.get("/cards", response_model=List[PMCard])
async def list_cards(
    status: Optional[str] = None,
    owner: Optional[str] = None,
    workspace_key: Optional[str] = None,
    limit: int = 100,
):
    return pm_card_service.list_cards(limit=limit, status=status, owner=owner, workspace_key=workspace_key)


@router.post("/cards", response_model=PMCard)
async def create_card(payload: PMCardCreate):
    return pm_card_service.create_card(payload)


@router.get("/execution-queue", response_model=List[ExecutionQueueEntry])
async def list_execution_queue(
    target_agent: Optional[str] = None,
    manager_agent: Optional[str] = None,
    workspace_key: Optional[str] = None,
    execution_state: Optional[str] = None,
    limit: int = 100,
):
    return pm_card_service.list_execution_queue(
        limit=limit,
        target_agent=target_agent,
        manager_agent=manager_agent,
        workspace_key=workspace_key,
        execution_state=execution_state,
    )


@router.post("/cards/{card_id}/dispatch", response_model=PMCardDispatchResult)
async def dispatch_card(card_id: str, payload: PMCardDispatchRequest):
    result = pm_card_service.dispatch_card(card_id, payload)
    if not result:
        raise HTTPException(status_code=404, detail="PM card not found")
    return result


@router.post("/cards/{card_id}/actions", response_model=PMCardActionResult)
async def act_on_card(card_id: str, payload: PMCardActionRequest):
    result = pm_card_service.act_on_card(card_id, payload)
    if not result:
        raise HTTPException(status_code=404, detail="PM card not found")
    return result


@router.patch("/cards/{card_id}", response_model=PMCard)
async def update_card(card_id: str, payload: PMCardUpdate):
    card = pm_card_service.update_card(card_id, payload)
    if not card:
        raise HTTPException(status_code=404, detail="PM card not found")
    return card
