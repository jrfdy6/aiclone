"""
notifications Routes

API endpoints for notifications functionality.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_notifications():
    """List all notifications items."""
    return {
        "success": True,
        "message": "Notifications list endpoint",
        "data": []
    }
