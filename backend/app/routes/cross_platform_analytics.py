"""
Cross-Platform Analytics Routes
"""
import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Query
from app.services.cross_platform_analytics_service import (
    get_unified_performance, get_content_performance_by_platform
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/unified", response_model=Dict[str, Any])
async def get_unified_performance_endpoint(
    user_id: str = Query(..., description="User identifier"),
    days: int = Query(30, ge=7, le=365, description="Number of days to analyze")
) -> Dict[str, Any]:
    """Get unified performance metrics across all platforms"""
    try:
        performance = get_unified_performance(user_id, days)
        return {"success": True, "performance": performance}
    except Exception as e:
        logger.exception(f"Error getting unified performance: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get performance: {str(e)}")


@router.get("/content/{content_id}", response_model=Dict[str, Any])
async def get_content_performance_by_platform_endpoint(
    content_id: str,
    user_id: str = Query(..., description="User identifier")
) -> Dict[str, Any]:
    """Get performance metrics for content by platform"""
    try:
        performance = get_content_performance_by_platform(user_id, content_id)
        if not performance:
            raise HTTPException(status_code=404, detail="Content not found")
        return {"success": True, "performance": performance}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting content performance: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get performance: {str(e)}")

