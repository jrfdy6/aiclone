from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter

from app.models import Prospect
from app.services import firestore_client
from app.services.local_store import load_cached_prospects

router = APIRouter(prefix="/prospects", tags=["Prospects"])


def _load_from_firestore() -> List[Prospect]:
    payload = firestore_client.list_documents("prospects")
    if not payload:
        return []
    return [Prospect(**item) for item in payload]


def _filter(prospects: List[Prospect], category: Optional[str], has_email: Optional[bool]) -> List[Prospect]:
    results = prospects
    if category:
        results = [p for p in results if (p.category or "").lower() == category.lower()]
    if has_email is not None:
        results = [p for p in results if bool(p.contact.email) is has_email]
    return results


@router.get("/", response_model=List[Prospect])
async def list_prospects(category: Optional[str] = None, has_email: Optional[bool] = None):
    prospects = _load_from_firestore() or load_cached_prospects()
    return _filter(prospects, category, has_email)
