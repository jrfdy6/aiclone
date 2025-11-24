"""
Persona Service
"""
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from app.services.firestore_client import db
from app.models.personas import Persona

logger = logging.getLogger(__name__)


def create_persona(
    user_id: str,
    name: str,
    outreach_tone: str = "professional",
    industry_focus: Optional[List[str]] = None,
    use_cases: Optional[List[str]] = None,
    writing_style: str = "clear and concise",
    user_positioning: str = "",
    brand_voice: str = "",
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """Create a new persona."""
    try:
        persona_ref = db.collection("personas").document()
        persona_id = persona_ref.id
        
        now = datetime.now().isoformat()
        persona_data = {
            "user_id": user_id,
            "name": name,
            "is_default": False,
            "outreach_tone": outreach_tone,
            "industry_focus": industry_focus or [],
            "use_cases": use_cases or [],
            "writing_style": writing_style,
            "user_positioning": user_positioning,
            "brand_voice": brand_voice,
            "created_at": now,
            "updated_at": now,
            "metadata": metadata or {},
        }
        
        persona_ref.set(persona_data)
        logger.info(f"Created persona {persona_id} for user {user_id}")
        return persona_id
        
    except Exception as e:
        logger.error(f"Error creating persona: {e}")
        raise


def get_persona(persona_id: str) -> Optional[Persona]:
    """Get a persona by ID."""
    try:
        persona_doc = db.collection("personas").document(persona_id).get()
        
        if not persona_doc.exists:
            return None
        
        data = persona_doc.to_dict()
        return Persona(
            id=persona_id,
            user_id=data.get("user_id", ""),
            name=data.get("name", ""),
            is_default=data.get("is_default", False),
            outreach_tone=data.get("outreach_tone", "professional"),
            industry_focus=data.get("industry_focus", []),
            use_cases=data.get("use_cases", []),
            writing_style=data.get("writing_style", "clear and concise"),
            user_positioning=data.get("user_positioning", ""),
            brand_voice=data.get("brand_voice", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            metadata=data.get("metadata", {}),
        )
    except Exception as e:
        logger.error(f"Error getting persona {persona_id}: {e}")
        return None


def list_personas(user_id: str) -> List[Persona]:
    """List personas for a user."""
    try:
        query = db.collection("personas").where("user_id", "==", user_id)
        docs = query.stream()
        
        personas = []
        for doc in docs:
            try:
                data = doc.to_dict()
                personas.append(Persona(
                    id=doc.id,
                    user_id=data.get("user_id", ""),
                    name=data.get("name", ""),
                    is_default=data.get("is_default", False),
                    outreach_tone=data.get("outreach_tone", "professional"),
                    industry_focus=data.get("industry_focus", []),
                    use_cases=data.get("use_cases", []),
                    writing_style=data.get("writing_style", "clear and concise"),
                    user_positioning=data.get("user_positioning", ""),
                    brand_voice=data.get("brand_voice", ""),
                    created_at=data.get("created_at", ""),
                    updated_at=data.get("updated_at", ""),
                    metadata=data.get("metadata", {}),
                ))
            except Exception as e:
                logger.warning(f"Error processing persona document {doc.id}: {e}")
                continue
        
        # Sort by default first, then by name
        personas.sort(key=lambda x: (not x.is_default, x.name))
        return personas
    except Exception as e:
        logger.error(f"Error listing personas: {e}")
        return []


def update_persona(persona_id: str, updates: Dict[str, Any]) -> bool:
    """Update a persona."""
    try:
        persona_ref = db.collection("personas").document(persona_id)
        updates["updated_at"] = datetime.now().isoformat()
        persona_ref.update(updates)
        return True
    except Exception as e:
        logger.error(f"Error updating persona: {e}")
        return False


def delete_persona(persona_id: str) -> bool:
    """Delete a persona."""
    try:
        db.collection("personas").document(persona_id).delete()
        return True
    except Exception as e:
        logger.error(f"Error deleting persona: {e}")
        return False


def set_default_persona(user_id: str, persona_id: str) -> bool:
    """Set a persona as default (unset others)."""
    try:
        # Get all personas for user
        personas = list_personas(user_id)
        
        # Unset default on all personas
        for persona in personas:
            if persona.is_default:
                update_persona(persona.id, {"is_default": False})
        
        # Set new default
        return update_persona(persona_id, {"is_default": True})
    except Exception as e:
        logger.error(f"Error setting default persona: {e}")
        return False


def get_default_persona(user_id: str) -> Optional[Persona]:
    """Get the default persona for a user."""
    personas = list_personas(user_id)
    for persona in personas:
        if persona.is_default:
            return persona
    return None

