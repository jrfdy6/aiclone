"""
Prospect Discovery Routes

Endpoints for finding actual prospects from public directories.
"""

import ipaddress
import logging
import os
import re
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from app.models.prospect_discovery import (
    ProspectSource,
    SOURCE_DORKS,
    THEME_SPECIALTIES,
    ProspectDiscoveryRequest,
    ProspectDiscoveryResponse,
)
from app.services.prospect_discovery_service import PROSPECT_CATEGORIES, get_prospect_discovery_service
from app.services.firestore_client import get_firestore_client
from app.services.firestore_prospect_authority_service import (
    legacy_pipeline_projection,
    read_prospects,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Prospect Discovery"])

_SAFE_FIRESTORE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{0,127}$")


def _configured_owner_user_id() -> str:
    user_id = str(os.getenv("DEFAULT_USER_ID") or "default-user").strip()
    if not _SAFE_FIRESTORE_ID.fullmatch(user_id):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "state": "degraded",
                "reason_codes": ["owner_authority_misconfigured"],
                "message": "Prospect discovery owner authority is not configured safely.",
            },
        )
    return user_id


def _owner_user_id(requested: str | None = None) -> str:
    configured = _configured_owner_user_id()
    if requested is not None and requested != configured:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The requested user does not match the configured owner authority.",
        )
    return configured


def _safe_document_id(value: str, label: str) -> str:
    normalized = str(value or "").strip()
    if not _SAFE_FIRESTORE_ID.fullmatch(normalized):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid {label}.",
        )
    return normalized


def _bounded_text(value: Any, limit: int) -> str:
    raw = getattr(value, "value", value)
    return str(raw or "")[:limit]


def _bounded_nonnegative_int(value: Any, maximum: int = 1_000_000) -> int:
    try:
        return min(max(0, int(value or 0)), maximum)
    except (TypeError, ValueError):
        return 0


def _bounded_strings(value: Any, *, count: int, length: int) -> List[str]:
    if not isinstance(value, list):
        return []
    return [_bounded_text(item, length) for item in value[:count]]


def _bounded_discovery_summary(data: Dict[str, Any], *, document_id: str = "") -> Dict[str, Any]:
    raw_prospects = data.get("prospects")
    prospect_count = len(raw_prospects) if isinstance(raw_prospects, list) else data.get("prospect_count")
    return {
        "discovery_id": _bounded_text(data.get("discovery_id") or document_id, 128),
        "source": _bounded_text(data.get("source"), 100),
        "specialty": _bounded_text(data.get("specialty"), 500),
        "location": _bounded_text(data.get("location"), 500),
        "keywords": _bounded_strings(data.get("keywords"), count=50, length=300),
        "total_found": _bounded_nonnegative_int(data.get("total_found")),
        "prospect_count": _bounded_nonnegative_int(prospect_count),
        "created_at": data.get("created_at"),
    }


def _bounded_prospect_projection(data: Dict[str, Any]) -> Dict[str, Any]:
    contact = data.get("contact") if isinstance(data.get("contact"), dict) else {}
    fit_score = _bounded_nonnegative_int(data.get("fit_score"), 100)
    return {
        "name": _bounded_text(data.get("name"), 300),
        "title": _bounded_text(data.get("title"), 500),
        "organization": _bounded_text(data.get("organization"), 500),
        "specialty": _bounded_strings(data.get("specialty"), count=50, length=300),
        "location": _bounded_text(data.get("location"), 500),
        "source_url": _bounded_text(data.get("source_url"), 2_000),
        "source": _bounded_text(data.get("source"), 100),
        "contact": {
            "email": _bounded_text(contact.get("email"), 320),
            "phone": _bounded_text(contact.get("phone"), 100),
            "website": _bounded_text(contact.get("website"), 2_000),
            "linkedin": _bounded_text(contact.get("linkedin"), 2_000),
        },
        "bio_snippet": _bounded_text(data.get("bio_snippet"), 5_000),
        "fit_score": fit_score,
    }


def _bounded_discovery_detail(data: Dict[str, Any], *, document_id: str) -> Dict[str, Any]:
    prospects = data.get("prospects") if isinstance(data.get("prospects"), list) else []
    bounded_prospects = [
        _bounded_prospect_projection(item)
        for item in prospects[:100]
        if isinstance(item, dict)
    ]
    return {
        "state": "ready",
        **_bounded_discovery_summary(data, document_id=document_id),
        "prospects": bounded_prospects,
    }


def _validate_public_urls(urls: List[str]) -> List[str]:
    normalized: List[str] = []
    for raw in urls:
        value = str(raw or "").strip()
        parsed = urlparse(value)
        hostname = str(parsed.hostname or "").rstrip(".").lower()
        if parsed.scheme != "https" or not hostname or parsed.username or parsed.password:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Discovery URLs must be public HTTPS URLs without embedded credentials.",
            )
        if hostname == "localhost" or hostname.endswith(".localhost"):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Local discovery URLs are not allowed.")
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Private discovery URLs are not allowed.")
        normalized.append(value)
    return normalized


