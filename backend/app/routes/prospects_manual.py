from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.models import Prospect
from app.services import firestore_client
from app.services.local_store import save_prospect

router = APIRouter(prefix="/prospects/manual", tags=["Prospects"])


@router.post("/", response_model=Prospect)
async def create_prospect(prospect: Prospect):
    if not prospect.id:
        prospect.id = str(uuid.uuid4())

    payload = prospect.model_dump()
    if firestore_client.get_firestore_client() is not None:
        firestore_client.write_document("prospects", prospect.id, payload)
    else:
        save_prospect(prospect)
    return prospect
