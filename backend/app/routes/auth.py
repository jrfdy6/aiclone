"""
auth Routes

API endpoints for auth functionality.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_auth():
    """List all auth items."""
    return {
        "success": True,
        "message": "Auth list endpoint",
        "data": []
    }
