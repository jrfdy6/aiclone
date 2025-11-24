"""
Enhanced Playbook Service
"""
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from app.services.firestore_client import db
from app.models.playbooks import Playbook, PlaybookExecution

logger = logging.getLogger(__name__)

# Default playbooks (from existing code)
DEFAULT_PLAYBOOKS = [
    {
        "id": "ai_advantage_jumpstart",
        "name": "AI Advantage Jumpstart",
        "description": "Complete guide to leveraging AI for business growth",
        "category": "AI",
        "prompts": [
            {
                "id": "onboarding",
                "title": "Onboarding Prompt",
                "prompt": "I want you to act as my personal AI assistant starting today..."
            }
        ]
    },
    {
        "id": "linkedin_growth",
        "name": "LinkedIn Growth",
        "description": "Complete playbook for growing your LinkedIn presence and engagement",
        "category": "Social Media",
        "prompts": []
    },
    {
        "id": "b2b_prospecting",
        "name": "B2B Prospecting",
        "description": "End-to-end B2B prospecting strategy with outreach templates",
        "category": "Sales",
        "prompts": []
    },
    {
        "id": "newsletter_writing",
        "name": "Newsletter Writing",
        "description": "Create engaging newsletters that convert readers into customers",
        "category": "Content",
        "prompts": []
    },
    {
        "id": "competitor_analysis",
        "name": "Competitor Analysis",
        "description": "Deep dive into competitor strategies and market positioning",
        "category": "Research",
        "prompts": []
    },
    {
        "id": "seo_pillar_content",
        "name": "SEO Pillar Content",
        "description": "Build comprehensive SEO content that ranks and converts",
        "category": "Content",
        "prompts": []
    },
]


def get_playbook(playbook_id: str, user_id: Optional[str] = None) -> Optional[Playbook]:
    """Get a playbook by ID."""
    try:
        # First check Firestore for user-specific playbook
        if user_id:
            user_playbook_doc = db.collection("user_playbooks").document(f"{user_id}_{playbook_id}").get()
            if user_playbook_doc.exists:
                data = user_playbook_doc.to_dict()
                return Playbook(
                    id=playbook_id,
                    name=data.get("name", ""),
                    description=data.get("description", ""),
                    category=data.get("category", ""),
                    prompts=data.get("prompts", []),
                    is_favorite=data.get("is_favorite", False),
                    usage_count=data.get("usage_count", 0),
                    created_at=data.get("created_at", ""),
                    updated_at=data.get("updated_at", ""),
                    metadata=data.get("metadata", {}),
                )
        
        # Check default playbooks
        for default in DEFAULT_PLAYBOOKS:
            if default["id"] == playbook_id:
                # Get user preferences if user_id provided
                is_favorite = False
                usage_count = 0
                if user_id:
                    user_prefs_doc = db.collection("user_playbook_prefs").document(f"{user_id}_{playbook_id}").get()
                    if user_prefs_doc.exists:
                        prefs = user_prefs_doc.to_dict()
                        is_favorite = prefs.get("is_favorite", False)
                        usage_count = prefs.get("usage_count", 0)
                
                return Playbook(
                    id=default["id"],
                    name=default["name"],
                    description=default["description"],
                    category=default["category"],
                    prompts=default.get("prompts", []),
                    is_favorite=is_favorite,
                    usage_count=usage_count,
                    created_at=datetime.now().isoformat(),
                    updated_at=datetime.now().isoformat(),
                    metadata={},
                )
        
        return None
    except Exception as e:
        logger.error(f"Error getting playbook {playbook_id}: {e}")
        return None


