"""
Prospects Routes - Prospect management endpoints
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from app.services.firestore_client import db

router = APIRouter()


class ProspectResponse(BaseModel):
    """Prospect data model"""
    id: str
    name: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    email: Optional[str] = None
    fit_score: Optional[float] = None
    status: Optional[str] = None
    tags: Optional[List[str]] = None
    last_action: Optional[str] = None
    summary: Optional[str] = None
    pain_points: Optional[List[str]] = None
    analysis: Optional[Dict[str, Any]] = None
    created_at: Optional[float] = None
    updated_at: Optional[float] = None


class ProspectListResponse(BaseModel):
    """Response for listing prospects"""
    success: bool
    prospects: List[ProspectResponse]
    total: int


@router.get("/", response_model=ProspectListResponse)
async def list_prospects(
    user_id: str = Query(..., description="User identifier"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: Optional[int] = Query(100, ge=1, le=500, description="Maximum number of prospects to return"),
    sort_by: Optional[str] = Query("updated_at", description="Field to sort by"),
    sort_order: Optional[str] = Query("desc", description="Sort order: asc or desc")
):
    """
    List prospects for a user with optional filtering and sorting.
    """
    try:
        # Build query
        query = db.collection("prospects").where("user_id", "==", user_id)
        
        # Apply status filter if provided
        if status and status != "all":
            query = query.where("status", "==", status)
        
        # Execute query
        docs = query.limit(limit).stream()
        
        prospects = []
        for doc in docs:
            data = doc.to_dict()
            prospect_id = doc.id
            
            # Extract fit_score from various possible locations
            fit_score = None
            if "fit_score" in data:
                fit_score = data["fit_score"]
            elif "scores" in data and isinstance(data["scores"], dict):
                fit_score = data["scores"].get("fit_score")
            elif "analysis" in data and isinstance(data["analysis"], dict):
                confidence = data["analysis"].get("confidence_score")
                if confidence:
                    fit_score = confidence
            
            # Extract summary
            summary = None
            if "summary" in data:
                summary = data["summary"]
            elif "analysis" in data and isinstance(data["analysis"], dict):
                summary = data["analysis"].get("summary")
            
            # Extract pain points
            pain_points = None
            if "pain_points" in data:
                pain_points = data["pain_points"]
            elif isinstance(pain_points, str):
                pain_points = [pain_points]
            
            # Determine status
            prospect_status = data.get("status", "new")
            if "review_status" in data:
                prospect_status = data["review_status"]
            
            # Build last_action string
            last_action = None
            if "last_action" in data:
                last_action = data["last_action"]
            elif "updated_at" in data:
                import datetime
                updated = data["updated_at"]
                if isinstance(updated, (int, float)):
                    dt = datetime.datetime.fromtimestamp(updated)
                    days_ago = (datetime.datetime.now() - dt).days
                    last_action = f"Updated {days_ago} days ago"
            
            prospect = ProspectResponse(
                id=prospect_id,
                name=data.get("name"),
                company=data.get("company"),
                job_title=data.get("job_title"),
                email=data.get("email"),
                fit_score=fit_score,
                status=prospect_status,
                tags=data.get("tags", []),
                last_action=last_action,
                summary=summary,
                pain_points=pain_points if isinstance(pain_points, list) else None,
                analysis=data.get("analysis"),
                created_at=data.get("created_at"),
                updated_at=data.get("updated_at"),
            )
            prospects.append(prospect)
        
        # Sort results
        if sort_by:
            reverse = sort_order == "desc"
            try:
                prospects.sort(key=lambda x: getattr(x, sort_by) or 0, reverse=reverse)
            except:
                # If sorting fails, fallback to updated_at
                prospects.sort(key=lambda x: x.updated_at or 0, reverse=reverse)
        
        return ProspectListResponse(
            success=True,
            prospects=prospects,
            total=len(prospects)
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list prospects: {str(e)}")


@router.get("/{prospect_id}", response_model=ProspectResponse)
async def get_prospect(
    prospect_id: str,
    user_id: str = Query(..., description="User identifier")
):
    """
    Get a single prospect by ID.
    """
    try:
        doc_ref = db.collection("prospects").document(prospect_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Prospect not found")
        
        data = doc.to_dict()
        if data.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Prospect does not belong to user")
        
        # Extract fields (same logic as list endpoint)
        fit_score = data.get("fit_score") or (data.get("scores", {}) or {}).get("fit_score") or (data.get("analysis", {}) or {}).get("confidence_score")
        summary = data.get("summary") or (data.get("analysis", {}) or {}).get("summary")
        pain_points = data.get("pain_points")
        if pain_points and isinstance(pain_points, str):
            pain_points = [pain_points]
        
        prospect_status = data.get("status", "new")
        if "review_status" in data:
            prospect_status = data["review_status"]
        
        return ProspectResponse(
            id=prospect_id,
            name=data.get("name"),
            company=data.get("company"),
            job_title=data.get("job_title"),
            email=data.get("email"),
            fit_score=fit_score,
            status=prospect_status,
            tags=data.get("tags", []),
            last_action=data.get("last_action"),
            summary=summary,
            pain_points=pain_points if isinstance(pain_points, list) else None,
            analysis=data.get("analysis"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get prospect: {str(e)}")
