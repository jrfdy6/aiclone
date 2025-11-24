"""
Predictive Insights Routes
"""
import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Query
from app.services.predictive_insights_service import (
    forecast_revenue, forecast_pipeline,
    detect_anomalies, forecast_content_performance
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/forecast/revenue", response_model=Dict[str, Any])
async def forecast_revenue_endpoint(
    user_id: str = Query(..., description="User identifier"),
    days_ahead: int = Query(30, ge=7, le=365, description="Days to forecast ahead")
) -> Dict[str, Any]:
    """Forecast revenue"""
    try:
        forecast = forecast_revenue(user_id, days_ahead)
        return {"success": True, "forecast": forecast}
    except Exception as e:
        logger.exception(f"Error forecasting revenue: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to forecast revenue: {str(e)}")


@router.get("/forecast/pipeline", response_model=Dict[str, Any])
async def forecast_pipeline_endpoint(
    user_id: str = Query(..., description="User identifier"),
    days_ahead: int = Query(30, ge=7, le=365)
) -> Dict[str, Any]:
    """Forecast pipeline growth"""
    try:
        forecast = forecast_pipeline(user_id, days_ahead)
        return {"success": True, "forecast": forecast}
    except Exception as e:
        logger.exception(f"Error forecasting pipeline: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to forecast pipeline: {str(e)}")


@router.get("/anomalies", response_model=Dict[str, Any])
async def detect_anomalies_endpoint(
    user_id: str = Query(..., description="User identifier"),
    metric_type: str = Query(..., description="Metric type to check"),
    days: int = Query(30, ge=7, le=365)
) -> Dict[str, Any]:
    """Detect anomalies in metrics"""
    try:
        anomalies = detect_anomalies(user_id, metric_type, days)
        return {"success": True, "anomalies": anomalies, "count": len(anomalies)}
    except Exception as e:
        logger.exception(f"Error detecting anomalies: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to detect anomalies: {str(e)}")


@router.post("/forecast/content", response_model=Dict[str, Any])
async def forecast_content_performance_endpoint(
    user_id: str = Query(..., description="User identifier"),
    content_preview: str = Query(..., description="Content preview text"),
    days_ahead: int = Query(7, ge=1, le=30)
) -> Dict[str, Any]:
    """Forecast content performance"""
    try:
        forecast = forecast_content_performance(user_id, content_preview, days_ahead)
        return {"success": True, "forecast": forecast}
    except Exception as e:
        logger.exception(f"Error forecasting content performance: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to forecast content: {str(e)}")

