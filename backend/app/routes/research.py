"""
Research Routes - Manual research trigger
"""

import logging
import time
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.perplexity_client import get_perplexity_client
from app.services.firecrawl_client import get_firecrawl_client
from app.services.firestore_client import db
from app.models.research import ResearchTriggerRequest, ResearchTriggerResponse, ResearchInsight, ResearchSource

logger = logging.getLogger(__name__)
router = APIRouter()


def extract_insights_from_research(research_text: str, sources: list) -> Dict[str, Any]:
    """
    Extract structured insights from research text.
    In production, this would use an LLM to extract structured data.
    For now, we do simple keyword extraction.
    """
    text_lower = research_text.lower()
    
    # Extract keywords (simple approach - look for common business terms)
    keywords = []
    common_keywords = [
        "growth", "scaling", "revenue", "efficiency", "automation",
        "saas", "b2b", "enterprise", "smb", "startup",
        "sales", "marketing", "customer", "retention", "acquisition"
    ]
    for keyword in common_keywords:
        if keyword in text_lower:
            keywords.append(keyword)
    
    # Extract job titles (simple approach)
    job_titles = []
    title_keywords = ["vp", "director", "head", "chief", "founder", "ceo", "president", "manager"]
    for title in title_keywords:
        if title in text_lower:
            job_titles.append(title.title())
    
    # Extract pains (simple approach - look for pain indicators)
    pains = []
    pain_indicators = ["challenge", "problem", "struggle", "difficulty", "pain", "issue", "barrier"]
    for indicator in pain_indicators:
        if indicator in text_lower:
            pains.append(indicator)
    
    # Extract trends (simple approach)
    trends = []
    trend_indicators = ["trend", "growing", "increasing", "rising", "emerging", "popular"]
    for indicator in trend_indicators:
        if indicator in text_lower:
            trends.append(indicator)
    
    return {
        "keywords": list(set(keywords))[:10],  # Limit to top 10
        "job_titles": list(set(job_titles))[:10],
        "trending_pains": list(set(pains))[:10],
        "industry_trends": list(set(trends))[:10],
    }


@router.post("/trigger", response_model=ResearchTriggerResponse)
async def trigger_research(request: ResearchTriggerRequest) -> Dict[str, Any]:
    """
    Manually trigger research on a topic/industry.
    
    Process:
    1. Perplexity searches the topic
    2. Firecrawl scrapes top source URLs
    3. AI summarizes insights
    4. Store lightweight summary in Firestore
    """
    try:
        # Step 1: Research with Perplexity
        perplexity = get_perplexity_client()
        research_data = perplexity.research_topic(
            topic=request.topic,
            num_results=10,
            include_comparison=True,
        )
        
        # Step 2: Scrape additional content from sources using Firecrawl
        firecrawl = get_firecrawl_client()
        scraped_content = []
        sources_to_scrape = research_data.get("sources", [])[:5]  # Limit to 5 URLs
        
        for source in sources_to_scrape:
            url = source.get("url", "")
            if url:
                try:
                    scraped = firecrawl.scrape_url(url)
                    scraped_content.append({
                        "url": url,
                        "title": scraped.title,
                        "content": scraped.content[:1000],  # Limit content length
                    })
                except Exception as e:
                    logger.warning(f"Failed to scrape {url}: {e}")
                    continue
        
        # Step 3: Extract insights from research
        research_summary = research_data.get("summary", "")
        all_sources = research_data.get("sources", [])
        
        # Combine research summary with scraped content
        combined_text = research_summary
        for scraped in scraped_content:
            combined_text += " " + scraped.get("content", "")
        
        # Extract structured insights
        insights = extract_insights_from_research(combined_text, all_sources)
        
        # Step 4: Build research insight document
        research_insight = ResearchInsight(
            title=request.topic,
            industry=request.industry or request.topic.split()[0] if request.topic else "General",
            summary=research_summary[:500],  # Lightweight summary
            keywords=insights["keywords"],
            job_titles=insights["job_titles"],
            sources=[ResearchSource(url=s.get("url", ""), title=s.get("title", "")) for s in all_sources[:10]],
            created_at=time.time(),
            updated_at=time.time(),
        )
        
        # Step 5: Store in Firestore
        research_id = f"research_{int(time.time())}"
        research_doc = {
            "research_id": research_id,
            "title": research_insight.title,
            "industry": research_insight.industry,
            "summary": research_insight.summary,
            "keywords": research_insight.keywords,
            "job_titles": research_insight.job_titles,
            "linked_research_ids": [],
            "sources": [{"url": s.url, "title": s.title} for s in research_insight.sources],
            "created_at": research_insight.created_at,
            "updated_at": research_insight.updated_at,
        }
        
        doc_ref = db.collection("users").document(request.user_id).collection("research_insights").document(research_id)
        doc_ref.set(research_doc)
        
        return ResearchTriggerResponse(
            success=True,
            research_id=research_id,
            status="success",
            summary=research_insight
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"API configuration error: {str(e)}. Please set PERPLEXITY_API_KEY and/or FIRECRAWL_API_KEY environment variables."
        )
    except Exception as e:
        logger.exception(f"Error triggering research: {e}")
        raise HTTPException(status_code=500, detail=f"Research trigger failed: {str(e)}")


