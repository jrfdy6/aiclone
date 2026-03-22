from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException

from app.models import PersonaDelta, PersonaDeltaCreate, PersonaDeltaResolve, PersonaDeltaUpdate
from app.services import persona_delta_service

router = APIRouter(tags=["Persona"], prefix="/api/persona")


@router.get("/deltas", response_model=List[PersonaDelta])
async def list_persona_deltas(status: Optional[str] = None, limit: int = 50):
    return persona_delta_service.list_deltas(limit=limit, status=status)


@router.post("/deltas", response_model=PersonaDelta)
async def create_persona_delta(payload: PersonaDeltaCreate):
    return persona_delta_service.create_delta(payload)


@router.patch("/deltas/{delta_id}", response_model=PersonaDelta)
async def update_persona_delta(delta_id: str, payload: PersonaDeltaUpdate):
    updated = persona_delta_service.update_delta(delta_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail="Persona delta not found")
    return updated


@router.post("/deltas/{delta_id}/resolve", response_model=PersonaDelta)
async def resolve_persona_delta(delta_id: str, payload: PersonaDeltaResolve):
    updated = persona_delta_service.resolve_delta(delta_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail="Persona delta not found")
    return updated
