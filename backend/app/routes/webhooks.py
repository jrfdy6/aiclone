"""
webhooks Routes

API endpoints for webhooks functionality.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_webhooks():
    """List all webhooks items."""
    return {
        "success": True,
        "message": "Webhooks list endpoint",
        "data": []
    }
