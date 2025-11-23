"""
Prospect Routes - Discovery, Approval, Scoring
"""

import logging
import time
import re
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException

from app.services.search_client import get_search_client
from app.services.firecrawl_client import get_firecrawl_client
from app.services.scoring import score_prospect
from app.services.firestore_client import db
from app.models.prospect import (
    ProspectDiscoveryRequest,
    ProspectDiscoveryResponse,
    ProspectApproveRequest,
    ProspectScoreRequest,
    ProspectScoreResponse,
    Prospect,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def extract_prospect_info(html_content: str, url: str) -> Optional[Dict[str, Any]]:
    """
    Extract prospect information from scraped HTML.
    Simple regex-based extraction - in production, use more sophisticated parsing.
    """
    content_lower = html_content.lower()
    
    # Try to extract email
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, html_content)
    email = emails[0] if emails else None
    
    # Try to extract name (look for common patterns)
    name_patterns = [
        r'<h[1-3][^>]*>([A-Z][a-z]+ [A-Z][a-z]+)</h[1-3]>',
        r'<p[^>]*>([A-Z][a-z]+ [A-Z][a-z]+)</p>',
        r'([A-Z][a-z]+ [A-Z][a-z]+), (VP|Director|Head|Chief|Founder|CEO)',
    ]
    name = None
    for pattern in name_patterns:
        matches = re.findall(pattern, html_content)
        if matches:
            name = matches[0] if isinstance(matches[0], str) else matches[0][0]
            break
    
    # Try to extract job title
    job_title = None
    title_keywords = ["VP", "Director", "Head", "Chief", "Founder", "CEO", "President", "Manager"]
    for keyword in title_keywords:
        if keyword.lower() in content_lower:
            # Try to find full title
            title_pattern = rf'({keyword}[^,<]*?)(?:,|</|$)'
            matches = re.findall(title_pattern, html_content, re.IGNORECASE)
            if matches:
                job_title = matches[0].strip()
                break
    
    # Try to extract LinkedIn URL
    linkedin_pattern = r'https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9-]+'
    linkedin_matches = re.findall(linkedin_pattern, html_content)
    linkedin = linkedin_matches[0] if linkedin_matches else None
    
    if not name and not email:
        return None
    
    return {
        "name": name or "Unknown",
        "email": email,
        "job_title": job_title or "Unknown",
        "linkedin": linkedin,
    }


@router.post("/discover", response_model=ProspectDiscoveryResponse)
async def discover_prospects(request: ProspectDiscoveryRequest) -> Dict[str, Any]:
    """
    Discover prospects using Google Custom Search + Firecrawl.
    
    Process:
    1. Search API finds relevant company pages
    2. Firecrawl scrapes team pages
    3. Extract prospect information
    4. Store as "pending" approval status
    """
    try:
        search_client = get_search_client()
        firecrawl = get_firecrawl_client()
        
        # Step 1: Build search query
        query_parts = []
        if request.company_name:
            query_parts.append(f'"{request.company_name}"')
        else:
            query_parts.append("companies")
        
        if request.industry:
            query_parts.append(request.industry)
        
        if request.location:
            query_parts.append(request.location)
        
        query_parts.append("team about contact")
        search_query = " ".join(query_parts)
        
        # Step 2: Search for company pages
        search_results = search_client.search_companies(
            industry=request.industry,
            location=request.location,
            company_name=request.company_name,
            max_results=request.max_results,
        )
        
        # Step 3: Scrape team pages and extract prospects
        discovered_prospects = []
        seen_emails = set()
        
        for result in search_results[:20]:  # Limit to 20 URLs to scrape
            try:
                # Scrape the page
                scraped = firecrawl.scrape_url(result.link)
                
                # Extract prospect info
                prospect_info = extract_prospect_info(scraped.content, result.link)
                
                if prospect_info:
                    # Avoid duplicates
                    email = prospect_info.get("email")
                    if email and email in seen_emails:
                        continue
                    if email:
                        seen_emails.add(email)
                    
                    # Extract company name from URL or page
                    company = result.display_link.replace("www.", "").split(".")[0].title()
                    
                    # Create prospect document
                    prospect_id = f"prospect_{int(time.time())}_{len(discovered_prospects)}"
                    prospect_data = {
                        "prospect_id": prospect_id,
                        "user_id": request.user_id,
                        "name": prospect_info.get("name", "Unknown"),
                        "email": prospect_info.get("email"),
                        "job_title": prospect_info.get("job_title", "Unknown"),
                        "company": company,
                        "website": result.link,
                        "linkedin": prospect_info.get("linkedin"),
                        "discovery_source": "SearchAPI + Firecrawl",
                        "approval_status": "pending",
                        "linked_research_ids": [],
                        "created_at": time.time(),
                        "updated_at": time.time(),
                    }
                    
                    # Store in Firestore
                    doc_ref = db.collection("users").document(request.user_id).collection("prospects").document(prospect_id)
                    doc_ref.set(prospect_data)
                    
                    discovered_prospects.append(Prospect(**prospect_data))
                    
                    if len(discovered_prospects) >= request.max_results:
                        break
                        
            except Exception as e:
                logger.warning(f"Error processing {result.link}: {e}")
                continue
        
        return ProspectDiscoveryResponse(
            success=True,
            discovered_count=len(discovered_prospects),
            prospects=discovered_prospects
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"API configuration error: {str(e)}. Please set GOOGLE_CUSTOM_SEARCH_API_KEY and GOOGLE_CUSTOM_SEARCH_ENGINE_ID environment variables."
        )
    except Exception as e:
        logger.exception(f"Error discovering prospects: {e}")
        raise HTTPException(status_code=500, detail=f"Prospect discovery failed: {str(e)}")


