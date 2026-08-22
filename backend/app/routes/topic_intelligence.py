"""
Topic Intelligence Routes

Endpoints for the Topic Intelligence Pipeline:
- Run full pipeline for a theme
- Get available themes and their dorks
- Store MCP-generated topic intelligence
"""

import logging
import hashlib
import os
import re
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Query, Response, status
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
from app.services.firestore_client import get_firestore_client

logger = logging.getLogger(__name__)
router = APIRouter()

_SAFE_FIRESTORE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{0,127}$")


def _configured_owner_user_id() -> str:
    user_id = str(os.getenv("DEFAULT_USER_ID") or "default-user").strip()
    if not _SAFE_FIRESTORE_ID.fullmatch(user_id):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "state": "degraded",
                "reason_codes": ["owner_authority_misconfigured"],
                "message": "Topic-intelligence owner authority is not configured safely.",
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


def _bounded_text(value: Any, limit: int) -> str:
    return str(value or "")[:limit]


def _bounded_nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _bounded_strings(value: Any, *, count: int = 100, length: int = 1_000) -> List[str]:
    if not isinstance(value, list):
        return []
    return [_bounded_text(item, length) for item in value[:count]]


def _bounded_records(value: Any, allowed_fields: Dict[str, int], *, count: int = 50) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    records: List[Dict[str, Any]] = []
    for raw in value[:count]:
        if not isinstance(raw, dict):
            continue
        record: Dict[str, Any] = {}
        for key, limit in allowed_fields.items():
            item = raw.get(key)
            if isinstance(item, list):
                record[key] = _bounded_strings(item, count=50, length=limit)
            elif item is not None:
                record[key] = _bounded_text(item, limit)
        records.append(record)
    return records


def _bounded_topic_projection(data: Dict[str, Any]) -> Dict[str, Any]:
    prospect = data.get("prospect_intelligence") if isinstance(data.get("prospect_intelligence"), dict) else {}
    return {
        "research_id": _bounded_text(data.get("research_id"), 300),
        "theme": _bounded_text(data.get("theme"), 300),
        "theme_display": _bounded_text(data.get("theme_display"), 500),
        "sources_scraped": _bounded_nonnegative_int(data.get("sources_scraped")),
        "summary": _bounded_text(data.get("summary"), 20_000),
        "prospect_intelligence": {
            key: _bounded_strings(prospect.get(key), count=100, length=1_000)
            for key in ("target_personas", "pain_points", "language_patterns", "decision_triggers", "objections")
        },
        "outreach_templates": _bounded_records(
            data.get("outreach_templates"),
            {"type": 100, "channel": 100, "subject": 500, "hook": 1_000, "body": 10_000, "personalization_hooks": 1_000},
        ),
        "content_ideas": _bounded_records(
            data.get("content_ideas"),
            {"format": 100, "platform": 100, "headline": 1_000, "title": 1_000, "description": 5_000, "outline": 1_000, "cta": 2_000},
        ),
        "opportunity_insights": _bounded_records(
            data.get("opportunity_insights"),
            {"gap": 2_000, "opportunity": 2_000, "description": 5_000, "evidence": 2_000, "action": 5_000},
        ),
        "keywords": _bounded_strings(data.get("keywords"), count=100, length=300),
        "trending_topics": _bounded_strings(data.get("trending_topics"), count=100, length=500),
        "created_at": data.get("created_at"),
        "source": _bounded_text(data.get("source"), 100),
    }


def _set_firestore_headers(response: Response, state: str, reason_codes: List[str] | None = None) -> None:
    response.headers["X-AI-Clone-Firestore-State"] = state
    response.headers["X-AI-Clone-Data-Source"] = "firestore:users/*/topic_intelligence" if state == "ready" else "unavailable"
    if reason_codes:
        response.headers["X-AI-Clone-Degraded-Reasons"] = ",".join(reason_codes)
    response.headers["Cache-Control"] = "no-store, max-age=0"


