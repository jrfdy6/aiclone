"""
cross platform analytics Routes

API endpoints for cross platform analytics functionality.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_cross_platform_analytics():
    """List all cross platform analytics items."""
    return {
        "success": True,
        "message": "Cross Platform Analytics list endpoint",
        "data": []
    }
