"""
vault Routes

API endpoints for vault functionality.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_vault():
    """List all vault items."""
    return {
        "success": True,
        "message": "Vault list endpoint",
        "data": []
    }
