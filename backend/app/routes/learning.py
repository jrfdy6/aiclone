"""
Learning Routes - Learning loop for referral patterns
"""

import logging
import time
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query

from app.services.firestore_client import db
from app.models.learning import (
    UpdatePatternsRequest,
    UpdatePatternsResponse,
    GetPatternsRequest,
    GetPatternsResponse,
    LearningPattern,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def update_pattern(
    user_id: str,
    pattern_type: str,
    value: str,
    engagement_data: Dict[str, Any],
) -> LearningPattern:
    """
    Update or create a learning pattern.
    """
    # Create pattern ID
    pattern_id = f"{pattern_type}_{value.lower().replace(' ', '_')}"
    
    # Get existing pattern
    doc_ref = db.collection("users").document(user_id).collection("learning_patterns").document(pattern_id)
    doc = doc_ref.get()
    
    if doc.exists:
        pattern_data = doc.to_dict()
        engagement_count = pattern_data.get("engagement_count", 0) + 1
        
        # Calculate performance score based on engagement
        meetings = engagement_data.get("meeting_booked", 0)
        emails_sent = engagement_data.get("email_sent", 0)
        emails_responded = engagement_data.get("email_responded", 0)
        
        # Simple performance calculation
        if emails_sent > 0:
            response_rate = emails_responded / emails_sent
        else:
            response_rate = 0
        
        performance_score = int((response_rate * 50) + (meetings * 10))
        performance_score = min(100, max(0, performance_score))
        
        # Update pattern
        updates = {
            "performance_score": performance_score,
            "engagement_count": engagement_count,
            "updated_at": time.time(),
        }
        
        if meetings > 0:
            updates["meetings_booked"] = pattern_data.get("meetings_booked", 0) + meetings
        if emails_sent > 0:
            updates["emails_sent"] = pattern_data.get("emails_sent", 0) + emails_sent
        if emails_responded > 0:
            updates["emails_responded"] = pattern_data.get("emails_responded", 0) + emails_responded
        
        doc_ref.update(updates)
        pattern_data.update(updates)
        
    else:
        # Create new pattern
        pattern_data = {
            "pattern_id": pattern_id,
            "user_id": user_id,
            pattern_type: value,
            "performance_score": 50,  # Default
            "engagement_count": 1,
            "meetings_booked": engagement_data.get("meeting_booked", 0),
            "emails_sent": engagement_data.get("email_sent", 0),
            "emails_responded": engagement_data.get("email_responded", 0),
            "updated_at": time.time(),
        }
        
        doc_ref.set(pattern_data)
    
    return LearningPattern(**pattern_data)


@router.post("/update-patterns", response_model=UpdatePatternsResponse)
async def update_learning_patterns(request: UpdatePatternsRequest) -> Dict[str, Any]:
    """
    Update learning patterns based on engagement data.
    """
    try:
        # Get prospect data
        prospect_ref = db.collection("users").document(request.user_id).collection("prospects").document(request.prospect_id)
        prospect_doc = prospect_ref.get()
        
        if not prospect_doc.exists:
            raise HTTPException(status_code=404, detail="Prospect not found")
        
        prospect_data = prospect_doc.to_dict()
        updated_patterns = []
        
        # Update industry pattern
        industry = prospect_data.get("company", "").split()[0] if prospect_data.get("company") else None
        if industry:
            pattern = update_pattern(request.user_id, "industry", industry, request.engagement_data)
            updated_patterns.append(pattern)
        
        # Update job title pattern
        job_title = prospect_data.get("job_title")
        if job_title:
            pattern = update_pattern(request.user_id, "job_title", job_title, request.engagement_data)
            updated_patterns.append(pattern)
        
        # Update keyword patterns
        cached_insights = prospect_data.get("cached_insights", {})
        keywords = cached_insights.get("signal_keywords", [])
        for keyword in keywords[:3]:  # Top 3 keywords
            pattern = update_pattern(request.user_id, "keyword", keyword, request.engagement_data)
            updated_patterns.append(pattern)
        
        # Update outreach angle pattern
        outreach_angle = prospect_data.get("best_outreach_angle")
        if outreach_angle:
            pattern = update_pattern(request.user_id, "outreach_angle", outreach_angle, request.engagement_data)
            updated_patterns.append(pattern)
        
        return UpdatePatternsResponse(
            success=True,
            updated_patterns=updated_patterns
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error updating learning patterns: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update learning patterns: {str(e)}")


@router.get("/patterns", response_model=GetPatternsResponse)
async def get_learning_patterns(
    user_id: str = Query(..., description="User identifier"),
    pattern_type: Optional[str] = Query(None, description="industry|job_title|keyword|outreach_angle"),
    limit: int = Query(10, ge=1, le=50)
) -> Dict[str, Any]:
    """
    Get learning patterns, optionally filtered by type.
    """
    try:
        collection = db.collection("users").document(user_id).collection("learning_patterns")
        
        if pattern_type:
            # Filter by pattern type (stored as field name)
            query = collection.where(pattern_type, "!=", None).order_by("performance_score", direction="DESCENDING").limit(limit)
        else:
            # Get all patterns, ordered by performance
            query = collection.order_by("performance_score", direction="DESCENDING").limit(limit)
        
        docs = query.get()
        patterns = []
        
        for doc in docs:
            pattern_data = doc.to_dict()
            patterns.append(LearningPattern(**pattern_data))
        
        return GetPatternsResponse(
            success=True,
            patterns=patterns
        )
        
    except Exception as e:
        logger.exception(f"Error getting learning patterns: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get learning patterns: {str(e)}")



