from __future__ import annotations

import os
import re
import uuid

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.models import Prospect
from app.services.firestore_prospect_authority_service import (
    FirestoreProspectAuthorityError,
    write_canonical_prospect,
)

router = APIRouter(tags=["Prospects"])

_SAFE_FIRESTORE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{0,127}$")


def _owner_user_id(requested: str) -> str:
    configured = str(os.getenv("DEFAULT_USER_ID") or "default-user").strip()
    if not _SAFE_FIRESTORE_ID.fullmatch(configured):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "state": "degraded",
                "reason_codes": ["owner_authority_misconfigured"],
                "message": "Prospect owner authority is not configured safely.",
            },
        )
    if requested != configured:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The requested user does not match the configured owner authority.",
        )
    return configured


@router.post("/", response_model=Prospect)
async def create_prospect(
    prospect: Prospect,
    response: Response,
    user_id: str = Query(default_factory=lambda: os.getenv("DEFAULT_USER_ID", "default-user")),
):
    user_id = _owner_user_id(user_id)
    if not prospect.id:
        prospect.id = str(uuid.uuid4())

    try:
        write_canonical_prospect(user_id, prospect.id, prospect.model_dump())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid user_id",
        ) from exc
    except FirestoreProspectAuthorityError:
        # Local prospect JSON remains a read-only compatibility source. A failed
        # canonical mutation must never create an unsynchronized second writer.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "state": "degraded",
                "reason_codes": ["canonical_prospect_write_unavailable"],
                "message": "The canonical prospect store is temporarily unavailable.",
            },
            headers={
                "X-AI-Clone-Firestore-State": "degraded",
                "X-AI-Clone-Data-Authority": f"firestore:users/{user_id}/prospects",
                "X-AI-Clone-Degraded-Reasons": "canonical_prospect_write_unavailable",
                "Cache-Control": "no-store, max-age=0",
            },
        )

    response.headers["X-AI-Clone-Firestore-State"] = "ready"
    response.headers["X-AI-Clone-Data-Authority"] = f"firestore:users/{user_id}/prospects"
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return prospect
