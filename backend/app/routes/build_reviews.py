from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException

from app.models.build_reviews import BuildReview, BuildReviewUpdate, BuildReviewUpsert
from app.services import build_review_service

router = APIRouter(tags=["Build Reviews"], prefix="/api/build-reviews")


@router.get("", response_model=List[BuildReview])
@router.get("/", response_model=List[BuildReview])
async def list_build_reviews(status: Optional[str] = None, limit: int = 100):
    return build_review_service.list_reviews(limit=limit, status=status)


@router.get("/{review_id}", response_model=BuildReview)
async def get_build_review(review_id: str):
    review = build_review_service.get_review(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Build review not found")
    return review


@router.post("", response_model=BuildReview)
@router.post("/", response_model=BuildReview)
async def upsert_build_review(payload: BuildReviewUpsert):
    return build_review_service.upsert_review(payload)


@router.patch("/{review_id}", response_model=BuildReview)
async def update_build_review(review_id: str, payload: BuildReviewUpdate):
    review = build_review_service.update_review(review_id, payload)
    if not review:
        raise HTTPException(status_code=404, detail="Build review not found")
    return review
