"""
Manual Outreach Routes

API endpoints for manual outreach operations.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_outreach():
    """List all outreach messages."""
    return {
        "success": True,
        "message": "Outreach list endpoint",
        "outreach": []
    }


@router.post("/")
async def create_outreach():
    """Create a new outreach message."""
    return {
        "success": True,
        "message": "Create outreach endpoint"
    }
