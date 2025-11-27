"""
Prospect Discovery Routes

Endpoints for finding actual prospects from public directories.
"""

import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

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


class ScrapeUrlsRequest(BaseModel):
    """Request to scrape specific URLs"""
    user_id: str
    urls: List[str]


@router.post("/scrape-urls", response_model=ProspectDiscoveryResponse)
async def scrape_specific_urls(request: ScrapeUrlsRequest) -> Dict[str, Any]:
    """
    Scrape specific profile URLs for prospect data.
    
    Use this when you have direct URLs to profile pages (e.g., from Psychology Today).
    
    Example:
    ```json
    {
      "user_id": "user123",
      "urls": [
        "https://www.psychologytoday.com/us/therapists/jane-doe-12345",
        "https://www.psychologytoday.com/us/therapists/john-smith-67890"
      ]
    }
    ```
    """
    try:
        service = get_prospect_discovery_service()
        result = await service.scrape_urls(
            user_id=request.user_id,
            urls=request.urls
        )
        return result
    except Exception as e:
        logger.exception(f"URL scraping failed: {e}")
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")


class ProspectSearchRequest(BaseModel):
    """Request for prospect search"""
    user_id: str
    specialty: str = ""
    location: str
    additional_context: str = None
    max_results: int = 10
    categories: List[str] = None  # e.g., ["pediatricians", "psychologists", "embassies"]


@router.get("/categories")
async def get_prospect_categories() -> Dict[str, Any]:
    """
    Get all available prospect categories for the multiselect UI.
    """
    from app.services.prospect_discovery_service import PROSPECT_CATEGORIES
    
    categories = []
    for cat_id, cat_info in PROSPECT_CATEGORIES.items():
        categories.append({
            "id": cat_id,
            "name": cat_info["name"],
            "keywords": cat_info["keywords"][:3],  # Sample keywords
        })
    
    return {
        "categories": categories,
        "total": len(categories)
    }


@router.post("/search-free", response_model=ProspectDiscoveryResponse)
async def free_prospect_search(request: ProspectSearchRequest) -> Dict[str, Any]:
    """
    Find prospects using Google Search (FREE - 100 queries/day) + Firecrawl.
    
    Now supports category-based search for finding K-12 decision influencers:
    - education_consultants
    - pediatricians
    - psychologists
    - treatment_centers
    - embassies
    - youth_sports
    - mom_groups
    - international_students
    
    Example:
    ```json
    {
      "user_id": "user123",
      "location": "Washington DC",
      "categories": ["pediatricians", "psychologists", "treatment_centers"],
      "additional_context": "adolescent mental health",
      "max_results": 10
    }
    ```
    """
    try:
        service = get_prospect_discovery_service()
        result = await service.find_prospects_free(
            user_id=request.user_id,
            specialty=request.specialty,
            location=request.location,
            additional_context=request.additional_context,
            max_results=request.max_results,
            categories=request.categories
        )
        return result
    except Exception as e:
        logger.exception(f"Free prospect search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.post("/ai-search", response_model=ProspectDiscoveryResponse)
async def ai_prospect_search(request: ProspectSearchRequest) -> Dict[str, Any]:
    """
    Use Perplexity AI to find real prospects (PAID - use when free tier exhausted).
    
    Example:
    ```json
    {
      "user_id": "user123",
      "specialty": "educational consultant",
      "location": "Washington DC",
      "additional_context": "Focus on those who specialize in private school placement",
      "max_results": 10
    }
    ```
    """
    try:
        service = get_prospect_discovery_service()
        result = await service.find_prospects_with_ai(
            user_id=request.user_id,
            specialty=request.specialty,
            location=request.location,
            additional_context=request.additional_context,
            max_results=request.max_results
        )
        return result
    except Exception as e:
        logger.exception(f"AI prospect search failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI search failed: {str(e)}")


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

