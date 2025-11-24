"""
Prospects Routes - Prospect management endpoints
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

router = APIRouter()


@router.get("/")
async def list_prospects(
    user_id: str = Query(..., description="User identifier"),
    limit: Optional[int] = Query(10, ge=1, le=100)
):
    """
    List prospects for a user.
    This is a minimal stub endpoint to prevent import errors.
    """
    return {
        "success": True,
        "message": "Prospects endpoint - implementation pending",
        "user_id": user_id,
        "limit": limit
    }
