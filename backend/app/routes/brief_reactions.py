from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

from app.models import BriefReaction, BriefReactionCreate, BriefReactionCreateResponse
from app.services import brief_reaction_service

router = APIRouter(tags=["Daily Brief Reactions"], prefix="/api/briefs")


@router.get("/{brief_id}/reactions", response_model=list[BriefReaction])
async def list_brief_reactions(brief_id: str, item_key: Optional[str] = None, limit: int = 100):
    keys = [item_key] if item_key else None
    return brief_reaction_service.list_reactions(brief_id=brief_id, item_keys=keys, limit=limit)


@router.post("/reactions", response_model=BriefReactionCreateResponse)
async def create_brief_reaction(payload: BriefReactionCreate):
    try:
        return brief_reaction_service.create_reaction(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
