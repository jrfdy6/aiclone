"""
automations Routes

API endpoints for automations functionality.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_automations():
    """List all automations items."""
    return {
        "success": True,
        "message": "Automations list endpoint",
        "data": []
    }
