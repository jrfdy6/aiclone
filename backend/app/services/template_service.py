"""
Template Service - Manages templates
"""
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from app.services.firestore_client import db
from app.models.templates import Template, TemplateCategory

logger = logging.getLogger(__name__)


def create_template(
    user_id: str,
    name: str,
    category: TemplateCategory,
    content: str,
    description: Optional[str] = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """Create a new template."""
    try:
        template_ref = db.collection("templates").document()
        template_id = template_ref.id
        
        now = datetime.now().isoformat()
        template_data = {
            "user_id": user_id,
            "name": name,
            "category": category.value,
            "content": content,
            "description": description or "",
            "tags": tags or [],
            "is_favorite": False,
            "created_at": now,
            "updated_at": now,
            "usage_count": 0,
            "metadata": metadata or {},
        }
        
        template_ref.set(template_data)
        logger.info(f"Created template {template_id} for user {user_id}")
        return template_id
        
    except Exception as e:
        logger.error(f"Error creating template: {e}")
        raise


def get_template(template_id: str) -> Optional[Template]:
    """Get a template by ID."""
    try:
        template_doc = db.collection("templates").document(template_id).get()
        
        if not template_doc.exists:
            return None
        
        data = template_doc.to_dict()
        return Template(
            id=template_id,
            user_id=data.get("user_id", ""),
            name=data.get("name", ""),
            category=TemplateCategory(data.get("category", "linkedin_post")),
            content=data.get("content", ""),
            description=data.get("description"),
            tags=data.get("tags", []),
            is_favorite=data.get("is_favorite", False),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            usage_count=data.get("usage_count", 0),
            metadata=data.get("metadata", {}),
        )
    except Exception as e:
        logger.error(f"Error getting template {template_id}: {e}")
        return None


def list_templates(
    user_id: str,
    category: Optional[TemplateCategory] = None,
    is_favorite: Optional[bool] = None,
    limit: int = 100
) -> List[Template]:
    """List templates for a user."""
    try:
        query = db.collection("templates").where("user_id", "==", user_id)
        
        if category:
            query = query.where("category", "==", category.value)
        
        if is_favorite is not None:
            query = query.where("is_favorite", "==", is_favorite)
        
        # Try to order by updated_at
        try:
            docs = query.order_by("updated_at", direction="DESCENDING").limit(limit).stream()
        except Exception:
            docs = query.limit(limit).stream()
        
        templates = []
        for doc in docs:
            try:
                data = doc.to_dict()
                templates.append(Template(
                    id=doc.id,
                    user_id=data.get("user_id", ""),
                    name=data.get("name", ""),
                    category=TemplateCategory(data.get("category", "linkedin_post")),
                    content=data.get("content", ""),
                    description=data.get("description"),
                    tags=data.get("tags", []),
                    is_favorite=data.get("is_favorite", False),
                    created_at=data.get("created_at", ""),
                    updated_at=data.get("updated_at", ""),
                    usage_count=data.get("usage_count", 0),
                    metadata=data.get("metadata", {}),
                ))
            except Exception as e:
                logger.warning(f"Error processing template document {doc.id}: {e}")
                continue
        
        # Sort in Python if order_by didn't work
        if templates:
            try:
                templates.sort(key=lambda x: x.updated_at, reverse=True)
            except:
                pass
        
        return templates
    except Exception as e:
        logger.error(f"Error listing templates: {e}")
        return []


def update_template(template_id: str, updates: Dict[str, Any]) -> bool:
    """Update a template."""
    try:
        template_ref = db.collection("templates").document(template_id)
        updates["updated_at"] = datetime.now().isoformat()
        template_ref.update(updates)
        return True
    except Exception as e:
        logger.error(f"Error updating template: {e}")
        return False


def delete_template(template_id: str) -> bool:
    """Delete a template."""
    try:
        db.collection("templates").document(template_id).delete()
        return True
    except Exception as e:
        logger.error(f"Error deleting template: {e}")
        return False


def toggle_favorite(template_id: str) -> Optional[bool]:
    """Toggle favorite status of a template."""
    try:
        template = get_template(template_id)
        if not template:
            return None
        
        new_status = not template.is_favorite
        update_template(template_id, {"is_favorite": new_status})
        return new_status
    except Exception as e:
        logger.error(f"Error toggling favorite: {e}")
        return None


def increment_usage(template_id: str) -> bool:
    """Increment usage count for a template."""
    try:
        template = get_template(template_id)
        if not template:
            return False
        
        template_ref = db.collection("templates").document(template_id)
        template_ref.update({
            "usage_count": template.usage_count + 1,
            "updated_at": datetime.now().isoformat()
        })
        return True
    except Exception as e:
        logger.error(f"Error incrementing usage: {e}")
        return False

