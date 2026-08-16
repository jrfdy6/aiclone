from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models import SocialFeedbackCreate
from app.services import social_feedback_service

router = APIRouter(tags=["SocialFeedback"], prefix="/api/workspace")


@router.post("/feedback")
async def create_social_feedback(payload: SocialFeedbackCreate):
    try:
        path = social_feedback_service.append_feedback(payload.dict())
        return {"path": path.relative_to(path.parents[1]).as_posix(), "status": "recorded"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
