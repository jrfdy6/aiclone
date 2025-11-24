"""
Calendar Routes - Follow-up scheduling and management
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


class FollowUpEventCreate(BaseModel):
    """Request to create a follow-up event"""
    prospect_id: str = Field(..., description="Prospect ID")
    scheduled_date: str = Field(..., description="ISO date string (YYYY-MM-DD)")
    type: str = Field(..., description="Event type: initial, follow_up, check_in, nurture")
    notes: Optional[str] = None


class FollowUpEventUpdate(BaseModel):
    """Request to update a follow-up event"""
    scheduled_date: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class FollowUpEvent(BaseModel):
    """Follow-up event model"""
    id: str
    prospect_id: str
    prospect_name: Optional[str] = None
    company: Optional[str] = None
    scheduled_date: str
    type: str
    status: str
    notes: Optional[str] = None
    last_contact: Optional[str] = None
    suggested_message: Optional[str] = None
    created_at: float
    updated_at: float


class FollowUpEventListResponse(BaseModel):
    """Response for listing follow-up events"""
    success: bool
    events: List[FollowUpEvent]
    total: int


@router.get("/", response_model=FollowUpEventListResponse)
async def list_follow_ups(
    user_id: str = Query(..., description="User identifier"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    status: Optional[str] = Query(None, description="Filter by status: pending, completed, overdue"),
    limit: int = Query(500, ge=1, le=1000),
):
    """
    List follow-up events for a user with optional filtering.
    """
    try:
        # Build query
        query = db.collection("follow_up_events").where("user_id", "==", user_id)
        
        if status:
            query = query.where("status", "==", status)
        
        # Execute query
        docs = query.limit(limit).stream()
        
        events = []
        now = datetime.now()
        today = now.date().isoformat()
        
        for doc in docs:
            data = doc.to_dict()
            event_id = doc.id
            
            # Determine if overdue
            scheduled_date_str = data.get("scheduled_date", "")
            event_status = data.get("status", "pending")
            
            if event_status == "pending" and scheduled_date_str:
                try:
                    scheduled_date = datetime.fromisoformat(scheduled_date_str.split('T')[0]).date()
                    if scheduled_date < now.date():
                        event_status = "overdue"
                except:
                    pass
            
            # Fetch prospect details
            prospect_name = None
            company = None
            prospect_id = data.get("prospect_id", "")
            
            if prospect_id:
                try:
                    prospect_doc = db.collection("prospects").document(prospect_id).get()
                    if prospect_doc.exists:
                        prospect_data = prospect_doc.to_dict()
                        prospect_name = prospect_data.get("name")
                        company = prospect_data.get("company")
                except Exception as e:
                    logger.warning(f"Error fetching prospect {prospect_id}: {e}")
            
            # Filter by date range if provided
            if start_date or end_date:
                if scheduled_date_str:
                    try:
                        event_date = scheduled_date_str.split('T')[0]
                        if start_date and event_date < start_date:
                            continue
                        if end_date and event_date > end_date:
                            continue
                    except:
                        pass
            
            event = FollowUpEvent(
                id=event_id,
                prospect_id=prospect_id,
                prospect_name=prospect_name,
                company=company,
                scheduled_date=scheduled_date_str,
                type=data.get("type", "follow_up"),
                status=event_status,
                notes=data.get("notes"),
                last_contact=data.get("last_contact"),
                suggested_message=data.get("suggested_message"),
                created_at=data.get("created_at", time.time()),
                updated_at=data.get("updated_at", time.time()),
            )
            events.append(event)
        
        # Sort by scheduled_date
        events.sort(key=lambda x: x.scheduled_date or "")
        
        return FollowUpEventListResponse(
            success=True,
            events=events,
            total=len(events)
        )
    
    except Exception as e:
        logger.exception(f"Error listing follow-up events: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list follow-up events: {str(e)}")


@router.post("/", response_model=FollowUpEvent)
async def create_follow_up(
    user_id: str = Query(..., description="User identifier"),
    event_data: FollowUpEventCreate = ...,
):
    """
    Create a new follow-up event.
    """
    try:
        # Verify prospect exists and belongs to user
        prospect_doc = db.collection("prospects").document(event_data.prospect_id).get()
        if not prospect_doc.exists:
            raise HTTPException(status_code=404, detail="Prospect not found")
        
        prospect_data = prospect_doc.to_dict()
        if prospect_data.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Prospect does not belong to user")
        
        # Create event
        event_ref = db.collection("follow_up_events").document()
        event_data_dict = {
            "user_id": user_id,
            "prospect_id": event_data.prospect_id,
            "scheduled_date": event_data.scheduled_date,
            "type": event_data.type,
            "status": "pending",
            "notes": event_data.notes,
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        event_ref.set(event_data_dict)
        
        # Fetch prospect name for response
        prospect_name = prospect_data.get("name")
        company = prospect_data.get("company")
        
        return FollowUpEvent(
            id=event_ref.id,
            prospect_id=event_data.prospect_id,
            prospect_name=prospect_name,
            company=company,
            scheduled_date=event_data.scheduled_date,
            type=event_data.type,
            status="pending",
            notes=event_data.notes,
            created_at=event_data_dict["created_at"],
            updated_at=event_data_dict["updated_at"],
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error creating follow-up event: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create follow-up event: {str(e)}")


@router.put("/{event_id}", response_model=FollowUpEvent)
async def update_follow_up(
    event_id: str,
    user_id: str = Query(..., description="User identifier"),
    update_data: FollowUpEventUpdate = ...,
):
    """
    Update a follow-up event.
    """
    try:
        event_ref = db.collection("follow_up_events").document(event_id)
        event_doc = event_ref.get()
        
        if not event_doc.exists:
            raise HTTPException(status_code=404, detail="Follow-up event not found")
        
        event_data = event_doc.to_dict()
        if event_data.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Event does not belong to user")
        
        # Build update dict
        updates = {"updated_at": time.time()}
        if update_data.scheduled_date is not None:
            updates["scheduled_date"] = update_data.scheduled_date
        if update_data.type is not None:
            updates["type"] = update_data.type
        if update_data.status is not None:
            updates["status"] = update_data.status
        if update_data.notes is not None:
            updates["notes"] = update_data.notes
        
        event_ref.update(updates)
        
        # Fetch updated data
        updated_doc = event_ref.get()
        updated_data = updated_doc.to_dict()
        
        # Fetch prospect details
        prospect_name = None
        company = None
        prospect_id = updated_data.get("prospect_id", "")
        if prospect_id:
            try:
                prospect_doc = db.collection("prospects").document(prospect_id).get()
                if prospect_doc.exists:
                    prospect_data = prospect_doc.to_dict()
                    prospect_name = prospect_data.get("name")
                    company = prospect_data.get("company")
            except:
                pass
        
        return FollowUpEvent(
            id=event_id,
            prospect_id=prospect_id,
            prospect_name=prospect_name,
            company=company,
            scheduled_date=updated_data.get("scheduled_date", ""),
            type=updated_data.get("type", "follow_up"),
            status=updated_data.get("status", "pending"),
            notes=updated_data.get("notes"),
            last_contact=updated_data.get("last_contact"),
            suggested_message=updated_data.get("suggested_message"),
            created_at=updated_data.get("created_at", time.time()),
            updated_at=updated_data.get("updated_at", time.time()),
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error updating follow-up event: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update follow-up event: {str(e)}")


@router.delete("/{event_id}")
async def delete_follow_up(
    event_id: str,
    user_id: str = Query(..., description="User identifier"),
):
    """
    Delete a follow-up event.
    """
    try:
        event_ref = db.collection("follow_up_events").document(event_id)
        event_doc = event_ref.get()
        
        if not event_doc.exists:
            raise HTTPException(status_code=404, detail="Follow-up event not found")
        
        event_data = event_doc.to_dict()
        if event_data.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Event does not belong to user")
        
        event_ref.delete()
        
        return {"success": True, "message": "Follow-up event deleted"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error deleting follow-up event: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete follow-up event: {str(e)}")

