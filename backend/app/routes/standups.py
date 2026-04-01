from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException

from app.models import StandupCreate, StandupEntry, StandupPromotionRequest, StandupPromotionResult, StandupUpdate
from app.services import standup_service

router = APIRouter(tags=["Standups"], prefix="/api/standups")


@router.get("/", response_model=List[StandupEntry])
async def list_entries(owner: Optional[str] = None, workspace_key: Optional[str] = None, limit: int = 50):
    return standup_service.list_standups(limit=limit, owner=owner, workspace_key=workspace_key)


@router.post("/", response_model=StandupEntry)
async def create_entry(payload: StandupCreate):
    return standup_service.create_standup(payload)


@router.post("/promote", response_model=StandupPromotionResult)
async def promote_entry(payload: StandupPromotionRequest):
    return standup_service.promote_standup(payload)


@router.patch("/{entry_id}", response_model=StandupEntry)
async def update_entry(entry_id: str, payload: StandupUpdate):
    entry = standup_service.update_standup(entry_id, payload)
    if not entry:
        raise HTTPException(status_code=404, detail="Standup entry not found")
    return entry
