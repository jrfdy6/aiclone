from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException

from app.models import Playbook
from app.services import firestore_client
from app.services.local_store import load_local_playbooks

router = APIRouter(prefix="/playbooks", tags=["Playbooks"])


def _load_from_firestore() -> List[Playbook]:
    payload = firestore_client.list_documents("playbooks")
    if not payload:
        return []
    return [Playbook(**item) for item in payload]


@router.get("/", response_model=List[Playbook])
async def list_playbooks(category: Optional[str] = None):
    playbooks = _load_from_firestore() or load_local_playbooks()
    if category:
        playbooks = [p for p in playbooks if p.category.lower() == category.lower()]
    return playbooks


@router.get("/{playbook_id}", response_model=Playbook)
async def get_playbook(playbook_id: str):
    doc = firestore_client.get_document("playbooks", playbook_id)
    if doc:
        return Playbook(**doc)
    for item in load_local_playbooks():
        if item.id == playbook_id:
            return item
    raise HTTPException(status_code=404, detail="Playbook not found")
