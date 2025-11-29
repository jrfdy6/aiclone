"""
multi format content Routes

API endpoints for multi format content functionality.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_multi_format_content():
    """List all multi format content items."""
    return {
        "success": True,
        "message": "Multi Format Content list endpoint",
        "data": []
    }
