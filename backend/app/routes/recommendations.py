"""
recommendations Routes

API endpoints for recommendations functionality.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_recommendations():
    """List all recommendations items."""
    return {
        "success": True,
        "message": "Recommendations list endpoint",
        "data": []
    }
