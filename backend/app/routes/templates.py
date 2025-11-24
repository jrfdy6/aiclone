"""
Template Management Routes
"""
import logging
import re
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from app.models.templates import (
    TemplateCreate, TemplateUpdate, TemplateResponse,
    TemplateListResponse, TemplateUseRequest, TemplateUseResponse,
    TemplateCategory
)
from app.services.template_service import (
    create_template, get_template, list_templates, update_template,
    delete_template, toggle_favorite, increment_usage
)

logger = logging.getLogger(__name__)
router = APIRouter()


def render_template(content: str, variables: Dict[str, str]) -> str:
    """Replace variables in template content."""
    rendered = content
    for key, value in variables.items():
        # Replace {variable_name} or {{variable_name}} patterns
        rendered = re.sub(r'\{\{?\s*' + re.escape(key) + r'\s*\}\}?', value, rendered)
    return rendered


@router.post("", response_model=TemplateResponse)
async def create_template_endpoint(request: TemplateCreate) -> Dict[str, Any]:
    """Create a new template."""
    try:
        template_id = create_template(
            user_id=request.user_id,
            name=request.name,
            category=request.category,
            content=request.content,
            description=request.description,
            tags=request.tags,
            metadata=request.metadata,
        )
        
        template = get_template(template_id)
        if not template:
            raise HTTPException(status_code=500, detail="Failed to retrieve created template")
        
        return TemplateResponse(success=True, template=template)
    except Exception as e:
        logger.exception(f"Error creating template: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create template: {str(e)}")


@router.get("", response_model=TemplateListResponse)
async def list_templates_endpoint(
    user_id: str = Query(..., description="User identifier"),
    category: Optional[str] = Query(None, description="Filter by category"),
    is_favorite: Optional[bool] = Query(None, description="Filter by favorite status"),
    limit: int = Query(100, ge=1, le=500),
) -> Dict[str, Any]:
    """List templates for a user."""
    try:
        template_category = TemplateCategory(category) if category else None
        templates = list_templates(
            user_id=user_id,
            category=template_category,
            is_favorite=is_favorite,
            limit=limit
        )
        return TemplateListResponse(
            success=True,
            templates=templates,
            total=len(templates)
        )
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
    except Exception as e:
        logger.exception(f"Error listing templates: {e}")
        return TemplateListResponse(success=True, templates=[], total=0)


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template_endpoint(template_id: str) -> Dict[str, Any]:
    """Get a template by ID."""
    template = get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return TemplateResponse(success=True, template=template)


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template_endpoint(
    template_id: str,
    request: TemplateUpdate
) -> Dict[str, Any]:
    """Update a template."""
    template = get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    updates = {}
    if request.name is not None:
        updates["name"] = request.name
    if request.category is not None:
        updates["category"] = request.category.value
    if request.content is not None:
        updates["content"] = request.content
    if request.description is not None:
        updates["description"] = request.description
    if request.tags is not None:
        updates["tags"] = request.tags
    if request.metadata is not None:
        updates["metadata"] = request.metadata
    
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    success = update_template(template_id, updates)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update template")
    
    updated_template = get_template(template_id)
    return TemplateResponse(success=True, template=updated_template)


@router.delete("/{template_id}")
async def delete_template_endpoint(template_id: str) -> Dict[str, Any]:
    """Delete a template."""
    template = get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    success = delete_template(template_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete template")
    
    return {"success": True, "message": "Template deleted"}


@router.post("/{template_id}/favorite", response_model=TemplateResponse)
async def toggle_template_favorite(template_id: str) -> Dict[str, Any]:
    """Toggle favorite status of a template."""
    new_status = toggle_favorite(template_id)
    if new_status is None:
        raise HTTPException(status_code=404, detail="Template not found")
    
    template = get_template(template_id)
    return TemplateResponse(success=True, template=template)


@router.post("/{template_id}/duplicate", response_model=TemplateResponse)
async def duplicate_template(
    template_id: str,
    user_id: str = Query(..., description="User identifier")
) -> Dict[str, Any]:
    """Duplicate a template."""
    template = get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    try:
        new_template_id = create_template(
            user_id=user_id,
            name=f"{template.name} (Copy)",
            category=template.category,
            content=template.content,
            description=template.description,
            tags=template.tags,
            metadata=template.metadata,
        )
        
        new_template = get_template(new_template_id)
        return TemplateResponse(success=True, template=new_template)
    except Exception as e:
        logger.exception(f"Error duplicating template: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to duplicate template: {str(e)}")


@router.post("/{template_id}/use", response_model=TemplateUseResponse)
async def use_template(
    template_id: str,
    request: TemplateUseRequest
) -> Dict[str, Any]:
    """Use a template to generate content."""
    template = get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Render template with variables
    generated_content = render_template(template.content, request.variables)
    
    # Increment usage count
    increment_usage(template_id)
    
    return TemplateUseResponse(
        success=True,
        generated_content=generated_content,
        template_id=template_id,
        template_name=template.name
    )

