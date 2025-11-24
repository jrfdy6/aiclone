"""
Knowledge Vault Service
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from collections import defaultdict
from app.services.firestore_client import db
from app.models.vault import VaultItem, VaultTopicCategory

logger = logging.getLogger(__name__)


def create_vault_item(
    user_id: str,
    title: str,
    summary: str,
    category: VaultTopicCategory,
    tags: Optional[List[str]] = None,
    sources: Optional[List[Dict[str, str]]] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """Create a new vault item."""
    try:
        item_ref = db.collection("vault_items").document()
        item_id = item_ref.id
        
        now = datetime.now().isoformat()
        item_data = {
            "user_id": user_id,
            "title": title,
            "summary": summary,
            "category": category.value,
            "tags": tags or [],
            "sources": sources or [],
            "created_at": now,
            "updated_at": now,
            "linked_outreach_ids": [],
            "linked_content_ids": [],
            "metadata": metadata or {},
        }
        
        item_ref.set(item_data)
        logger.info(f"Created vault item {item_id} for user {user_id}")
        return item_id
        
    except Exception as e:
        logger.error(f"Error creating vault item: {e}")
        raise


def get_vault_item(item_id: str) -> Optional[VaultItem]:
    """Get a vault item by ID."""
    try:
        item_doc = db.collection("vault_items").document(item_id).get()
        
        if not item_doc.exists:
            return None
        
        data = item_doc.to_dict()
        return VaultItem(
            id=item_id,
            user_id=data.get("user_id", ""),
            title=data.get("title", ""),
            summary=data.get("summary", ""),
            category=VaultTopicCategory(data.get("category", "industry_insights")),
            tags=data.get("tags", []),
            sources=data.get("sources", []),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            linked_outreach_ids=data.get("linked_outreach_ids", []),
            linked_content_ids=data.get("linked_content_ids", []),
            metadata=data.get("metadata", {}),
        )
    except Exception as e:
        logger.error(f"Error getting vault item {item_id}: {e}")
        return None


def list_vault_items(
    user_id: str,
    category: Optional[VaultTopicCategory] = None,
    tags: Optional[List[str]] = None,
    limit: int = 100
) -> List[VaultItem]:
    """List vault items for a user."""
    try:
        query = db.collection("vault_items").where("user_id", "==", user_id)
        
        if category:
            query = query.where("category", "==", category.value)
        
        # Try to order by updated_at
        try:
            docs = query.order_by("updated_at", direction="DESCENDING").limit(limit).stream()
        except Exception:
            docs = query.limit(limit).stream()
        
        items = []
        for doc in docs:
            try:
                data = doc.to_dict()
                item = VaultItem(
                    id=doc.id,
                    user_id=data.get("user_id", ""),
                    title=data.get("title", ""),
                    summary=data.get("summary", ""),
                    category=VaultTopicCategory(data.get("category", "industry_insights")),
                    tags=data.get("tags", []),
                    sources=data.get("sources", []),
                    created_at=data.get("created_at", ""),
                    updated_at=data.get("updated_at", ""),
                    linked_outreach_ids=data.get("linked_outreach_ids", []),
                    linked_content_ids=data.get("linked_content_ids", []),
                    metadata=data.get("metadata", {}),
                )
                
                # Filter by tags if specified
                if tags and not any(tag in item.tags for tag in tags):
                    continue
                
                items.append(item)
            except Exception as e:
                logger.warning(f"Error processing vault item document {doc.id}: {e}")
                continue
        
        # Sort in Python if order_by didn't work
        if items:
            try:
                items.sort(key=lambda x: x.updated_at, reverse=True)
            except:
                pass
        
        return items
    except Exception as e:
        logger.error(f"Error listing vault items: {e}")
        return []


def update_vault_item(item_id: str, updates: Dict[str, Any]) -> bool:
    """Update a vault item."""
    try:
        item_ref = db.collection("vault_items").document(item_id)
        updates["updated_at"] = datetime.now().isoformat()
        item_ref.update(updates)
        return True
    except Exception as e:
        logger.error(f"Error updating vault item: {e}")
        return False


def delete_vault_item(item_id: str) -> bool:
    """Delete a vault item."""
    try:
        db.collection("vault_items").document(item_id).delete()
        return True
    except Exception as e:
        logger.error(f"Error deleting vault item: {e}")
        return False


def link_to_outreach(item_id: str, outreach_id: str) -> bool:
    """Link a vault item to an outreach."""
    try:
        item = get_vault_item(item_id)
        if not item:
            return False
        
        if outreach_id not in item.linked_outreach_ids:
            item.linked_outreach_ids.append(outreach_id)
            update_vault_item(item_id, {"linked_outreach_ids": item.linked_outreach_ids})
        return True
    except Exception as e:
        logger.error(f"Error linking to outreach: {e}")
        return False


def link_to_content(item_id: str, content_id: str) -> bool:
    """Link a vault item to content."""
    try:
        item = get_vault_item(item_id)
        if not item:
            return False
        
        if content_id not in item.linked_content_ids:
            item.linked_content_ids.append(content_id)
            update_vault_item(item_id, {"linked_content_ids": item.linked_content_ids})
        return True
    except Exception as e:
        logger.error(f"Error linking to content: {e}")
        return False

