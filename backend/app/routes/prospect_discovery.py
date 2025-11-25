"""
Prospect Discovery Routes

Endpoints for finding actual prospects from public directories.
"""

import logging
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException

from app.models.prospect_discovery import (
    ProspectSource,
    SOURCE_DORKS,
    THEME_SPECIALTIES,
    ProspectDiscoveryRequest,
    ProspectDiscoveryResponse,
)
from app.services.prospect_discovery_service import get_prospect_discovery_service
from app.services.firestore_client import db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/sources")
async def get_sources() -> Dict[str, Any]:
    """
    Get all available prospect discovery sources.
    """
    sources = []
    for source in ProspectSource:
        sources.append({
            "id": source.value,
            "name": source.value.replace("_", " ").title(),
            "dork_count": len(SOURCE_DORKS.get(source, [])),
            "sample_dork": SOURCE_DORKS.get(source, [""])[0] if SOURCE_DORKS.get(source) else "",
        })
    
    return {
        "sources": sources,
        "total": len(sources)
    }


@router.get("/specialties/{theme}")
async def get_specialties_for_theme(theme: str) -> Dict[str, Any]:
    """
    Get recommended specialties for a theme.
    """
    specialties = THEME_SPECIALTIES.get(theme, [])
    
    if not specialties:
        return {
            "theme": theme,
            "specialties": [],
            "message": f"No predefined specialties for theme '{theme}'. Use custom specialty."
        }
    
    return {
        "theme": theme,
        "specialties": specialties,
        "total": len(specialties)
    }


@router.post("/search", response_model=ProspectDiscoveryResponse)
async def discover_prospects(request: ProspectDiscoveryRequest) -> Dict[str, Any]:
    """
    Discover prospects from a public source.
    
    This endpoint:
    1. Builds a targeted search query
    2. Scrapes relevant directory pages
    3. Extracts prospect data (name, title, contact, etc.)
    4. Calculates fit scores
    5. Returns structured prospect list
    
    Example request:
    ```json
    {
      "user_id": "user123",
      "source": "psychology_today",
      "specialty": "educational consultant",
      "location": "California",
      "max_results": 20
    }
    ```
    """
    try:
        service = get_prospect_discovery_service()
        result = await service.discover_prospects(request)
        return result
    
    except Exception as e:
        logger.exception(f"Prospect discovery failed: {e}")
        raise HTTPException(status_code=500, detail=f"Discovery failed: {str(e)}")


@router.get("/user/{user_id}")
async def get_user_discoveries(user_id: str, limit: int = 20) -> Dict[str, Any]:
    """
    Get all prospect discoveries for a user.
    """
    try:
        docs = db.collection("users").document(user_id).collection("prospect_discoveries").order_by(
            "created_at", direction="DESCENDING"
        ).limit(limit).stream()
        
        results = []
        for doc in docs:
            data = doc.to_dict()
            # Don't include full prospect list in summary
            data["prospect_count"] = len(data.get("prospects", []))
            data.pop("prospects", None)
            results.append(data)
        
        return {
            "user_id": user_id,
            "discoveries": results,
            "total": len(results)
        }
        
    except Exception as e:
        logger.exception(f"Error fetching discoveries: {e}")
        raise HTTPException(status_code=500, detail=f"Fetch failed: {str(e)}")


@router.get("/user/{user_id}/{discovery_id}")
async def get_discovery_by_id(user_id: str, discovery_id: str) -> Dict[str, Any]:
    """
    Get a specific discovery with all prospects.
    """
    try:
        doc_ref = db.collection("users").document(user_id).collection("prospect_discoveries").document(discovery_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail=f"Discovery '{discovery_id}' not found")
        
        return doc.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error fetching discovery: {e}")
        raise HTTPException(status_code=500, detail=f"Fetch failed: {str(e)}")


@router.get("/user/{user_id}/prospects/all")
async def get_all_discovered_prospects(user_id: str, limit: int = 100) -> Dict[str, Any]:
    """
    Get all prospects discovered across all discoveries.
    Aggregates and deduplicates by email.
    """
    try:
        # Get from prospects collection (where save_to_prospects=True sends them)
        docs = db.collection("users").document(user_id).collection("prospects").where(
            "source", ">=", "discovery:"
        ).limit(limit).stream()
        
        prospects = []
        seen_emails = set()
        
        for doc in docs:
            data = doc.to_dict()
            email = data.get("email")
            
            # Deduplicate by email
            if email and email in seen_emails:
                continue
            if email:
                seen_emails.add(email)
            
            prospects.append(data)
        
        # Sort by fit score
        prospects.sort(key=lambda p: p.get("fit_score", 0), reverse=True)
        
        return {
            "user_id": user_id,
            "prospects": prospects,
            "total": len(prospects)
        }
        
    except Exception as e:
        logger.exception(f"Error fetching prospects: {e}")
        raise HTTPException(status_code=500, detail=f"Fetch failed: {str(e)}")

