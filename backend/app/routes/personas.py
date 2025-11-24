"""
Personas Routes
"""
import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Query
from app.models.personas import (
    PersonaCreate, PersonaUpdate, PersonaResponse, PersonaListResponse
)
from app.services.persona_service import (
    create_persona, get_persona, list_personas, update_persona,
    delete_persona, set_default_persona, get_default_persona
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("", response_model=PersonaResponse)
async def create_persona_endpoint(request: PersonaCreate) -> Dict[str, Any]:
    """Create a new persona."""
    try:
        persona_id = create_persona(
            user_id=request.user_id,
            name=request.name,
            outreach_tone=request.outreach_tone or "professional",
            industry_focus=request.industry_focus or [],
            use_cases=request.use_cases or [],
            writing_style=request.writing_style or "clear and concise",
            user_positioning=request.user_positioning or "",
            brand_voice=request.brand_voice or "",
            metadata=request.metadata or {},
        )
        
        persona = get_persona(persona_id)
        if not persona:
            raise HTTPException(status_code=500, detail="Failed to retrieve created persona")
        
        return PersonaResponse(success=True, persona=persona)
    except Exception as e:
        logger.exception(f"Error creating persona: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create persona: {str(e)}")


@router.get("", response_model=PersonaListResponse)
async def list_personas_endpoint(
    user_id: str = Query(..., description="User identifier")
) -> Dict[str, Any]:
    """List personas for a user."""
    try:
        personas = list_personas(user_id=user_id)
        return PersonaListResponse(
            success=True,
            personas=personas,
            total=len(personas)
        )
    except Exception as e:
        logger.exception(f"Error listing personas: {e}")
        return PersonaListResponse(success=True, personas=[], total=0)


@router.get("/default", response_model=PersonaResponse)
async def get_default_persona_endpoint(
    user_id: str = Query(..., description="User identifier")
) -> Dict[str, Any]:
    """Get the default persona for a user."""
    persona = get_default_persona(user_id)
    if not persona:
        raise HTTPException(status_code=404, detail="No default persona found")
    return PersonaResponse(success=True, persona=persona)


@router.get("/{persona_id}", response_model=PersonaResponse)
async def get_persona_endpoint(persona_id: str) -> Dict[str, Any]:
    """Get a persona by ID."""
    persona = get_persona(persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    return PersonaResponse(success=True, persona=persona)


@router.put("/{persona_id}", response_model=PersonaResponse)
async def update_persona_endpoint(
    persona_id: str,
    request: PersonaUpdate
) -> Dict[str, Any]:
    """Update a persona."""
    persona = get_persona(persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    
    updates = {}
    if request.name is not None:
        updates["name"] = request.name
    if request.outreach_tone is not None:
        updates["outreach_tone"] = request.outreach_tone
    if request.industry_focus is not None:
        updates["industry_focus"] = request.industry_focus
    if request.use_cases is not None:
        updates["use_cases"] = request.use_cases
    if request.writing_style is not None:
        updates["writing_style"] = request.writing_style
    if request.user_positioning is not None:
        updates["user_positioning"] = request.user_positioning
    if request.brand_voice is not None:
        updates["brand_voice"] = request.brand_voice
    if request.metadata is not None:
        updates["metadata"] = request.metadata
    
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    success = update_persona(persona_id, updates)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update persona")
    
    updated_persona = get_persona(persona_id)
    return PersonaResponse(success=True, persona=updated_persona)


@router.delete("/{persona_id}")
async def delete_persona_endpoint(persona_id: str) -> Dict[str, Any]:
    """Delete a persona."""
    persona = get_persona(persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    
    success = delete_persona(persona_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete persona")
    
    return {"success": True, "message": "Persona deleted"}


@router.post("/{persona_id}/set-default", response_model=PersonaResponse)
async def set_default_persona_endpoint(
    persona_id: str,
    user_id: str = Query(..., description="User identifier")
) -> Dict[str, Any]:
    """Set a persona as default."""
    persona = get_persona(persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    
    if persona.user_id != user_id:
        raise HTTPException(status_code=403, detail="Persona does not belong to user")
    
    success = set_default_persona(user_id, persona_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to set default persona")
    
    updated_persona = get_persona(persona_id)
    return PersonaResponse(success=True, persona=updated_persona)

