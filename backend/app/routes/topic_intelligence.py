"""
Topic Intelligence Routes

Endpoints for the Topic Intelligence Pipeline:
- Run full pipeline for a theme
- Get available themes and their dorks
- Store MCP-generated topic intelligence
"""

import logging
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models.topic_intelligence import (
    IntelligenceTheme,
    THEME_DORKS,
    THEME_DISPLAY_NAMES,
    THEME_SOURCES,
    TopicIntelligenceRequest,
    TopicIntelligenceResponse,
    TopicIntelligenceResult,
    ProspectIntelligence,
    OutreachTemplate,
    ContentIdea,
    OpportunityInsight,
)
from app.services.topic_intelligence_service import get_topic_intelligence_service
from app.services.firestore_client import db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/themes")
async def get_themes() -> Dict[str, Any]:
    """
    Get all available intelligence themes with their display names and sources.
    """
    themes = []
    for theme in IntelligenceTheme:
        themes.append({
            "id": theme.value,
            "name": THEME_DISPLAY_NAMES.get(theme, theme.value),
            "dork_count": len(THEME_DORKS.get(theme, [])),
            "sources": THEME_SOURCES.get(theme, []),
        })
    
    return {
        "themes": themes,
        "total": len(themes)
    }


@router.get("/themes/{theme_id}/dorks")
async def get_theme_dorks(theme_id: str) -> Dict[str, Any]:
    """
    Get all Google dorks for a specific theme.
    """
    try:
        theme = IntelligenceTheme(theme_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Theme '{theme_id}' not found")
    
    dorks = THEME_DORKS.get(theme, [])
    
    return {
        "theme": theme_id,
        "theme_name": THEME_DISPLAY_NAMES.get(theme, theme_id),
        "dorks": dorks,
        "total": len(dorks)
    }


@router.post("/run", response_model=TopicIntelligenceResponse)
async def run_topic_intelligence(request: TopicIntelligenceRequest) -> Dict[str, Any]:
    """
    Run the full Topic Intelligence Pipeline for a theme.
    
    This endpoint:
    1. Gets Google dorks for the selected theme
    2. Researches using Perplexity
    3. Scrapes top URLs with Firecrawl
    4. Extracts prospect intelligence
    5. Generates outreach templates
    6. Generates content ideas
    7. Identifies market opportunities
    8. Stores everything in Firestore
    
    Note: This can take 30-60 seconds. For faster results, use the /store endpoint
    with MCP-generated data from Cursor.
    """
    try:
        service = get_topic_intelligence_service()
        result = await service.run_pipeline(request)
        
        return TopicIntelligenceResponse(
            success=True,
            research_id=result.research_id,
            status="success",
            result=result
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"API configuration error: {str(e)}. Ensure PERPLEXITY_API_KEY and FIRECRAWL_API_KEY are set."
        )
    except Exception as e:
        logger.exception(f"Error running topic intelligence: {e}")
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {str(e)}")


class TopicIntelligenceStoreRequest(BaseModel):
    """Request to store MCP-generated topic intelligence"""
    user_id: str = Field(..., description="User ID")
    theme: str = Field(..., description="Theme ID or custom theme name")
    summary: str = Field(..., description="Research summary")
    prospect_intelligence: Dict[str, Any] = Field(..., description="Prospect intelligence data")
    outreach_templates: List[Dict[str, Any]] = Field(default_factory=list)
    content_ideas: List[Dict[str, Any]] = Field(default_factory=list)
    opportunity_insights: List[Dict[str, Any]] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    trending_topics: List[str] = Field(default_factory=list)
    sources_scraped: int = Field(0, description="Number of sources scraped")


@router.post("/store", response_model=TopicIntelligenceResponse)
async def store_topic_intelligence(request: TopicIntelligenceStoreRequest) -> Dict[str, Any]:
    """
    Store topic intelligence data generated via MCP (Perplexity/Firecrawl in Cursor).
    
    This is the recommended approach for avoiding Railway timeout issues.
    Use MCPs in Cursor to run the research, then store the results here.
    """
    import time
    
    try:
        # Determine theme display name
        try:
            theme_enum = IntelligenceTheme(request.theme)
            theme_display = THEME_DISPLAY_NAMES.get(theme_enum, request.theme)
        except ValueError:
            theme_display = request.theme  # Custom theme
        
        research_id = f"topic_intel_{request.theme}_{int(time.time())}"
        
        # Build prospect intelligence
        pi_data = request.prospect_intelligence
        prospect_intel = ProspectIntelligence(
            target_personas=pi_data.get("target_personas", []),
            pain_points=pi_data.get("pain_points", []),
            language_patterns=pi_data.get("language_patterns", []),
            decision_triggers=pi_data.get("decision_triggers", []),
            objections=pi_data.get("objections", []),
        )
        
        # Build outreach templates
        outreach_templates = [
            OutreachTemplate(**t) for t in request.outreach_templates
        ]
        
        # Build content ideas
        content_ideas = [
            ContentIdea(**c) for c in request.content_ideas
        ]
        
        # Build opportunity insights
        opportunities = [
            OpportunityInsight(**o) for o in request.opportunity_insights
        ]
        
        # Create result
        result = TopicIntelligenceResult(
            theme=request.theme,
            theme_display=theme_display,
            research_id=research_id,
            sources_scraped=request.sources_scraped,
            summary=request.summary,
            prospect_intelligence=prospect_intel,
            outreach_templates=outreach_templates,
            content_ideas=content_ideas,
            opportunity_insights=opportunities,
            keywords=request.keywords,
            trending_topics=request.trending_topics,
        )
        
        # Store in Firestore
        doc_data = {
            "research_id": research_id,
            "theme": request.theme,
            "theme_display": theme_display,
            "sources_scraped": request.sources_scraped,
            "summary": request.summary,
            "prospect_intelligence": prospect_intel.dict(),
            "outreach_templates": [t.dict() for t in outreach_templates],
            "content_ideas": [c.dict() for c in content_ideas],
            "opportunity_insights": [o.dict() for o in opportunities],
            "keywords": request.keywords,
            "trending_topics": request.trending_topics,
            "created_at": time.time(),
            "source": "mcp",
        }
        
        doc_ref = db.collection("users").document(request.user_id).collection("topic_intelligence").document(research_id)
        doc_ref.set(doc_data)
        
        logger.info(f"Stored MCP topic intelligence: {research_id}")
        
        return TopicIntelligenceResponse(
            success=True,
            research_id=research_id,
            status="success",
            result=result
        )
        
    except Exception as e:
        logger.exception(f"Error storing topic intelligence: {e}")
        raise HTTPException(status_code=500, detail=f"Storage failed: {str(e)}")


@router.get("/user/{user_id}")
async def get_user_topic_intelligence(user_id: str, limit: int = 20) -> Dict[str, Any]:
    """
    Get all topic intelligence results for a user.
    """
    try:
        docs = db.collection("users").document(user_id).collection("topic_intelligence").order_by(
            "created_at", direction="DESCENDING"
        ).limit(limit).stream()
        
        results = []
        for doc in docs:
            data = doc.to_dict()
            results.append(data)
        
        return {
            "user_id": user_id,
            "results": results,
            "total": len(results)
        }
        
    except Exception as e:
        logger.exception(f"Error fetching topic intelligence: {e}")
        raise HTTPException(status_code=500, detail=f"Fetch failed: {str(e)}")


@router.get("/user/{user_id}/{research_id}")
async def get_topic_intelligence_by_id(user_id: str, research_id: str) -> Dict[str, Any]:
    """
    Get a specific topic intelligence result by ID.
    """
    try:
        doc_ref = db.collection("users").document(user_id).collection("topic_intelligence").document(research_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail=f"Research '{research_id}' not found")
        
        return doc.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error fetching topic intelligence: {e}")
        raise HTTPException(status_code=500, detail=f"Fetch failed: {str(e)}")


@router.get("/user/{user_id}/dork-stats/{theme_id}")
async def get_dork_performance_stats(user_id: str, theme_id: str) -> Dict[str, Any]:
    """
    Get aggregated dork performance stats for a theme.
    Shows which dorks performed best across all runs.
    """
    try:
        # Get all results for this theme
        docs = db.collection("users").document(user_id).collection("topic_intelligence").where(
            "theme", "==", theme_id
        ).stream()
        
        # Aggregate dork performance
        dork_stats: Dict[int, Dict[str, Any]] = {}
        
        for doc in docs:
            data = doc.to_dict()
            dork_perf = data.get("dork_performance", [])
            
            for perf in dork_perf:
                idx = perf.get("dork_index", -1)
                if idx not in dork_stats:
                    dork_stats[idx] = {
                        "dork_index": idx,
                        "dork": perf.get("dork", ""),
                        "total_runs": 0,
                        "total_sources": 0,
                        "avg_sources": 0,
                        "total_summary_length": 0,
                        "errors": 0,
                    }
                
                dork_stats[idx]["total_runs"] += 1
                dork_stats[idx]["total_sources"] += perf.get("sources_found", 0)
                dork_stats[idx]["total_summary_length"] += perf.get("summary_length", 0)
                if perf.get("error"):
                    dork_stats[idx]["errors"] += 1
        
        # Calculate averages and sort by performance
        results = []
        for idx, stats in dork_stats.items():
            if stats["total_runs"] > 0:
                stats["avg_sources"] = round(stats["total_sources"] / stats["total_runs"], 1)
                stats["avg_summary_length"] = round(stats["total_summary_length"] / stats["total_runs"], 0)
            results.append(stats)
        
        # Sort by avg_sources (best performing first)
        results.sort(key=lambda x: x["avg_sources"], reverse=True)
        
        return {
            "theme": theme_id,
            "total_runs": sum(s["total_runs"] for s in results) // 3 if results else 0,  # Divide by 3 dorks per run
            "dork_rankings": results,
            "best_dork": results[0] if results else None,
        }
        
    except Exception as e:
        logger.exception(f"Error fetching dork stats: {e}")
        raise HTTPException(status_code=500, detail=f"Fetch failed: {str(e)}")

