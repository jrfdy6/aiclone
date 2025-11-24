"""
Cross-Platform Analytics Service
Unified performance tracking across platforms
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from app.services.firestore_client import db

logger = logging.getLogger(__name__)


def get_unified_performance(user_id: str, days: int = 30) -> Dict[str, Any]:
    """
    Get unified performance metrics across all platforms.
    Aggregates LinkedIn, Twitter, email, etc.
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Get all published content
        query = db.collection("users").document(user_id).collection("content_library")
        query = query.where("status", "==", "published")
        
        platforms: Dict[str, Dict[str, Any]] = {}
        total_metrics = {
            "total_views": 0,
            "total_engagements": 0,
            "total_clicks": 0,
            "total_shares": 0,
            "posts_count": 0
        }
        
        for doc in query.stream():
            data = doc.to_dict()
            if not data:
                continue
            
            published_platforms = data.get("published_platforms", [])
            published_at = data.get("published_at") or data.get("created_at", "")
            
            # Filter by date
            if published_at:
                try:
                    pub_date = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                    if pub_date < start_date:
                        continue
                except:
                    pass
            
            # Aggregate by platform
            for platform in published_platforms:
                if platform not in platforms:
                    platforms[platform] = {
                        "posts": 0,
                        "views": 0,
                        "engagements": 0,
                        "clicks": 0,
                        "shares": 0
                    }
                
                platforms[platform]["posts"] += 1
                
                # Get metrics from metadata or linked metrics
                views = data.get("metadata", {}).get("views", 0)
                engagements = data.get("metadata", {}).get("engagements", 0)
                clicks = data.get("metadata", {}).get("clicks", 0)
                shares = data.get("metadata", {}).get("shares", 0)
                
                platforms[platform]["views"] += views
                platforms[platform]["engagements"] += engagements
                platforms[platform]["clicks"] += clicks
                platforms[platform]["shares"] += shares
                
                total_metrics["total_views"] += views
                total_metrics["total_engagements"] += engagements
                total_metrics["total_clicks"] += clicks
                total_metrics["total_shares"] += shares
                total_metrics["posts_count"] += 1
        
        # Calculate engagement rates per platform
        platform_performance = {}
        for platform, metrics in platforms.items():
            engagement_rate = (metrics["engagements"] / metrics["views"] * 100) if metrics["views"] > 0 else 0
            platform_performance[platform] = {
                **metrics,
                "engagement_rate": round(engagement_rate, 2),
                "avg_views_per_post": metrics["views"] / max(1, metrics["posts"])
            }
        
        # Overall engagement rate
        overall_engagement_rate = (total_metrics["total_engagements"] / total_metrics["total_views"] * 100) if total_metrics["total_views"] > 0 else 0
        
        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": days
            },
            "platforms": platform_performance,
            "total": {
                **total_metrics,
                "overall_engagement_rate": round(overall_engagement_rate, 2)
            },
            "top_platform": max(platform_performance.items(), key=lambda x: x[1]["engagement_rate"])[0] if platform_performance else None
        }
        
    except Exception as e:
        logger.error(f"Error getting unified performance: {e}")
        return {}


def get_content_performance_by_platform(user_id: str, content_id: str) -> Dict[str, Any]:
    """Get performance metrics for a specific content item by platform"""
    try:
        content = db.collection("users").document(user_id).collection("content_library").document(content_id).get()
        if not content.exists:
            return {}
        
        data = content.to_dict()
        published_platforms = data.get("published_platforms", [])
        
        performance = {}
        for platform in published_platforms:
            # Get metrics for this platform (would need platform-specific metric storage)
            performance[platform] = {
                "views": data.get("metadata", {}).get(f"{platform}_views", 0),
                "engagements": data.get("metadata", {}).get(f"{platform}_engagements", 0),
                "clicks": data.get("metadata", {}).get(f"{platform}_clicks", 0),
            }
        
        return {
            "content_id": content_id,
            "title": data.get("title", ""),
            "platforms": performance
        }
        
    except Exception as e:
        logger.error(f"Error getting content performance by platform: {e}")
        return {}

