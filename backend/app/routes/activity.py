"""
activity Routes

API endpoints for activity functionality.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_activity():
    """List all activity items."""
    return {
        "success": True,
        "message": "Activity list endpoint",
        "data": []
    }