def _firestore_unavailable_detail(reason_code: str) -> Dict[str, Any]:
    return {
        "state": "degraded",
        "reason_codes": [reason_code],
        "message": "Topic intelligence storage is temporarily unavailable.",
    }


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
        owner_user_id = _owner_user_id(request.user_id)
        service = get_topic_intelligence_service()
        result = await service.run_pipeline(request.model_copy(update={"user_id": owner_user_id}))
        
        return TopicIntelligenceResponse(
            success=True,
            research_id=result.research_id,
            status="success",
            result=result
        )
    
    except HTTPException:
        raise
    except ValueError as exc:
        logger.warning("Topic-intelligence configuration failed [%s]", type(exc).__name__)
        raise HTTPException(
            status_code=400,
            detail="Topic-intelligence connectors are not configured.",
        ) from exc
    except Exception as exc:
        logger.warning("Topic-intelligence pipeline failed [%s]", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_firestore_unavailable_detail("topic_intelligence_pipeline_failed"),
        ) from exc


class TopicIntelligenceStoreRequest(BaseModel):
    """Request to store MCP-generated topic intelligence"""
    user_id: str | None = Field(
        None,
        description="Compatibility owner ID; the API enforces DEFAULT_USER_ID",
    )
    theme: str = Field(..., min_length=1, max_length=300, description="Theme ID or custom theme name")
    summary: str = Field(..., max_length=20_000, description="Research summary")
    prospect_intelligence: Dict[str, Any] = Field(..., description="Prospect intelligence data")
    outreach_templates: List[Dict[str, Any]] = Field(default_factory=list, max_length=50)
    content_ideas: List[Dict[str, Any]] = Field(default_factory=list, max_length=50)
    opportunity_insights: List[Dict[str, Any]] = Field(default_factory=list, max_length=50)
    keywords: List[str] = Field(default_factory=list, max_length=100)
    trending_topics: List[str] = Field(default_factory=list, max_length=100)
    sources_scraped: int = Field(0, ge=0, le=10_000, description="Number of sources scraped")


@router.post("/store", response_model=TopicIntelligenceResponse)
async def store_topic_intelligence(request: TopicIntelligenceStoreRequest, response: Response) -> Dict[str, Any]:
    """
    Store topic intelligence data generated via MCP (Perplexity/Firecrawl in Cursor).
    
    This is the recommended approach for avoiding Railway timeout issues.
    Use MCPs in Cursor to run the research, then store the results here.
    """
    import time
    
    owner_user_id = _owner_user_id(request.user_id)
    client = get_firestore_client()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_firestore_unavailable_detail("firestore_unavailable"),
        )
    try:
        # Determine theme display name
        try:
            theme_enum = IntelligenceTheme(request.theme)
            theme_display = THEME_DISPLAY_NAMES.get(theme_enum, request.theme)
        except ValueError:
            theme_display = request.theme  # Custom theme
        
        theme_key = re.sub(r"[^A-Za-z0-9_-]+", "-", request.theme).strip("-")[:40] or "custom"
        theme_digest = hashlib.sha256(request.theme.encode("utf-8")).hexdigest()[:10]
        research_id = f"topic_intel_{theme_key}_{theme_digest}_{int(time.time())}"
        
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
        
        doc_ref = client.collection("users").document(owner_user_id).collection("topic_intelligence").document(research_id)
        doc_ref.set(doc_data)
        
        logger.info("Stored owner topic-intelligence result")
        
        _set_firestore_headers(response, "ready")
        return TopicIntelligenceResponse(
            success=True,
            research_id=research_id,
            status="success",
            result=result
        )
        
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Topic intelligence write failed [%s]", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_firestore_unavailable_detail("firestore_write_failed"),
        ) from exc


@router.get("/user/{user_id}")
async def get_user_topic_intelligence(
    user_id: str,
    response: Response,
    limit: int = Query(default=20, ge=1, le=100),
) -> Dict[str, Any]:
    """
    Get all topic intelligence results for a user.
    """
    user_id = _owner_user_id(user_id)
    client = get_firestore_client()
    if client is None:
        _set_firestore_headers(response, "degraded", ["firestore_unavailable"])
        return {
            "state": "degraded",
            "reason_codes": ["firestore_unavailable"],
            "user_id": user_id,
            "results": [],
            "total": 0,
        }
    try:
        docs = client.collection("users").document(user_id).collection("topic_intelligence").order_by(
            "created_at", direction="DESCENDING"
        ).limit(limit).stream()
        
        results = []
        for doc in docs:
            data = doc.to_dict() or {}
            data.setdefault("research_id", doc.id)
            results.append(_bounded_topic_projection(data))
        
        _set_firestore_headers(response, "ready")
        return {
            "state": "ready",
            "user_id": user_id,
            "results": results,
            "total": len(results)
        }
        
    except Exception as exc:
        logger.warning("Topic intelligence list read failed [%s]", type(exc).__name__)
        _set_firestore_headers(response, "degraded", ["firestore_read_failed"])
        return {
            "state": "degraded",
            "reason_codes": ["firestore_read_failed"],
            "user_id": user_id,
            "results": [],
            "total": 0,
        }