def _bounded_discovery_result(result: ProspectDiscoveryResponse, message: str) -> ProspectDiscoveryResponse:
    if result.success:
        bounded_prospects = []
        for prospect in result.prospects[:50]:
            bounded_prospects.append(
                prospect.model_copy(
                    update={
                        "name": _bounded_text(prospect.name, 300),
                        "title": _bounded_text(prospect.title, 500) or None,
                        "organization": _bounded_text(prospect.organization, 500) or None,
                        "specialty": _bounded_strings(prospect.specialty, count=50, length=300),
                        "location": _bounded_text(prospect.location, 500) or None,
                        "source_url": _bounded_text(prospect.source_url, 2_000),
                        "contact": prospect.contact.model_copy(
                            update={
                                "email": _bounded_text(prospect.contact.email, 320) or None,
                                "phone": _bounded_text(prospect.contact.phone, 100) or None,
                                "website": _bounded_text(prospect.contact.website, 2_000) or None,
                                "linkedin": _bounded_text(prospect.contact.linkedin, 2_000) or None,
                            }
                        ),
                        "bio_snippet": _bounded_text(prospect.bio_snippet, 5_000) or None,
                        "fit_score": _bounded_nonnegative_int(prospect.fit_score, 100),
                        "raw_data": {},
                    }
                )
            )
        return result.model_copy(
            update={
                "discovery_id": _bounded_text(result.discovery_id, 128),
                "source": _bounded_text(result.source, 100),
                "total_found": _bounded_nonnegative_int(result.total_found),
                "prospects": bounded_prospects,
                "search_query_used": _bounded_text(result.search_query_used, 2_000),
                "error": None,
            }
        )
    return result.model_copy(
        update={
            "error": message,
            "prospects": [],
            "search_query_used": "",
            "total_found": 0,
        }
    )


def _degraded_firestore_payload(*, user_id: str, collection: str) -> Dict[str, Any]:
    return {
        "state": "degraded",
        "reason_codes": ["firestore_unavailable"],
        "data_source": f"firestore:{collection}",
        "user_id": user_id,
    }


def _set_firestore_headers(response: Response, state: str, source: str, reason_codes: List[str] | None = None) -> None:
    response.headers["X-AI-Clone-Firestore-State"] = state
    response.headers["X-AI-Clone-Data-Source"] = source
    if reason_codes:
        response.headers["X-AI-Clone-Degraded-Reasons"] = ",".join(reason_codes)
    response.headers["Cache-Control"] = "no-store, max-age=0"


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
        owner_user_id = _owner_user_id(request.user_id)
        service = get_prospect_discovery_service()
        result = await service.discover_prospects(request.model_copy(update={"user_id": owner_user_id}))
        return _bounded_discovery_result(result, "Prospect discovery did not complete. Check connector readiness.")
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Prospect discovery failed [%s]", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "state": "degraded",
                "reason_codes": ["prospect_discovery_failed"],
                "message": "Prospect discovery is temporarily unavailable.",
            },
        ) from exc


@router.get("/user/{user_id}")
async def get_user_discoveries(
    user_id: str,
    response: Response,
    limit: int = Query(default=20, ge=1, le=100),
) -> Dict[str, Any]:
    """
    Get all prospect discoveries for a user.
    """
    user_id = _owner_user_id(user_id)
    client = get_firestore_client()
    if client is None:
        _set_firestore_headers(response, "degraded", "unavailable", ["firestore_unavailable"])
        return {
            **_degraded_firestore_payload(user_id=user_id, collection="prospect_discoveries"),
            "discoveries": [],
            "total": 0,
        }
    try:
        docs = client.collection("users").document(user_id).collection("prospect_discoveries").order_by(
            "created_at", direction="DESCENDING"
        ).limit(limit).stream()
        
        results = []
        for doc in docs:
            data = doc.to_dict() or {}
            results.append(_bounded_discovery_summary(data, document_id=str(doc.id)))
        
        _set_firestore_headers(response, "ready", "firestore:users/*/prospect_discoveries")
        return {
            "state": "ready",
            "user_id": user_id,
            "discoveries": results,
            "total": len(results)
        }
        
    except Exception as exc:
        logger.warning("Prospect discovery history read failed [%s]", type(exc).__name__)
        _set_firestore_headers(response, "degraded", "unavailable", ["firestore_read_failed"])
        payload = _degraded_firestore_payload(user_id=user_id, collection="prospect_discoveries")
        payload["reason_codes"] = ["firestore_read_failed"]
        return {**payload, "discoveries": [], "total": 0}


