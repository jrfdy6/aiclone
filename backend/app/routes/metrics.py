"""
Metrics Routes - KPI tracking
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query

from app.services.firestore_client import db
from app.models.metrics import MetricsResponse, UpdateMetricsRequest, Metrics, TopPerformer

logger = logging.getLogger(__name__)
router = APIRouter()


def get_or_create_metrics(user_id: str, period_type: str = "weekly") -> Dict[str, Any]:
    """
    Get or create metrics document for current period.
    """
    now = datetime.now()
    
    if period_type == "weekly":
        # Get start of current week (Monday)
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        metric_id = f"week_{int(week_start.timestamp())}"
        month = None
    else:
        # Monthly
        month = now.strftime("%Y-%m")
        metric_id = f"month_{month}"
        week_start = None
    
    # Try to get existing metrics
    doc_ref = db.collection("users").document(user_id).collection("metrics").document(metric_id)
    doc = doc_ref.get()
    
    if doc.exists:
        return doc.to_dict()
    
    # Create new metrics document
    metrics_data = {
        "metric_id": metric_id,
        "user_id": user_id,
        "week_start": week_start.timestamp() if week_start else None,
        "month": month,
        "prospects_analyzed": 0,
        "emails_sent": 0,
        "meetings_booked": 0,
        "top_industries": [],
        "top_job_titles": [],
        "top_outreach_angles": [],
        "updated_at": time.time(),
    }
    
    doc_ref.set(metrics_data)
    return metrics_data


@router.get("/current")
async def get_current_metrics(
    user_id: str = Query(..., description="User identifier"),
    period: str = Query("weekly", description="weekly|monthly")
) -> Dict[str, Any]:
    """
    Get current period metrics.
    """
    try:
        metrics_data = get_or_create_metrics(user_id, period)
        
        metrics = Metrics(**metrics_data)
        
        # Convert Pydantic model to dict for FastAPI response
        response = MetricsResponse(
            success=True,
            metrics=metrics
        )
        return response.model_dump()
        
    except Exception as e:
        logger.exception(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")


@router.post("/update")
async def update_metrics(request: UpdateMetricsRequest) -> Dict[str, Any]:
    """
    Update metrics based on action.
    """
    try:
        metrics_data = get_or_create_metrics(request.user_id, "weekly")
        metric_id = metrics_data["metric_id"]
        
        # Update based on action
        updates = {
            "updated_at": time.time(),
        }
        
        if request.action == "prospects_analyzed":
            updates["prospects_analyzed"] = metrics_data.get("prospects_analyzed", 0) + 1
        elif request.action == "emails_sent":
            updates["emails_sent"] = metrics_data.get("emails_sent", 0) + 1
        elif request.action == "meetings_booked":
            updates["meetings_booked"] = metrics_data.get("meetings_booked", 0) + 1
        
        # If prospect_id provided, update top performers
        if request.prospect_id:
            try:
                # Get prospect data
                prospect_ref = db.collection("users").document(request.user_id).collection("prospects").document(request.prospect_id)
                prospect_doc = prospect_ref.get()
                
                if prospect_doc.exists:
                    prospect_data = prospect_doc.to_dict()
                    
                    # Update top industries
                    industry = prospect_data.get("company", "").split()[0] if prospect_data.get("company") else None
                    if industry:
                        top_industries = metrics_data.get("top_industries", [])
                        industry_found = False
                        for item in top_industries:
                            if item.get("value") == industry:
                                item["count"] = item.get("count", 0) + 1
                                if request.action == "meetings_booked":
                                    item["meetings"] = item.get("meetings", 0) + 1
                                industry_found = True
                                break
                        if not industry_found:
                            top_industries.append({
                                "value": industry,
                                "count": 1,
                                "meetings": 1 if request.action == "meetings_booked" else 0,
                            })
                        updates["top_industries"] = sorted(top_industries, key=lambda x: x.get("count", 0), reverse=True)[:10]
                    
                    # Update top job titles
                    job_title = prospect_data.get("job_title")
                    if job_title:
                        top_job_titles = metrics_data.get("top_job_titles", [])
                        title_found = False
                        for item in top_job_titles:
                            if item.get("value") == job_title:
                                item["count"] = item.get("count", 0) + 1
                                if request.action == "meetings_booked":
                                    item["meetings"] = item.get("meetings", 0) + 1
                                title_found = True
                                break
                        if not title_found:
                            top_job_titles.append({
                                "value": job_title,
                                "count": 1,
                                "meetings": 1 if request.action == "meetings_booked" else 0,
                            })
                        updates["top_job_titles"] = sorted(top_job_titles, key=lambda x: x.get("count", 0), reverse=True)[:10]
                    
                    # Update top outreach angles
                    outreach_angle = prospect_data.get("best_outreach_angle")
                    if outreach_angle:
                        top_angles = metrics_data.get("top_outreach_angles", [])
                        angle_found = False
                        for item in top_angles:
                            if item.get("value") == outreach_angle:
                                item["count"] = item.get("count", 0) + 1
                                if request.action == "meetings_booked":
                                    item["meetings"] = item.get("meetings", 0) + 1
                                angle_found = True
                                break
                        if not angle_found:
                            top_angles.append({
                                "value": outreach_angle,
                                "count": 1,
                                "meetings": 1 if request.action == "meetings_booked" else 0,
                            })
                        updates["top_outreach_angles"] = sorted(top_angles, key=lambda x: x.get("count", 0), reverse=True)[:10]
            except Exception as e:
                logger.warning(f"Error updating top performers: {e}")
        
        # Update metrics document
        doc_ref = db.collection("users").document(request.user_id).collection("metrics").document(metric_id)
        doc_ref.update(updates)
        
        return {
            "success": True,
            "metric_id": metric_id,
            "updated": updates
        }
        
    except Exception as e:
        logger.exception(f"Error updating metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update metrics: {str(e)}")


