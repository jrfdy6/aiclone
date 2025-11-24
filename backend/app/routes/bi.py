"""
Business Intelligence Routes
"""
import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Query, Body
from app.services.bi_service import get_executive_dashboard, create_custom_dashboard

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/executive-dashboard", response_model=Dict[str, Any])
async def get_executive_dashboard_endpoint(
    user_id: str = Query(..., description="User identifier"),
    days: int = Query(30, ge=7, le=365, description="Number of days to analyze")
) -> Dict[str, Any]:
    """Get executive dashboard metrics"""
    try:
        dashboard = get_executive_dashboard(user_id, days)
        return {"success": True, "dashboard": dashboard}
    except Exception as e:
        logger.exception(f"Error getting executive dashboard: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard: {str(e)}")


@router.post("/custom-dashboard", response_model=Dict[str, Any])
async def create_custom_dashboard_endpoint(
    user_id: str = Query(..., description="User identifier"),
    config: Dict[str, Any] = Body(..., description="Dashboard configuration")
) -> Dict[str, Any]:
    """Create a custom dashboard"""
    try:
        dashboard_id = create_custom_dashboard(user_id, config)
        return {"success": True, "dashboard_id": dashboard_id}
    except Exception as e:
        logger.exception(f"Error creating custom dashboard: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create dashboard: {str(e)}")

