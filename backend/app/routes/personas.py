"""
personas Routes

API endpoints for personas functionality.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_personas():
    """List all personas items."""
    return {
        "success": True,
        "message": "Personas list endpoint",
        "data": []
    }
