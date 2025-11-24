"""
Activity Logging Routes
"""
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from app.models.activity import (
    ActivityCreate, ActivityEvent, ActivityListResponse,
    ActivityResponse, ActivityType
)
from app.services.activity_service import log_activity, get_activity, list_activities

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("", response_model=ActivityResponse)
async def create_activity(request: ActivityCreate) -> Dict[str, Any]:
    """Log a new activity event."""
    try:
        activity_id = log_activity(
            user_id=request.user_id,
            activity_type=request.type,
            title=request.title,
            message=request.message,
            metadata=request.metadata,
            link=request.link,
        )
        
        activity = get_activity(activity_id)
        if not activity:
            raise HTTPException(status_code=500, detail="Failed to retrieve created activity")
        
        return ActivityResponse(success=True, activity=activity)
    except Exception as e:
        logger.exception(f"Error creating activity: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to log activity: {str(e)}")


@router.get("", response_model=ActivityListResponse)
async def list_activity_events(
    user_id: str = Query(..., description="User identifier"),
    type: Optional[str] = Query(None, description="Filter by activity type"),
    limit: int = Query(100, ge=1, le=500),
) -> Dict[str, Any]:
    """List activity events for a user."""
    try:
        activity_type = ActivityType(type) if type else None
        activities = list_activities(
            user_id=user_id,
            activity_type=activity_type,
            limit=limit
        )
        return ActivityListResponse(
            success=True,
            activities=activities,
            total=len(activities)
        )
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid activity type: {type}")
    except Exception as e:
        logger.exception(f"Error listing activities: {e}")
        return ActivityListResponse(success=True, activities=[], total=0)


@router.get("/{activity_id}", response_model=ActivityResponse)
async def get_activity_event(activity_id: str) -> Dict[str, Any]:
    """Get an activity event by ID."""
    activity = get_activity(activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    return ActivityResponse(success=True, activity=activity)

