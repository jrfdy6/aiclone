"""
nlp Routes

API endpoints for nlp functionality.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_nlp():
    """List all nlp items."""
    return {
        "success": True,
        "message": "Nlp list endpoint",
        "data": []
    }
