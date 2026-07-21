from __future__ import annotations

import asyncio
import os
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response

from app.models import PersonaDelta, PersonaDeltaCreate, PersonaDeltaResolve, PersonaDeltaUpdate
from app.services import persona_delta_service
from app.services.persona_review_queue_service import annotate_for_brain_queue, prepare_for_brain_queue

router = APIRouter(tags=["Persona"], prefix="/api/persona")


def _read_timeout_setting() -> float:
    try:
        value = float(os.getenv("BRAIN_PERSONA_READ_TIMEOUT_SECONDS", "5.0"))
    except (TypeError, ValueError):
        value = 5.0
    return max(0.1, min(10.0, value))


BRAIN_PERSONA_READ_TIMEOUT_SECONDS = _read_timeout_setting()


@router.get("/deltas", response_model=List[PersonaDelta])
async def list_persona_deltas(
    response: Response,
    status: Optional[str] = None,
    limit: int = 50,
    view: Optional[str] = None,
):
    bounded_limit = max(1, min(int(limit or 50), 100))
    try:
        deltas = await asyncio.wait_for(
            asyncio.to_thread(persona_delta_service.list_deltas, limit=bounded_limit, status=status),
            timeout=BRAIN_PERSONA_READ_TIMEOUT_SECONDS,
        )
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Persona delta read timed out.") from exc
    if (view or "").strip().lower() == "brain_queue":
        response.headers["Cache-Control"] = "no-store, max-age=0"
        return prepare_for_brain_queue(deltas)
    return deltas


@router.get("/deltas/{delta_id}", response_model=PersonaDelta)
async def get_persona_delta(delta_id: UUID, response: Response):
    response.headers["Cache-Control"] = "no-store, max-age=0"
    try:
        delta = await asyncio.wait_for(
            asyncio.to_thread(persona_delta_service.get_delta, str(delta_id)),
            timeout=BRAIN_PERSONA_READ_TIMEOUT_SECONDS,
        )
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Persona delta read timed out.") from exc
    if delta is None:
        raise HTTPException(status_code=404, detail="Persona delta not found")
    return annotate_for_brain_queue(delta)


@router.post("/deltas", response_model=PersonaDelta)
def create_persona_delta(payload: PersonaDeltaCreate):
    return persona_delta_service.create_delta(payload)


@router.patch("/deltas/{delta_id}", response_model=PersonaDelta)
def update_persona_delta(delta_id: UUID, payload: PersonaDeltaUpdate):
    updated = persona_delta_service.update_delta(str(delta_id), payload)
    if not updated:
        raise HTTPException(status_code=404, detail="Persona delta not found")
    return updated


@router.post("/deltas/{delta_id}/resolve", response_model=PersonaDelta)
def resolve_persona_delta(delta_id: UUID, payload: PersonaDeltaResolve):
    updated = persona_delta_service.resolve_delta(str(delta_id), payload)
    if not updated:
        raise HTTPException(status_code=404, detail="Persona delta not found")
    return updated
