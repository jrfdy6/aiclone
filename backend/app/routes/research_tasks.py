"""
research tasks Routes

API endpoints for research tasks functionality.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_research_tasks():
    """List all research tasks items."""
    return {
        "success": True,
        "message": "Research Tasks list endpoint",
        "data": []
    }
