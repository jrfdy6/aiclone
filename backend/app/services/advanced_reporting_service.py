"""
Advanced Reporting Service
Custom report builder, comparative analytics
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from app.services.firestore_client import db

logger = logging.getLogger(__name__)


def generate_comparative_report(
    user_id: str,
    metric: str,
    period1_start: str,
    period1_end: str,
    period2_start: str,
    period2_end: str
) -> Dict[str, Any]:
    """
    Generate comparative report between two periods.
    Returns period-over-period comparison.
    """
    try:
        # Parse dates
        p1_start = datetime.fromisoformat(period1_start)
        p1_end = datetime.fromisoformat(period1_end)
        p2_start = datetime.fromisoformat(period2_start)
        p2_end = datetime.fromisoformat(period2_end)
        
        # Get metrics for each period
        period1_metrics = _get_period_metrics(user_id, p1_start, p1_end, metric)
        period2_metrics = _get_period_metrics(user_id, p2_start, p2_end, metric)
        
        # Calculate changes
        change = {}
        if period1_metrics.get("total", 0) > 0:
            pct_change = ((period2_metrics.get("total", 0) - period1_metrics.get("total", 0)) / period1_metrics.get("total", 0)) * 100
            change = {
                "absolute": period2_metrics.get("total", 0) - period1_metrics.get("total", 0),
                "percentage": round(pct_change, 2),
                "direction": "up" if pct_change > 0 else "down" if pct_change < 0 else "stable"
            }
        
        return {
            "metric": metric,
            "period1": {
                "start": period1_start,
                "end": period1_end,
                "metrics": period1_metrics
            },
            "period2": {
                "start": period2_start,
                "end": period2_end,
                "metrics": period2_metrics
            },
            "change": change
        }
        
    except Exception as e:
        logger.error(f"Error generating comparative report: {e}")
        return {}


def _get_period_metrics(user_id: str, start_date: datetime, end_date: datetime, metric: str) -> Dict[str, Any]:
    """Get metrics for a specific period"""
    if metric == "prospects":
        return _get_prospect_metrics(user_id, start_date, end_date)
    elif metric == "content":
        return _get_content_metrics(user_id, start_date, end_date)
    elif metric == "engagement":
        return _get_engagement_metrics(user_id, start_date, end_date)
    else:
        return {"total": 0}


def _get_prospect_metrics(user_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
    """Get prospect metrics for period"""
    try:
        query = db.collection("users").document(user_id).collection("prospects")
        docs = query.stream()
        
        count = 0
        for doc in docs:
            data = doc.to_dict()
            if not data:
                continue
            created_at = data.get("created_at", "")
            if created_at:
                try:
                    created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    if start_date <= created <= end_date:
                        count += 1
                except:
                    pass
        
        return {"total": count, "type": "prospects"}
    except Exception as e:
        logger.error(f"Error getting prospect metrics: {e}")
        return {"total": 0}


def _get_content_metrics(user_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
    """Get content metrics for period"""
    try:
        query = db.collection("users").document(user_id).collection("content_drafts")
        query = query.where("status", "==", "published")
        docs = query.stream()
        
        count = 0
        total_views = 0
        total_engagements = 0
        
        for doc in docs:
            data = doc.to_dict()
            if not data:
                continue
            published_at = data.get("published_at") or data.get("created_at", "")
            if published_at:
                try:
                    published = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                    if start_date <= published <= end_date:
                        count += 1
                        total_views += data.get("views", 0)
                        total_engagements += data.get("engagements", 0)
                except:
                    pass
        
        avg_engagement_rate = (total_engagements / total_views * 100) if total_views > 0 else 0
        
        return {
            "total": count,
            "type": "content",
            "total_views": total_views,
            "total_engagements": total_engagements,
            "avg_engagement_rate": round(avg_engagement_rate, 2)
        }
    except Exception as e:
        logger.error(f"Error getting content metrics: {e}")
        return {"total": 0}


def _get_engagement_metrics(user_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
    """Get engagement metrics for period"""
    try:
        content_metrics = _get_content_metrics(user_id, start_date, end_date)
        return {
            "total_views": content_metrics.get("total_views", 0),
            "total_engagements": content_metrics.get("total_engagements", 0),
            "avg_engagement_rate": content_metrics.get("avg_engagement_rate", 0),
            "type": "engagement"
        }
    except Exception as e:
        logger.error(f"Error getting engagement metrics: {e}")
        return {"total": 0}


def create_custom_report(user_id: str, config: Dict[str, Any]) -> str:
    """Create a custom report configuration"""
    try:
        report_id = db.collection("users").document(user_id).collection("custom_reports").document().id
        
        report_data = {
            "id": report_id,
            "user_id": user_id,
            "name": config.get("name", "Custom Report"),
            "type": config.get("type", "comparative"),
            "config": config,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        db.collection("users").document(user_id).collection("custom_reports").document(report_id).set(report_data)
        logger.info(f"Created custom report: {report_id}")
        return report_id
    except Exception as e:
        logger.error(f"Error creating custom report: {e}")
        raise

