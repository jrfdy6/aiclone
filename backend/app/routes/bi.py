"""
bi Routes

API endpoints for bi functionality.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_bi():
    """List all bi items."""
    return {
        "success": True,
        "message": "Bi list endpoint",
        "data": []
    }
