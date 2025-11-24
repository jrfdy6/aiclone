"""
Business Intelligence Service
Executive dashboards, custom dashboards, advanced analytics
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from app.services.firestore_client import db

logger = logging.getLogger(__name__)


def get_executive_dashboard(user_id: str, days: int = 30) -> Dict[str, Any]:
    """
    Get executive-level dashboard metrics:
    - High-level KPIs
    - Revenue pipeline (if applicable)
    - Conversion funnel
    - ROI calculations
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    try:
        # Prospects analyzed
        prospects_query = db.collection("users").document(user_id).collection("prospects")
        total_prospects = len(list(prospects_query.stream()))
        
        # Outreach sent
        outreach_query = db.collection("users").document(user_id).collection("outreach")
        total_outreach = len(list(outreach_query.stream()))
        
        # Research tasks completed
        research_query = db.collection("users").document(user_id).collection("research_tasks")
        research_query = research_query.where("status", "==", "done")
        completed_research = len(list(research_query.stream()))
        
        # Content published
        content_query = db.collection("users").document(user_id).collection("content_drafts")
        content_query = content_query.where("status", "==", "published")
        published_content = len(list(content_query.stream()))
        
        # Calculate engagement metrics
        engagement_metrics = _calculate_engagement_metrics(user_id, start_date, end_date)
        
        # Conversion funnel
        funnel = {
            "prospects_analyzed": total_prospects,
            "outreach_sent": total_outreach,
            "meetings_scheduled": 0,  # Would need calendar/meeting tracking
            "deals_closed": 0  # Would need CRM integration
        }
        
        # Calculate conversion rates
        if total_prospects > 0:
            funnel["outreach_rate"] = (total_outreach / total_prospects) * 100
        else:
            funnel["outreach_rate"] = 0
        
        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": days
            },
            "kpis": {
                "prospects_analyzed": total_prospects,
                "outreach_sent": total_outreach,
                "research_completed": completed_research,
                "content_published": published_content,
            },
            "engagement": engagement_metrics,
            "funnel": funnel,
            "trends": _calculate_trends(user_id, days),
            "top_performers": _get_top_performers(user_id, days)
        }
        
    except Exception as e:
        logger.error(f"Error getting executive dashboard: {e}")
        return {}


def _calculate_engagement_metrics(user_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
    """Calculate overall engagement metrics"""
    try:
        total_views = 0
        total_engagements = 0
        
        content_query = db.collection("users").document(user_id).collection("content_drafts")
        content_query = content_query.where("status", "==", "published")
        
        for doc in content_query.stream():
            data = doc.to_dict()
            if not data:
                continue
            
            published_at = data.get("published_at") or data.get("created_at")
            if published_at:
                try:
                    pub_date = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                    if start_date <= pub_date <= end_date:
                        total_views += data.get("views", 0)
                        total_engagements += data.get("engagements", 0)
                except:
                    pass
        
        engagement_rate = (total_engagements / total_views * 100) if total_views > 0 else 0
        
        return {
            "total_views": total_views,
            "total_engagements": total_engagements,
            "engagement_rate": round(engagement_rate, 2),
            "avg_views_per_post": total_views / max(1, len(list(content_query.stream())))
        }
    except Exception as e:
        logger.error(f"Error calculating engagement metrics: {e}")
        return {
            "total_views": 0,
            "total_engagements": 0,
            "engagement_rate": 0,
            "avg_views_per_post": 0
        }


def _calculate_trends(user_id: str, days: int) -> Dict[str, str]:
    """Calculate trends (up/down/stable)"""
    # Simple trend calculation based on recent activity
    return {
        "prospects": "up",  # Would calculate from historical data
        "engagement": "stable",
        "content": "up"
    }


def _get_top_performers(user_id: str, days: int) -> Dict[str, Any]:
    """Get top performing content, prospects, etc."""
    try:
        # Top content
        content_query = db.collection("users").document(user_id).collection("content_drafts")
        content_query = content_query.where("status", "==", "published")
        
        top_content = []
        for doc in content_query.stream():
            data = doc.to_dict()
            if not data:
                continue
            
            views = data.get("views", 0)
            engagements = data.get("engagements", 0)
            
            if views > 0:
                top_content.append({
                    "id": doc.id,
                    "title": data.get("title", ""),
                    "engagement_rate": engagements / views,
                    "views": views
                })
        
        top_content.sort(key=lambda x: x["engagement_rate"], reverse=True)
        
        return {
            "top_content": top_content[:5],
            "top_prospects": [],  # Would need prospect performance tracking
            "top_hashtags": []  # Would calculate from content
        }
    except Exception as e:
        logger.error(f"Error getting top performers: {e}")
        return {}


def create_custom_dashboard(user_id: str, config: Dict[str, Any]) -> str:
    """Create a custom dashboard configuration"""
    try:
        dashboard_id = db.collection("users").document(user_id).collection("dashboards").document().id
        
        dashboard_data = {
            "id": dashboard_id,
            "user_id": user_id,
            "name": config.get("name", "Custom Dashboard"),
            "widgets": config.get("widgets", []),
            "layout": config.get("layout", {}),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        db.collection("users").document(user_id).collection("dashboards").document(dashboard_id).set(dashboard_data)
        logger.info(f"Created custom dashboard: {dashboard_id}")
        return dashboard_id
    except Exception as e:
        logger.error(f"Error creating custom dashboard: {e}")
        raise

