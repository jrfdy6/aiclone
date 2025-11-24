"""
Content Library Service
Repository, version control, approval workflows
"""
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from app.services.firestore_client import db
from app.models.content_library import (
    ContentItem, ContentCreate, ContentUpdate,
    ContentVersion, ContentStatus, ContentFormat
)

logger = logging.getLogger(__name__)


def create_content(user_id: str, content_data: ContentCreate) -> ContentItem:
    """Create new content item"""
    try:
        content_id = db.collection("users").document(user_id).collection("content_library").document().id
        now = datetime.now()
        
        # Create initial version
        initial_version = ContentVersion(
            version_number=1,
            content=content_data.content,
            created_at=now,
            created_by=user_id,
            changes="Initial version"
        )
        
        content_item = ContentItem(
            id=content_id,
            user_id=user_id,
            title=content_data.title,
            content=content_data.content,
            format=content_data.format,
            status=ContentStatus.DRAFT,
            pillar=content_data.pillar,
            tags=content_data.tags,
            hashtags=content_data.hashtags,
            versions=[initial_version],
            current_version=1,
            metadata=content_data.metadata,
            created_at=now,
            updated_at=now
        )
        
        db.collection("users").document(user_id).collection("content_library").document(content_id).set(
            content_item.model_dump(mode='json', exclude_none=True)
        )
        
        logger.info(f"Created content item: {content_id}")
        return content_item
        
    except Exception as e:
        logger.error(f"Error creating content: {e}")
        raise


def get_content(user_id: str, content_id: str) -> Optional[ContentItem]:
    """Get content item by ID"""
    try:
        doc = db.collection("users").document(user_id).collection("content_library").document(content_id).get()
        if not doc.exists:
            return None
        
        data = doc.to_dict()
        return ContentItem(**data)
    except Exception as e:
        logger.error(f"Error getting content: {e}")
        return None


def list_content(
    user_id: str,
    format: Optional[ContentFormat] = None,
    status: Optional[ContentStatus] = None,
    limit: int = 100
) -> List[ContentItem]:
    """List content items with optional filters"""
    try:
        query = db.collection("users").document(user_id).collection("content_library")
        
        if format:
            query = query.where("format", "==", format.value)
        if status:
            query = query.where("status", "==", status.value)
        
        query = query.order_by("created_at", direction="DESCENDING")
        
        docs = query.limit(limit).stream()
        return [ContentItem(**doc.to_dict()) for doc in docs]
    except Exception as e:
        logger.error(f"Error listing content: {e}")
        return []


def update_content(
    user_id: str,
    content_id: str,
    update_data: ContentUpdate,
    create_new_version: bool = True
) -> Optional[ContentItem]:
    """Update content item, optionally creating new version"""
    try:
        doc_ref = db.collection("users").document(user_id).collection("content_library").document(content_id)
        current_content = get_content(user_id, content_id)
        
        if not current_content:
            return None
        
        update_dict = update_data.model_dump(exclude_unset=True)
        
        # If content changed, create new version
        if create_new_version and "content" in update_dict:
            new_version_num = current_content.current_version + 1
            new_version = ContentVersion(
                version_number=new_version_num,
                content=update_dict["content"],
                created_at=datetime.now(),
                created_by=user_id,
                changes=update_dict.get("changes", "Content updated")
            )
            
            # Add to versions list
            versions = current_content.versions + [new_version]
            update_dict["versions"] = [v.model_dump(mode='json') for v in versions]
            update_dict["current_version"] = new_version_num
        
        update_dict["updated_at"] = datetime.now()
        doc_ref.update(update_dict)
        
        logger.info(f"Updated content item: {content_id}")
        return get_content(user_id, content_id)
        
    except Exception as e:
        logger.error(f"Error updating content: {e}")
        return None


def approve_content(user_id: str, content_id: str, approver_id: str, comments: Optional[str] = None) -> bool:
    """Approve content item"""
    try:
        doc_ref = db.collection("users").document(user_id).collection("content_library").document(content_id)
        doc_ref.update({
            "status": ContentStatus.APPROVED.value,
            "approved_by": approver_id,
            "approved_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        })
        
        logger.info(f"Content approved: {content_id} by {approver_id}")
        return True
    except Exception as e:
        logger.error(f"Error approving content: {e}")
        return False


def publish_content(user_id: str, content_id: str, platforms: List[str]) -> bool:
    """Publish content to platforms"""
    try:
        doc_ref = db.collection("users").document(user_id).collection("content_library").document(content_id)
        doc_ref.update({
            "status": ContentStatus.PUBLISHED.value,
            "published_at": datetime.now().isoformat(),
            "published_platforms": platforms,
            "updated_at": datetime.now().isoformat()
        })
        
        logger.info(f"Content published: {content_id} to {platforms}")
        return True
    except Exception as e:
        logger.error(f"Error publishing content: {e}")
        return False


def delete_content(user_id: str, content_id: str) -> bool:
    """Delete content item"""
    try:
        doc_ref = db.collection("users").document(user_id).collection("content_library").document(content_id)
        doc_ref.delete()
        logger.info(f"Deleted content: {content_id}")
        return True
    except Exception as e:
        logger.error(f"Error deleting content: {e}")
        return False

