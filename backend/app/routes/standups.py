from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException

from app.models import StandupCreate, StandupEntry, StandupPromotionRequest, StandupPromotionResult, StandupUpdate
from app.services import standup_service

router = APIRouter(tags=["Standups"], prefix="/api/standups")


@router.get("/", response_model=List[StandupEntry])
async def list_entries(owner: Optional[str] = None, workspace_key: Optional[str] = None, limit: int = 50):
    entries = standup_service.list_standups(limit=limit, owner=owner, workspace_key=workspace_key)
    return standup_service.public_standup_entries(entries)


@router.post("/", response_model=StandupEntry)
async def create_entry(payload: StandupCreate):
    try:
        entry = standup_service.create_standup(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return standup_service.public_standup_entry(entry)


@router.post("/promote", response_model=StandupPromotionResult)
async def promote_entry(payload: StandupPromotionRequest):
    try:
        result = standup_service.promote_standup(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return standup_service.public_standup_promotion(result)


@router.patch("/{entry_id}", response_model=StandupEntry)
async def update_entry(entry_id: str, payload: StandupUpdate):
    try:
        entry = standup_service.update_standup(entry_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not entry:
        raise HTTPException(status_code=404, detail="Standup entry not found")
    return standup_service.public_standup_entry(entry)
