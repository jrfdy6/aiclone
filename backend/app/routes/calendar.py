"""
calendar Routes

API endpoints for calendar functionality.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_calendar():
    """List all calendar items."""
    return {
        "success": True,
        "message": "Calendar list endpoint",
        "data": []
    }
