"""
templates Routes

API endpoints for templates functionality.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_templates():
    """List all templates items."""
    return {
        "success": True,
        "message": "Templates list endpoint",
        "data": []
    }