@router.get("/user/{user_id}/{research_id}")
async def get_topic_intelligence_by_id(user_id: str, research_id: str, response: Response) -> Dict[str, Any]:
    """
    Get a specific topic intelligence result by ID.
    """
    user_id = _owner_user_id(user_id)
    client = get_firestore_client()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_firestore_unavailable_detail("firestore_unavailable"),
        )
    try:
        doc_ref = client.collection("users").document(user_id).collection("topic_intelligence").document(research_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail=f"Research '{research_id}' not found")
        
        _set_firestore_headers(response, "ready")
        data = doc.to_dict() or {}
        data.setdefault("research_id", doc.id)
        return _bounded_topic_projection(data)
        
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Topic intelligence detail read failed [%s]", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_firestore_unavailable_detail("firestore_read_failed"),
        ) from exc


@router.get("/user/{user_id}/dork-stats/{theme_id}")
async def get_dork_performance_stats(user_id: str, theme_id: str, response: Response) -> Dict[str, Any]:
    """
    Get aggregated dork performance stats for a theme.
    Shows which dorks performed best across all runs.
    """
    user_id = _owner_user_id(user_id)
    client = get_firestore_client()
    if client is None:
        _set_firestore_headers(response, "degraded", ["firestore_unavailable"])
        return {
            "state": "degraded",
            "reason_codes": ["firestore_unavailable"],
            "theme": theme_id,
            "total_runs": 0,
            "dork_rankings": [],
            "best_dork": None,
        }
    try:
        # Get all results for this theme
        docs = client.collection("users").document(user_id).collection("topic_intelligence").where(
            "theme", "==", theme_id
        ).stream()
        
        # Aggregate dork performance
        dork_stats: Dict[int, Dict[str, Any]] = {}
        
        for doc in docs:
            data = doc.to_dict() or {}
            dork_perf = data.get("dork_performance", [])
            if not isinstance(dork_perf, list):
                continue
            
            for perf in dork_perf[:100]:
                if not isinstance(perf, dict):
                    continue
                try:
                    idx = int(perf.get("dork_index", -1))
                except (TypeError, ValueError):
                    continue
                if idx < 0 or idx > 10_000:
                    continue
                if idx not in dork_stats:
                    dork_stats[idx] = {
                        "dork_index": idx,
                        "dork": _bounded_text(perf.get("dork"), 1_000),
                        "total_runs": 0,
                        "total_sources": 0,
                        "avg_sources": 0,
                        "total_summary_length": 0,
                        "errors": 0,
                    }
                
                dork_stats[idx]["total_runs"] += 1
                dork_stats[idx]["total_sources"] += _bounded_nonnegative_int(perf.get("sources_found"))
                dork_stats[idx]["total_summary_length"] += _bounded_nonnegative_int(perf.get("summary_length"))
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
        
        _set_firestore_headers(response, "ready")
        return {
            "state": "ready",
            "theme": theme_id,
            "total_runs": sum(s["total_runs"] for s in results) // 3 if results else 0,  # Divide by 3 dorks per run
            "dork_rankings": results,
            "best_dork": results[0] if results else None,
        }
        
    except Exception as exc:
        logger.warning("Topic intelligence statistics read failed [%s]", type(exc).__name__)
        _set_firestore_headers(response, "degraded", ["firestore_read_failed"])
        return {
            "state": "degraded",
            "reason_codes": ["firestore_read_failed"],
            "theme": theme_id,
            "total_runs": 0,
            "dork_rankings": [],
            "best_dork": None,
        }