class ResearchStoreRequest(BaseModel):
    """Request to store MCP-generated research."""
    user_id: str = Field(..., description="User ID")
    title: str = Field(..., description="Research topic/title")
    industry: Optional[str] = Field(None, description="Industry")
    summary: str = Field(..., description="Research summary from MCP")
    keywords: List[str] = Field(default_factory=list, description="Extracted keywords")
    job_titles: List[str] = Field(default_factory=list, description="Relevant job titles")
    trending_pains: Optional[List[str]] = Field(default_factory=list, description="Trending pain points")
    industry_trends: Optional[List[str]] = Field(default_factory=list, description="Industry trends")
    sources: List[Dict[str, str]] = Field(default_factory=list, description="Source URLs and titles")


@router.post("/store", response_model=ResearchTriggerResponse)
async def store_research(request: ResearchStoreRequest) -> Dict[str, Any]:
    """
    Store research data generated via MCP (Perplexity/Firecrawl in Cursor).
    
    This endpoint accepts research data that was generated using MCPs directly in Cursor,
    avoiding Railway timeout issues and enabling interactive research workflows.
    
    Process:
    1. Accept structured research data from MCP
    2. Store lightweight summary in Firestore
    3. Return research ID for use in scoring/outreach
    """
    try:
        # Extract insights if not provided
        if not request.keywords or not request.job_titles:
            insights = extract_insights_from_research(request.summary, request.sources)
            keywords = request.keywords or insights.get("keywords", [])
            job_titles = request.job_titles or insights.get("job_titles", [])
            trending_pains = request.trending_pains or insights.get("trending_pains", [])
            industry_trends = request.industry_trends or insights.get("industry_trends", [])
        else:
            keywords = request.keywords
            job_titles = request.job_titles
            trending_pains = request.trending_pains or []
            industry_trends = request.industry_trends or []
        
        # Convert sources to ResearchSource objects
        research_sources = []
        for source in request.sources:
            if isinstance(source, dict):
                research_sources.append(ResearchSource(
                    url=source.get("url", ""),
                    title=source.get("title", "")
                ))
            else:
                research_sources.append(ResearchSource(url=str(source), title=""))
        
        # Build research insight document
        research_insight = ResearchInsight(
            title=request.title,
            industry=request.industry or request.title.split()[0] if request.title else "General",
            summary=request.summary[:500],  # Lightweight summary
            keywords=keywords[:10],  # Limit to top 10
            job_titles=job_titles[:10],
            sources=research_sources[:10],  # Limit to top 10 sources
            created_at=time.time(),
            updated_at=time.time(),
        )
        
        # Store in Firestore
        research_id = f"research_{int(time.time())}"
        research_doc = {
            "research_id": research_id,
            "title": research_insight.title,
            "industry": research_insight.industry,
            "summary": research_insight.summary,
            "keywords": research_insight.keywords,
            "job_titles": research_insight.job_titles,
            "trending_pains": trending_pains[:10],
            "industry_trends": industry_trends[:10],
            "linked_research_ids": [],
            "sources": [{"url": s.url, "title": s.title} for s in research_insight.sources],
            "created_at": research_insight.created_at,
            "updated_at": research_insight.updated_at,
            "source": "mcp",  # Mark as MCP-generated
        }
        
        doc_ref = db.collection("users").document(request.user_id).collection("research_insights").document(research_id)
        doc_ref.set(research_doc)
        
        logger.info(f"Stored MCP research: {research_id} for user {request.user_id}")
        
        return ResearchTriggerResponse(
            success=True,
            research_id=research_id,
            status="success",
            summary=research_insight
        )
        
    except Exception as e:
        logger.exception(f"Error storing research: {e}")
        raise HTTPException(status_code=500, detail=f"Research storage failed: {str(e)}")



