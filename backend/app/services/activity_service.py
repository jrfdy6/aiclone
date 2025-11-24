"""
Activity Logging Service
"""
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from app.services.firestore_client import db
from app.models.activity import ActivityEvent, ActivityType

logger = logging.getLogger(__name__)


def log_activity(
    user_id: str,
    activity_type: ActivityType,
    title: str,
    message: str,
    metadata: Optional[Dict[str, Any]] = None,
    link: Optional[str] = None,
    broadcast: bool = True
) -> str:
    """
    Log an activity event.
    
    Returns the activity ID.
    """
    try:
        activity_ref = db.collection("activity_logs").document()
        activity_id = activity_ref.id
        
        activity_data = {
            "user_id": user_id,
            "type": activity_type.value,
            "title": title,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
            "link": link,
        }
        
        activity_ref.set(activity_data)
        logger.info(f"Logged activity {activity_id}: {title}")
        
        # Broadcast via WebSocket if enabled
        if broadcast:
            try:
                from app.services.websocket_manager import broadcast_activity
                import asyncio
                asyncio.create_task(broadcast_activity(
                    user_id=user_id,
                    activity_type=activity_type.value,
                    title=title,
                    message=message,
                    metadata=metadata
                ))
            except Exception as e:
                logger.warning(f"Failed to broadcast activity: {e}")
        
        return activity_id
        
    except Exception as e:
        logger.error(f"Error logging activity: {e}")
        raise


def get_activity(activity_id: str) -> Optional[ActivityEvent]:
    """Get an activity by ID."""
    try:
        activity_doc = db.collection("activity_logs").document(activity_id).get()
        
        if not activity_doc.exists:
            return None
        
        data = activity_doc.to_dict()
        return ActivityEvent(
            id=activity_id,
            user_id=data.get("user_id", ""),
            type=ActivityType(data.get("type", "info")),
            title=data.get("title", ""),
            message=data.get("message", ""),
            timestamp=data.get("timestamp", ""),
            metadata=data.get("metadata", {}),
            link=data.get("link"),
        )
    except Exception as e:
        logger.error(f"Error getting activity {activity_id}: {e}")
        return None


def list_activities(
    user_id: str,
    activity_type: Optional[ActivityType] = None,
    limit: int = 100
) -> List[ActivityEvent]:
    """List activity events for a user."""
    try:
        query = db.collection("activity_logs").where("user_id", "==", user_id)
        
        if activity_type:
            query = query.where("type", "==", activity_type.value)
        
        # Try to order by timestamp
        try:
            docs = query.order_by("timestamp", direction="DESCENDING").limit(limit).stream()
        except Exception:
            # Fallback if index doesn't exist
            docs = query.limit(limit).stream()
        
        activities = []
        for doc in docs:
            try:
                data = doc.to_dict()
                activities.append(ActivityEvent(
                    id=doc.id,
                    user_id=data.get("user_id", ""),
                    type=ActivityType(data.get("type", "info")),
                    title=data.get("title", ""),
                    message=data.get("message", ""),
                    timestamp=data.get("timestamp", ""),
                    metadata=data.get("metadata", {}),
                    link=data.get("link"),
                ))
            except Exception as e:
                logger.warning(f"Error processing activity document {doc.id}: {e}")
                continue
        
        # Sort in Python if order_by didn't work
        if activities:
            try:
                activities.sort(key=lambda x: x.timestamp, reverse=True)
            except:
                pass
        
        return activities
    except Exception as e:
        logger.error(f"Error listing activities: {e}")
        return []

