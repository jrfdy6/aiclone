"""
Notifications Routes - Alert and notification management
"""
import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.firestore_client import db

logger = logging.getLogger(__name__)
router = APIRouter()


class NotificationCreate(BaseModel):
    """Request to create a notification"""
    type: str = Field(..., description="Notification type")
    title: str = Field(..., description="Notification title")
    message: str = Field(..., description="Notification message")
    priority: str = Field("medium", description="Priority: high, medium, low")
    link: Optional[str] = None


class Notification(BaseModel):
    """Notification model"""
    id: str
    type: str
    title: str
    message: str
    timestamp: str
    read: bool
    link: Optional[str] = None
    priority: str


class NotificationListResponse(BaseModel):
    """Response for listing notifications"""
    success: bool
    notifications: List[Notification]
    unread_count: int
    total: int


@router.get("/", response_model=NotificationListResponse)
async def list_notifications(
    user_id: str = Query(..., description="User identifier"),
    unread_only: bool = Query(False, description="Only return unread notifications"),
    limit: int = Query(50, ge=1, le=200),
):
    """
    List notifications for a user.
    """
    try:
        # Start with base query
        query = db.collection("notifications").where("user_id", "==", user_id)
        
        if unread_only:
            query = query.where("read", "==", False)
        
        notifications = []
        unread_count = 0
        
        # Try different query strategies, starting with simplest
        try:
            # First, try without ordering (most reliable)
            docs = query.limit(limit).stream()
            
            for doc in docs:
                try:
                    data = doc.to_dict()
                    if not data:
                        continue
                        
                    notification_id = doc.id
                    
                    is_read = data.get("read", False)
                    if not is_read:
                        unread_count += 1
                    
                    # Get timestamp, default to current time if missing
                    timestamp = data.get("timestamp")
                    if not timestamp:
                        timestamp = datetime.now().isoformat()
                    
                    notification = Notification(
                        id=notification_id,
                        type=data.get("type", "info"),
                        title=data.get("title", ""),
                        message=data.get("message", ""),
                        timestamp=timestamp,
                        read=is_read,
                        link=data.get("link"),
                        priority=data.get("priority", "medium"),
                    )
                    notifications.append(notification)
                except Exception as doc_error:
                    logger.warning(f"Error processing notification document {doc.id}: {doc_error}")
                    continue
            
            # Sort by timestamp in Python (more reliable than Firestore ordering)
            try:
                notifications.sort(key=lambda x: x.timestamp, reverse=True)
            except Exception as sort_error:
                logger.warning(f"Error sorting notifications: {sort_error}")
                # If sorting fails, just return as-is
            
        except Exception as query_error:
            error_str = str(query_error)
            logger.error(f"Error querying notifications: {query_error}")
            
            # Check if this is an index error - if so, try simpler query
            if "requires an index" in error_str.lower() or "index" in error_str.lower():
                logger.info("Index required, trying simpler query without filters...")
                try:
                    # Try querying all notifications for this user without any additional filters
                    simple_query = db.collection("notifications").where("user_id", "==", user_id)
                    docs = simple_query.limit(limit).stream()
                    
                    for doc in docs:
                        try:
                            data = doc.to_dict()
                            if not data:
                                continue
                            
                            # Filter by read status in Python if needed
                            if unread_only and data.get("read", False):
                                continue
                            
                            notification_id = doc.id
                            is_read = data.get("read", False)
                            if not is_read:
                                unread_count += 1
                            
                            timestamp = data.get("timestamp") or datetime.now().isoformat()
                            
                            notification = Notification(
                                id=notification_id,
                                type=data.get("type", "info"),
                                title=data.get("title", ""),
                                message=data.get("message", ""),
                                timestamp=timestamp,
                                read=is_read,
                                link=data.get("link"),
                                priority=data.get("priority", "medium"),
                            )
                            notifications.append(notification)
                        except Exception as doc_error:
                            logger.warning(f"Error processing notification document {doc.id}: {doc_error}")
                            continue
                    
                    # Sort by timestamp
                    try:
                        notifications.sort(key=lambda x: x.timestamp, reverse=True)
                    except:
                        pass
                        
                except Exception as fallback_error:
                    logger.error(f"Fallback query also failed: {fallback_error}")
                    notifications = []
            else:
                # For other errors, just return empty list
                notifications = []
        
        # Return success response even if no notifications found
        return NotificationListResponse(
            success=True,
            notifications=notifications,
            unread_count=unread_count,
            total=len(notifications)
        )
    
    except Exception as e:
        logger.exception(f"Error listing notifications: {e}")
        # Return empty response instead of crashing
        return NotificationListResponse(
            success=True,
            notifications=[],
            unread_count=0,
            total=0
        )