def list_playbooks(user_id: Optional[str] = None, is_favorite: Optional[bool] = None) -> List[Playbook]:
    """List all playbooks."""
    try:
        playbooks = []
        
        # Get default playbooks
        for default in DEFAULT_PLAYBOOKS:
            is_fav = False
            usage = 0
            
            if user_id:
                prefs_doc = db.collection("user_playbook_prefs").document(f"{user_id}_{default['id']}").get()
                if prefs_doc.exists:
                    prefs = prefs_doc.to_dict()
                    is_fav = prefs.get("is_favorite", False)
                    usage = prefs.get("usage_count", 0)
            
            playbook = Playbook(
                id=default["id"],
                name=default["name"],
                description=default["description"],
                category=default["category"],
                prompts=default.get("prompts", []),
                is_favorite=is_fav,
                usage_count=usage,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                metadata={},
            )
            
            # Filter by favorite if specified
            if is_favorite is not None and playbook.is_favorite != is_favorite:
                continue
            
            playbooks.append(playbook)
        
        # Get user-specific playbooks
        if user_id:
            user_playbooks_docs = db.collection("user_playbooks").where("user_id", "==", user_id).stream()
            for doc in user_playbooks_docs:
                try:
                    data = doc.to_dict()
                    playbook = Playbook(
                        id=doc.id.replace(f"{user_id}_", ""),
                        name=data.get("name", ""),
                        description=data.get("description", ""),
                        category=data.get("category", ""),
                        prompts=data.get("prompts", []),
                        is_favorite=data.get("is_favorite", False),
                        usage_count=data.get("usage_count", 0),
                        created_at=data.get("created_at", ""),
                        updated_at=data.get("updated_at", ""),
                        metadata=data.get("metadata", {}),
                    )
                    
                    # Filter by favorite if specified
                    if is_favorite is not None and playbook.is_favorite != is_favorite:
                        continue
                    
                    playbooks.append(playbook)
                except Exception as e:
                    logger.warning(f"Error processing user playbook {doc.id}: {e}")
                    continue
        
        return playbooks
    except Exception as e:
        logger.error(f"Error listing playbooks: {e}")
        return []


def toggle_favorite(playbook_id: str, user_id: str) -> Optional[bool]:
    """Toggle favorite status of a playbook."""
    try:
        prefs_ref = db.collection("user_playbook_prefs").document(f"{user_id}_{playbook_id}")
        prefs_doc = prefs_ref.get()
        
        if prefs_doc.exists:
            current_fav = prefs_doc.to_dict().get("is_favorite", False)
            new_fav = not current_fav
        else:
            new_fav = True
        
        prefs_ref.set({
            "is_favorite": new_fav,
            "playbook_id": playbook_id,
            "user_id": user_id,
            "updated_at": datetime.now().isoformat(),
        }, merge=True)
        
        return new_fav
    except Exception as e:
        logger.error(f"Error toggling favorite: {e}")
        return None


def record_execution(
    playbook_id: str,
    user_id: str,
    input_text: str,
    output_text: str,
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """Record a playbook execution."""
    try:
        execution_ref = db.collection("playbook_executions").document()
        execution_id = execution_ref.id
        
        execution_data = {
            "playbook_id": playbook_id,
            "user_id": user_id,
            "input": input_text,
            "output": output_text,
            "executed_at": datetime.now().isoformat(),
            "metadata": metadata or {},
        }
        
        execution_ref.set(execution_data)
        
        # Update usage count
        prefs_ref = db.collection("user_playbook_prefs").document(f"{user_id}_{playbook_id}")
        prefs_doc = prefs_ref.get()
        
        if prefs_doc.exists:
            current_count = prefs_doc.to_dict().get("usage_count", 0)
            prefs_ref.update({"usage_count": current_count + 1})
        else:
            prefs_ref.set({
                "playbook_id": playbook_id,
                "user_id": user_id,
                "usage_count": 1,
                "updated_at": datetime.now().isoformat(),
            })
        
        return execution_id
    except Exception as e:
        logger.error(f"Error recording execution: {e}")
        raise


def list_executions(playbook_id: Optional[str] = None, user_id: Optional[str] = None, limit: int = 100) -> List[PlaybookExecution]:
    """List playbook executions."""
    try:
        query = db.collection("playbook_executions")
        
        if playbook_id:
            query = query.where("playbook_id", "==", playbook_id)
        
        if user_id:
            query = query.where("user_id", "==", user_id)
        
        try:
            docs = query.order_by("executed_at", direction="DESCENDING").limit(limit).stream()
        except Exception:
            docs = query.limit(limit).stream()
        
        executions = []
        for doc in docs:
            try:
                data = doc.to_dict()
                executions.append(PlaybookExecution(
                    id=doc.id,
                    playbook_id=data.get("playbook_id", ""),
                    user_id=data.get("user_id", ""),
                    input=data.get("input", ""),
                    output=data.get("output", ""),
                    executed_at=data.get("executed_at", ""),
                    metadata=data.get("metadata", {}),
                ))
            except Exception as e:
                logger.warning(f"Error processing execution document {doc.id}: {e}")
                continue
        
        # Sort in Python if order_by didn't work
        if executions:
            try:
                executions.sort(key=lambda x: x.executed_at, reverse=True)
            except:
                pass
        
        return executions
    except Exception as e:
        logger.error(f"Error listing executions: {e}")
        return []

