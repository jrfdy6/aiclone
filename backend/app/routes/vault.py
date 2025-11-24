"""
Knowledge Vault Routes
"""
import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from app.models.vault import (
    VaultItemCreate, VaultItemUpdate, VaultItemResponse,
    VaultListResponse, TopicClustersResponse, TrendlinesResponse,
    TopicCluster, Trendline, VaultTopicCategory
)
from app.services.vault_service import (
    create_vault_item, get_vault_item, list_vault_items,
    update_vault_item, delete_vault_item, link_to_outreach, link_to_content
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("", response_model=VaultItemResponse)
async def create_vault_item_endpoint(request: VaultItemCreate) -> Dict[str, Any]:
    """Create a new vault item."""
    try:
        item_id = create_vault_item(
            user_id=request.user_id,
            title=request.title,
            summary=request.summary,
            category=request.category,
            tags=request.tags,
            sources=request.sources,
            metadata=request.metadata,
        )
        
        item = get_vault_item(item_id)
        if not item:
            raise HTTPException(status_code=500, detail="Failed to retrieve created vault item")
        
        return VaultItemResponse(success=True, item=item)
    except Exception as e:
        logger.exception(f"Error creating vault item: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create vault item: {str(e)}")


@router.get("", response_model=VaultListResponse)
async def list_vault_items_endpoint(
    user_id: str = Query(..., description="User identifier"),
    category: Optional[str] = Query(None, description="Filter by category"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    limit: int = Query(100, ge=1, le=500),
) -> Dict[str, Any]:
    """List vault items for a user."""
    try:
        vault_category = VaultTopicCategory(category) if category else None
        tag_list = [tag.strip() for tag in tags.split(",")] if tags else None
        
        items = list_vault_items(
            user_id=user_id,
            category=vault_category,
            tags=tag_list,
            limit=limit
        )
        return VaultListResponse(
            success=True,
            items=items,
            total=len(items)
        )
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
    except Exception as e:
        logger.exception(f"Error listing vault items: {e}")
        return VaultListResponse(success=True, items=[], total=0)


@router.get("/{item_id}", response_model=VaultItemResponse)
async def get_vault_item_endpoint(item_id: str) -> Dict[str, Any]:
    """Get a vault item by ID."""
    item = get_vault_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Vault item not found")
    return VaultItemResponse(success=True, item=item)


@router.put("/{item_id}", response_model=VaultItemResponse)
async def update_vault_item_endpoint(
    item_id: str,
    request: VaultItemUpdate
) -> Dict[str, Any]:
    """Update a vault item."""
    item = get_vault_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Vault item not found")
    
    updates = {}
    if request.title is not None:
        updates["title"] = request.title
    if request.summary is not None:
        updates["summary"] = request.summary
    if request.category is not None:
        updates["category"] = request.category.value
    if request.tags is not None:
        updates["tags"] = request.tags
    if request.sources is not None:
        updates["sources"] = request.sources
    if request.metadata is not None:
        updates["metadata"] = request.metadata
    
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    success = update_vault_item(item_id, updates)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update vault item")
    
    updated_item = get_vault_item(item_id)
    return VaultItemResponse(success=True, item=updated_item)


@router.delete("/{item_id}")
async def delete_vault_item_endpoint(item_id: str) -> Dict[str, Any]:
    """Delete a vault item."""
    item = get_vault_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Vault item not found")
    
    success = delete_vault_item(item_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete vault item")
    
    return {"success": True, "message": "Vault item deleted"}


@router.post("/{item_id}/link-outreach")
async def link_vault_to_outreach(
    item_id: str,
    outreach_id: str = Query(..., description="Outreach ID to link")
) -> Dict[str, Any]:
    """Link a vault item to an outreach."""
    success = link_to_outreach(item_id, outreach_id)
    if not success:
        raise HTTPException(status_code=404, detail="Vault item not found")
    return {"success": True, "message": "Linked to outreach"}


@router.post("/{item_id}/link-content")
async def link_vault_to_content(
    item_id: str,
    content_id: str = Query(..., description="Content ID to link")
) -> Dict[str, Any]:
    """Link a vault item to content."""
    success = link_to_content(item_id, content_id)
    if not success:
        raise HTTPException(status_code=404, detail="Vault item not found")
    return {"success": True, "message": "Linked to content"}


@router.get("/topics/clusters", response_model=TopicClustersResponse)
async def get_topic_clusters(
    user_id: str = Query(..., description="User identifier"),
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    """Get topic clusters from vault items."""
    try:
        items = list_vault_items(user_id=user_id, limit=1000)  # Get all items for clustering
        
        # Simple clustering by category
        clusters: Dict[str, List[VaultItem]] = {}
        for item in items:
            category = item.category.value
            if category not in clusters:
                clusters[category] = []
            clusters[category].append(item)
        
        cluster_list = [
            TopicCluster(
                topic=category.replace("_", " ").title(),
                item_count=len(items),
                items=items[:limit]
            )
            for category, items in clusters.items()
        ]
        
        return TopicClustersResponse(success=True, clusters=cluster_list)
    except Exception as e:
        logger.exception(f"Error getting topic clusters: {e}")
        return TopicClustersResponse(success=True, clusters=[])


@router.get("/trendlines", response_model=TrendlinesResponse)
async def get_trendlines(
    user_id: str = Query(..., description="User identifier"),
    days: int = Query(30, ge=7, le=365, description="Number of days to analyze"),
) -> Dict[str, Any]:
    """Get trendlines for vault items."""
    try:
        items = list_vault_items(user_id=user_id, limit=1000)
        
        # Group by date and category
        from collections import defaultdict
        from datetime import datetime, timedelta
        
        trend_data: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        
        for item in items:
            try:
                item_date = datetime.fromisoformat(item.created_at.split("T")[0])
                date_str = item_date.strftime("%Y-%m-%d")
                trend_data[date_str][item.category.value] += 1
            except:
                continue
        
        # Build trendlines
        trendlines = [
            Trendline(
                date=date,
                item_count=sum(categories.values()),
                categories=dict(categories)
            )
            for date, categories in sorted(trend_data.items())
        ]
        
        return TrendlinesResponse(
            success=True,
            trendlines=trendlines[-days:],  # Last N days
            period=f"{days} days"
        )
    except Exception as e:
        logger.exception(f"Error getting trendlines: {e}")
        return TrendlinesResponse(success=True, trendlines=[], period=f"{days} days")