@router.post("/", response_model=Notification)
async def create_notification(
    user_id: str = Query(..., description="User identifier"),
    notification_data: NotificationCreate = ...,
):
    """
    Create a new notification.
    """
    try:
        notification_ref = db.collection("notifications").document()
        notification_dict = {
            "user_id": user_id,
            "type": notification_data.type,
            "title": notification_data.title,
            "message": notification_data.message,
            "priority": notification_data.priority,
            "link": notification_data.link,
            "read": False,
            "timestamp": datetime.now().isoformat(),
            "created_at": time.time(),
        }
        notification_ref.set(notification_dict)
        
        return Notification(
            id=notification_ref.id,
            type=notification_data.type,
            title=notification_data.title,
            message=notification_data.message,
            timestamp=notification_dict["timestamp"],
            read=False,
            link=notification_data.link,
            priority=notification_data.priority,
        )
    
    except Exception as e:
        logger.exception(f"Error creating notification: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create notification: {str(e)}")


@router.put("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    user_id: str = Query(..., description="User identifier"),
):
    """
    Mark a notification as read.
    """
    try:
        notification_ref = db.collection("notifications").document(notification_id)
        notification_doc = notification_ref.get()
        
        if not notification_doc.exists:
            raise HTTPException(status_code=404, detail="Notification not found")
        
        notification_data = notification_doc.to_dict()
        if notification_data.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Notification does not belong to user")
        
        notification_ref.update({
            "read": True,
            "read_at": time.time(),
        })
        
        return {"success": True, "message": "Notification marked as read"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error marking notification as read: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to mark notification as read: {str(e)}")


@router.post("/mark-all-read")
async def mark_all_notifications_read(
    user_id: str = Query(..., description="User identifier"),
):
    """
    Mark all notifications for a user as read.
    """
    try:
        query = db.collection("notifications").where("user_id", "==", user_id).where("read", "==", False)
        docs = query.stream()
        
        batch = db.batch()
        count = 0
        
        for doc in docs:
            batch.update(doc.reference, {
                "read": True,
                "read_at": time.time(),
            })
            count += 1
        
        if count > 0:
            batch.commit()
        
        return {"success": True, "marked_read": count}
    
    except Exception as e:
        logger.exception(f"Error marking all notifications as read: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to mark all notifications as read: {str(e)}")


@router.get("/generate-insights")
async def generate_notification_insights(
    user_id: str = Query(..., description="User identifier"),
):
    """
    Generate intelligent notifications based on prospect data and patterns.
    This endpoint analyzes prospects and creates relevant notifications.
    """
    try:
        notifications_created = []
        
        # Check for high-fit prospects
        prospects_query = db.collection("prospects").where("user_id", "==", user_id).limit(100)
        prospects = prospects_query.stream()
        
        high_fit_prospects = []
        for prospect_doc in prospects:
            data = prospect_doc.to_dict()
            fit_score = data.get("fit_score") or (data.get("scores", {}) or {}).get("fit_score", 0)
            status = data.get("status", "new")
            
            if fit_score > 0.85 and status == "new":
                high_fit_prospects.append({
                    "id": prospect_doc.id,
                    "name": data.get("name", "Unknown"),
                    "company": data.get("company", ""),
                    "fit_score": fit_score,
                })
        
        # Create notification for high-fit prospects
        if high_fit_prospects:
            top_prospect = high_fit_prospects[0]
            notification_ref = db.collection("notifications").document()
            notification_ref.set({
                "user_id": user_id,
                "type": "high_fit",
                "title": "🚨 High-Fit Prospect Detected",
                "message": f"{top_prospect['name']} ({top_prospect.get('company', '')}) has a {int(top_prospect['fit_score'] * 100)}% fit score",
                "priority": "high",
                "link": "/prospects",
                "read": False,
                "timestamp": datetime.now().isoformat(),
                "created_at": time.time(),
            })
            notifications_created.append(notification_ref.id)
        
        # Check for overdue follow-ups
        today = datetime.now().date().isoformat()
        follow_ups_query = db.collection("follow_up_events").where("user_id", "==", user_id).where("status", "==", "pending")
        follow_ups = follow_ups_query.stream()
        
        overdue_count = 0
        for follow_up_doc in follow_ups:
            data = follow_up_doc.to_dict()
            scheduled_date = data.get("scheduled_date", "")
            if scheduled_date < today:
                overdue_count += 1
        
        if overdue_count > 0:
            notification_ref = db.collection("notifications").document()
            notification_ref.set({
                "user_id": user_id,
                "type": "follow_up_overdue",
                "title": "🔥 Follow-Up Overdue",
                "message": f"You have {overdue_count} overdue follow-up{'s' if overdue_count > 1 else ''}",
                "priority": "high",
                "link": "/calendar",
                "read": False,
                "timestamp": datetime.now().isoformat(),
                "created_at": time.time(),
            })
            notifications_created.append(notification_ref.id)
        
        return {
            "success": True,
            "notifications_created": len(notifications_created),
            "notification_ids": notifications_created,
        }
    
    except Exception as e:
        logger.exception(f"Error generating notification insights: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate notification insights: {str(e)}")

