"""
Analytics Service
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from app.services.firestore_client import db
from app.models.analytics import AnalyticsMetric, MetricDataPoint, MetricType, TimeRange, AnalyticsSummary

logger = logging.getLogger(__name__)


def get_prospects_analyzed(user_id: str, days: int = 30) -> List[MetricDataPoint]:
    """Get prospects analyzed over time"""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Query prospects collection
        query = db.collection("users").document(user_id).collection("prospects")
        query = query.where("created_at", ">=", start_date.isoformat())
        query = query.where("created_at", "<=", end_date.isoformat())
        
        docs = query.stream()
        
        # Group by date
        daily_counts: Dict[str, int] = {}
        for doc in docs:
            data = doc.to_dict()
            if not data:
                continue
            created_at = data.get("created_at", "")
            if created_at:
                date_key = created_at.split("T")[0]  # Extract date
                daily_counts[date_key] = daily_counts.get(date_key, 0) + 1
        
        # Convert to data points
        data_points = [
            MetricDataPoint(date=date, value=float(count))
            for date, count in sorted(daily_counts.items())
        ]
        
        return data_points
    except Exception as e:
        logger.error(f"Error getting prospects analyzed: {e}")
        return []


def get_research_tasks_completed(user_id: str, days: int = 30) -> List[MetricDataPoint]:
    """Get research tasks completed over time"""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        query = db.collection("users").document(user_id).collection("research_tasks")
        query = query.where("status", "==", "done")
        query = query.where("completed_at", ">=", start_date.isoformat())
        
        docs = query.stream()
        
        daily_counts: Dict[str, int] = {}
        for doc in docs:
            data = doc.to_dict()
            if not data:
                continue
            completed_at = data.get("completed_at", "")
            if completed_at:
                date_key = completed_at.split("T")[0]
                daily_counts[date_key] = daily_counts.get(date_key, 0) + 1
        
        data_points = [
            MetricDataPoint(date=date, value=float(count))
            for date, count in sorted(daily_counts.items())
        ]
        
        return data_points
    except Exception as e:
        logger.error(f"Error getting research tasks completed: {e}")
        return []


def get_engagement_metrics(user_id: str, days: int = 30) -> Dict[str, Any]:
    """Get engagement metrics (content views, clicks, etc.)"""
    try:
        # This would query content_drafts and linkedin_metrics collections
        # For now, return mock data structure
        return {
            "total_views": 0,
            "total_engagements": 0,
            "engagement_rate": 0.0,
            "top_content": []
        }
    except Exception as e:
        logger.error(f"Error getting engagement metrics: {e}")
        return {}


def calculate_trend(data_points: List[MetricDataPoint]) -> str:
    """Calculate trend direction from data points"""
    if len(data_points) < 2:
        return "stable"
    
    first_half = data_points[:len(data_points)//2]
    second_half = data_points[len(data_points)//2:]
    
    first_avg = sum(p.value for p in first_half) / len(first_half) if first_half else 0
    second_avg = sum(p.value for p in second_half) / len(second_half) if second_half else 0
    
    if second_avg > first_avg * 1.1:
        return "up"
    elif second_avg < first_avg * 0.9:
        return "down"
    return "stable"


def get_analytics_summary(user_id: str, time_range: TimeRange = TimeRange.MONTH) -> AnalyticsSummary:
    """Get comprehensive analytics summary"""
    days_map = {
        TimeRange.DAY: 1,
        TimeRange.WEEK: 7,
        TimeRange.MONTH: 30,
        TimeRange.QUARTER: 90,
        TimeRange.YEAR: 365
    }
    days = days_map.get(time_range, 30)
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Get metrics
    prospects_data = get_prospects_analyzed(user_id, days)
    research_data = get_research_tasks_completed(user_id, days)
    
    # Build metrics list
    metrics = []
    
    if prospects_data:
        total = sum(p.value for p in prospects_data)
        avg = total / len(prospects_data) if prospects_data else 0
        metrics.append(AnalyticsMetric(
            metric_type=MetricType.PROSPECTS_ANALYZED,
            time_range=time_range,
            data_points=prospects_data,
            total=total,
            average=avg,
            trend=calculate_trend(prospects_data)
        ))
    
    if research_data:
        total = sum(p.value for p in research_data)
        avg = total / len(research_data) if research_data else 0
        metrics.append(AnalyticsMetric(
            metric_type=MetricType.RESEARCH_TASKS_COMPLETED,
            time_range=time_range,
            data_points=research_data,
            total=total,
            average=avg,
            trend=calculate_trend(research_data)
        ))
    
    return AnalyticsSummary(
        user_id=user_id,
        period_start=start_date.isoformat(),
        period_end=end_date.isoformat(),
        metrics=metrics,
        top_performers={}
    )

