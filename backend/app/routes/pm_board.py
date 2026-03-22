from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException

from app.models import PMCard, PMCardCreate, PMCardUpdate
from app.services import pm_card_service

router = APIRouter(tags=["PM Board"], prefix="/api/pm")


@router.get("/cards", response_model=List[PMCard])
async def list_cards(status: Optional[str] = None, owner: Optional[str] = None, limit: int = 100):
    return pm_card_service.list_cards(limit=limit, status=status, owner=owner)


@router.post("/cards", response_model=PMCard)
async def create_card(payload: PMCardCreate):
    return pm_card_service.create_card(payload)


@router.patch("/cards/{card_id}", response_model=PMCard)
async def update_card(card_id: str, payload: PMCardUpdate):
    card = pm_card_service.update_card(card_id, payload)
    if not card:
        raise HTTPException(status_code=404, detail="PM card not found")
    return card
