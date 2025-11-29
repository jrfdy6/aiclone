"""
websocket Routes

API endpoints for websocket functionality.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_websocket():
    """List all websocket items."""
    return {
        "success": True,
        "message": "Websocket list endpoint",
        "data": []
    }