@router.get("/user/{user_id}/{discovery_id}")
async def get_discovery_by_id(user_id: str, discovery_id: str, response: Response) -> Dict[str, Any]:
    """
    Get a specific discovery with all prospects.
    """
    user_id = _owner_user_id(user_id)
    discovery_id = _safe_document_id(discovery_id, "discovery_id")
    client = get_firestore_client()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                **_degraded_firestore_payload(user_id=user_id, collection="prospect_discoveries"),
                "message": "Prospect discovery history is temporarily unavailable.",
            },
        )
    try:
        doc_ref = client.collection("users").document(user_id).collection("prospect_discoveries").document(discovery_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail=f"Discovery '{discovery_id}' not found")
        
        _set_firestore_headers(response, "ready", "firestore:users/*/prospect_discoveries")
        return _bounded_discovery_detail(doc.to_dict() or {}, document_id=str(doc.id))
        
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Prospect discovery detail read failed [%s]", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "state": "degraded",
                "reason_codes": ["firestore_read_failed"],
                "message": "Prospect discovery history is temporarily unavailable.",
            },
        ) from exc


class ScrapeUrlsRequest(BaseModel):
    """Request to scrape specific URLs"""
    user_id: Optional[str] = None
    urls: List[str] = Field(min_length=1, max_length=20)
    save_to_prospects: bool = False


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
        owner_user_id = _owner_user_id(request.user_id)
        service = get_prospect_discovery_service()
        result = await service.scrape_urls(
            user_id=owner_user_id,
            urls=_validate_public_urls(request.urls),
            save_to_prospects=request.save_to_prospects,
        )
        return _bounded_discovery_result(result, "Prospect URL discovery did not complete. Check connector readiness.")
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Prospect URL scraping failed [%s]", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "state": "degraded",
                "reason_codes": ["prospect_url_scrape_failed"],
                "message": "Prospect URL discovery is temporarily unavailable.",
            },
        ) from exc


class ProspectSearchRequest(BaseModel):
    """Request for prospect search"""
    user_id: Optional[str] = None
    specialty: str = Field(default="", max_length=300)
    location: str = Field(min_length=1, max_length=300)
    additional_context: Optional[str] = Field(default=None, max_length=2_000)
    max_results: int = Field(default=10, ge=1, le=50)
    categories: Optional[List[str]] = Field(default=None, max_length=16)
    save_to_prospects: bool = False


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
        owner_user_id = _owner_user_id(request.user_id)
        unknown_categories = sorted(set(request.categories or []) - set(PROSPECT_CATEGORIES))
        if unknown_categories:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="One or more prospect categories are not supported.",
            )
        service = get_prospect_discovery_service()
        result = await service.find_prospects_free(
            user_id=owner_user_id,
            specialty=request.specialty,
            location=request.location,
            additional_context=request.additional_context,
            max_results=request.max_results,
            categories=request.categories,
            save_to_prospects=request.save_to_prospects,
        )
        return _bounded_discovery_result(result, "Free prospect search did not complete. Check connector readiness.")
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Free prospect search failed [%s]", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "state": "degraded",
                "reason_codes": ["free_prospect_search_failed"],
                "message": "Free prospect search is temporarily unavailable.",
            },
        ) from exc


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
        owner_user_id = _owner_user_id(request.user_id)
        service = get_prospect_discovery_service()
        result = await service.find_prospects_with_ai(
            user_id=owner_user_id,
            specialty=request.specialty,
            location=request.location,
            additional_context=request.additional_context,
            max_results=request.max_results,
            save_to_prospects=request.save_to_prospects,
        )
        return _bounded_discovery_result(result, "AI prospect search did not complete. Check connector readiness.")
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("AI prospect search failed [%s]", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "state": "degraded",
                "reason_codes": ["ai_prospect_search_failed"],
                "message": "AI prospect search is temporarily unavailable.",
            },
        ) from exc


@router.get("/user/{user_id}/prospects/all")
async def get_all_discovered_prospects(
    user_id: str,
    response: Response,
    limit: int = Query(default=100, ge=1, le=500),
) -> Dict[str, Any]:
    """
    Get all prospects discovered across all discoveries.
    Aggregates and deduplicates by email.
    """
    try:
        user_id = _owner_user_id(user_id)
        authority = read_prospects(user_id)
        prospects = []
        seen_emails = set()
        
        for canonical in authority.documents:
            data = legacy_pipeline_projection(canonical)
            if not str(data.get("source") or "").startswith("discovery:"):
                continue
            email = data.get("email")
            
            # Deduplicate by email
            if email and email in seen_emails:
                continue
            if email:
                seen_emails.add(email)
            
            prospects.append(data)
            if len(prospects) >= limit:
                break
        
        # Sort by fit score
        prospects.sort(key=lambda p: p.get("fit_score", 0), reverse=True)
        
        _set_firestore_headers(response, authority.state, authority.source, list(authority.reason_codes))
        return {
            "state": authority.state,
            "reason_codes": list(authority.reason_codes),
            "data_source": authority.source,
            "user_id": user_id,
            "prospects": prospects,
            "total": len(prospects)
        }
        
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid user_id") from exc
