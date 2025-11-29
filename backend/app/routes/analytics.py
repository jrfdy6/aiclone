"""
analytics Routes

API endpoints for analytics functionality.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_analytics():
    """List all analytics items."""
    return {
        "success": True,
        "message": "Analytics list endpoint",
        "data": []
    }
