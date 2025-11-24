"""
Content Library Routes
"""
import logging
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Query, Body
from app.models.content_library import (
    ContentCreate, ContentUpdate, ContentResponse,
    ContentListResponse, ContentFormat, ContentStatus
)
from app.services.content_library_service import (
    create_content, get_content, list_content,
    update_content, approve_content, publish_content, delete_content
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("", response_model=ContentResponse)
async def create_content_endpoint(request: ContentCreate) -> Dict[str, Any]:
    """Create new content item"""
    try:
        content = create_content(request.user_id, request)
        return ContentResponse(success=True, content=content)
    except Exception as e:
        logger.exception(f"Error creating content: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create content: {str(e)}")


@router.get("", response_model=ContentListResponse)
async def list_content_endpoint(
    user_id: str = Query(..., description="User identifier"),
    format: Optional[ContentFormat] = Query(None, description="Filter by format"),
    status: Optional[ContentStatus] = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=500)
) -> Dict[str, Any]:
    """List content items"""
    try:
        items = list_content(user_id, format, status, limit)
        return ContentListResponse(success=True, content_items=items, total=len(items))
    except Exception as e:
        logger.exception(f"Error listing content: {e}")
        return ContentListResponse(success=True, content_items=[], total=0)


@router.get("/{content_id}", response_model=ContentResponse)
async def get_content_endpoint(
    content_id: str,
    user_id: str = Query(..., description="User identifier")
) -> Dict[str, Any]:
    """Get content item by ID"""
    content = get_content(user_id, content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    return ContentResponse(success=True, content=content)


@router.put("/{content_id}", response_model=ContentResponse)
async def update_content_endpoint(
    content_id: str,
    request: ContentUpdate,
    user_id: str = Query(..., description="User identifier"),
    create_new_version: bool = Query(True, description="Create new version on update")
) -> Dict[str, Any]:
    """Update content item"""
    content = update_content(user_id, content_id, request, create_new_version)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    return ContentResponse(success=True, content=content)


@router.post("/{content_id}/approve", response_model=Dict[str, bool])
async def approve_content_endpoint(
    content_id: str,
    approver_id: str = Query(..., description="Approver user ID"),
    user_id: str = Query(..., description="Content owner user ID"),
    comments: Optional[str] = Query(None, description="Approval comments")
) -> Dict[str, bool]:
    """Approve content item"""
    success = approve_content(user_id, content_id, approver_id)
    if not success:
        raise HTTPException(status_code=404, detail="Content not found")
    return {"success": True}


@router.post("/{content_id}/publish", response_model=Dict[str, bool])
async def publish_content_endpoint(
    content_id: str,
    platforms: List[str] = Body(..., description="List of platforms to publish to"),
    user_id: str = Query(..., description="User identifier")
) -> Dict[str, bool]:
    """Publish content to platforms"""
    success = publish_content(user_id, content_id, platforms)
    if not success:
        raise HTTPException(status_code=404, detail="Content not found")
    return {"success": True}


@router.delete("/{content_id}", response_model=Dict[str, bool])
async def delete_content_endpoint(
    content_id: str,
    user_id: str = Query(..., description="User identifier")
) -> Dict[str, bool]:
    """Delete content item"""
    success = delete_content(user_id, content_id)
    if not success:
        raise HTTPException(status_code=404, detail="Content not found")
    return {"success": True}