@router.post("/approve")
async def approve_prospects(request: ProspectApproveRequest) -> Dict[str, Any]:
    """
    Approve or reject discovered prospects.
    """
    try:
        approved_count = 0
        rejected_count = 0
        errors = []
        
        for prospect_id in request.prospect_ids:
            try:
                doc_ref = db.collection("users").document(request.user_id).collection("prospects").document(prospect_id)
                doc = doc_ref.get()
                
                if not doc.exists:
                    errors.append(f"Prospect {prospect_id} not found")
                    continue
                
                # Update approval status
                updates = {
                    "approval_status": request.approval_status,
                    "updated_at": time.time(),
                }
                
                if request.approval_status == "approved":
                    updates["approved_at"] = time.time()
                    updates["approved_by"] = request.user_id
                    approved_count += 1
                else:
                    rejected_count += 1
                
                doc_ref.update(updates)
                
            except Exception as e:
                errors.append(f"Error processing {prospect_id}: {str(e)}")
        
        return {
            "success": True,
            "approved_count": approved_count,
            "rejected_count": rejected_count,
            "errors": errors
        }
        
    except Exception as e:
        logger.exception(f"Error approving prospects: {e}")
        raise HTTPException(status_code=500, detail=f"Prospect approval failed: {str(e)}")


@router.post("/score", response_model=ProspectScoreResponse)
async def score_prospects(request: ProspectScoreRequest) -> Dict[str, Any]:
    """
    Score prospects using hybrid approach (cached + query research).
    
    Process:
    1. Retrieve cached insights from prospect
    2. Query Firestore for research summaries
    3. Merge insights
    4. Calculate multi-dimensional scores
    5. Cache insights back to prospect
    """
    try:
        scored_prospects = []
        
        for prospect_id in request.prospect_ids:
            try:
                # Fetch prospect from Firestore
                doc_ref = db.collection("users").document(request.user_id).collection("prospects").document(prospect_id)
                doc = doc_ref.get()
                
                if not doc.exists:
                    continue
                
                prospect_data = doc.to_dict()
                
                # Only score approved prospects
                if prospect_data.get("approval_status") != "approved":
                    continue
                
                # Score the prospect
                scored_data = score_prospect(
                    prospect_data,
                    request.user_id,
                    request.audience_profile
                )
                
                # Update in Firestore
                updates = {
                    "fit_score": scored_data.get("fit_score"),
                    "referral_capacity": scored_data.get("referral_capacity"),
                    "signal_strength": scored_data.get("signal_strength"),
                    "best_outreach_angle": scored_data.get("best_outreach_angle"),
                    "scoring_reasoning": scored_data.get("scoring_reasoning"),
                    "cached_insights": scored_data.get("cached_insights"),
                    "scored_at": scored_data.get("scored_at"),
                    "updated_at": time.time(),
                }
                
                doc_ref.update(updates)
                
                # Add to response
                scored_data["prospect_id"] = prospect_id
                scored_prospects.append(Prospect(**scored_data))
                
            except Exception as e:
                logger.warning(f"Error scoring prospect {prospect_id}: {e}")
                continue
        
        return ProspectScoreResponse(
            success=True,
            scored_count=len(scored_prospects),
            prospects=scored_prospects
        )
        
    except Exception as e:
        logger.exception(f"Error scoring prospects: {e}")
        raise HTTPException(status_code=500, detail=f"Prospect scoring failed: {str(e)}")



