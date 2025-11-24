"""
Advanced Reporting Routes
"""
import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Query, Body
from app.services.advanced_reporting_service import generate_comparative_report, create_custom_report

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/comparative", response_model=Dict[str, Any])
async def generate_comparative_report_endpoint(
    user_id: str = Query(..., description="User identifier"),
    metric: str = Query(..., description="Metric to compare"),
    period1_start: str = Query(..., description="Period 1 start date (ISO format)"),
    period1_end: str = Query(..., description="Period 1 end date (ISO format)"),
    period2_start: str = Query(..., description="Period 2 start date (ISO format)"),
    period2_end: str = Query(..., description="Period 2 end date (ISO format)")
) -> Dict[str, Any]:
    """Generate comparative report between two periods"""
    try:
        report = generate_comparative_report(
            user_id, metric, period1_start, period1_end, period2_start, period2_end
        )
        return {"success": True, "report": report}
    except Exception as e:
        logger.exception(f"Error generating comparative report: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")


@router.post("/custom", response_model=Dict[str, Any])
async def create_custom_report_endpoint(
    user_id: str = Query(..., description="User identifier"),
    config: Dict[str, Any] = Body(..., description="Report configuration")
) -> Dict[str, Any]:
    """Create a custom report"""
    try:
        report_id = create_custom_report(user_id, config)
        return {"success": True, "report_id": report_id}
    except Exception as e:
        logger.exception(f"Error creating custom report: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create report: {str(e)}")

