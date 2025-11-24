"""
Enhanced Research & Knowledge Management Routes

Multi-source research pipeline implementing:
- Step A: Topic Trigger
- Step B: Multi-source Research (Perplexity, Firecrawl, Google Search)
- Step C: Normalization & Deduplication
- Step D: Prospect Target Extraction
- Step E: Storage in Firestore
- Step F: Integration with content generation & outreach
"""

import logging
import time
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException

from app.models.enhanced_research import (
    TopicTriggerRequest,
    TopicTriggerResponse,
    MultiSourceResearchRequest,
    MultiSourceResearchResponse,
    NormalizeInsightRequest,
    NormalizeInsightResponse,
    ProspectExtractionRequest,
    ProspectExtractionResponse,
    EnhancedResearchInsight,
    InsightStatus,
)
from app.services.enhanced_research_service import (
    assign_pillar_to_topic,
    collect_perplexity_source,
    collect_firecrawl_source,
    collect_google_search_sources,
    extract_prospect_targets,
    normalize_insight,
    calculate_engagement_signals,
    save_insight_to_firestore,
    load_insight_from_firestore,
)
from app.services.firestore_client import db
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/trigger", response_model=TopicTriggerResponse)
async def trigger_topic_research(request: TopicTriggerRequest) -> Dict[str, Any]:
    """
    Step A: Topic Trigger
    
    Input: user-defined topic or system-suggested trending topic
    Output: topic_id with initial metadata and pillar assignment
    """
    try:
        logger.info(f"🔍 Topic trigger: user={request.user_id}, topic='{request.topic}'")
        
        # Check for cached insights (if use_cached enabled)
        if request.use_cached:
            # Check if similar topic exists
            collection = db.collection("users").document(request.user_id).collection("research_insights")
            query = collection.where("topic", "==", request.topic).order_by("date_collected", direction="DESCENDING").limit(1)
            docs = query.get()
            
            if docs:
                existing = docs[0].to_dict()
                logger.info(f"  → Found cached insight: {existing.get('insight_id')}")
                return TopicTriggerResponse(
                    success=True,
                    topic_id=existing.get("topic", request.topic),
                    insight_id=existing.get("insight_id", ""),
                    status="cached",
                    pillar_assigned=existing.get("pillar"),
                )
        
        # Assign pillar if not provided
        pillar = request.pillar or assign_pillar_to_topic(request.topic, request.industry)
        logger.info(f"  → Assigned pillar: {pillar}")
        
        # Create initial insight object
        insight_id = f"insight_{int(time.time())}"
        insight = EnhancedResearchInsight(
            user_id=request.user_id,
            insight_id=insight_id,
            topic=request.topic,
            pillar=pillar,
            date_collected=datetime.now(timezone.utc).isoformat(),
            status=InsightStatus.COLLECTING,
        )
        
        # Save initial insight
        save_insight_to_firestore(insight)
        
        # Estimated completion: ~30-60 seconds for multi-source research
        estimated_time = 45
        
        return TopicTriggerResponse(
            success=True,
            topic_id=request.topic,
            insight_id=insight_id,
            status="collecting",
            pillar_assigned=pillar,
            estimated_completion_time=estimated_time,
        )
        
    except Exception as e:
        logger.exception(f"Error triggering topic research: {e}")
        raise HTTPException(status_code=500, detail=f"Topic trigger failed: {str(e)}")


@router.post("/collect", response_model=MultiSourceResearchResponse)
async def collect_multi_source_research(request: MultiSourceResearchRequest) -> Dict[str, Any]:
    """
    Step B: Multi-source Research
    
    Query Perplexity → get structured summaries and key points
    Query Firecrawl → scrape relevant blogs/news pages
    Query Google Custom Search → find case studies, startups, reports
    Merge all results into a single insight object
    """
    try:
        logger.info(f"📚 Multi-source research: insight_id={request.insight_id}")
        
        # Load existing insight
        insight = load_insight_from_firestore(request.user_id, request.insight_id)
        if not insight:
            raise HTTPException(status_code=404, detail="Insight not found")
        
        insight.status = InsightStatus.PROCESSING
        save_insight_to_firestore(insight)
        
        sources_collected = []
        sources_by_type = {}
        
        # 1. Collect from Perplexity
        if request.use_perplexity:
            logger.info("  → Collecting from Perplexity...")
            perplexity_source = await collect_perplexity_source(request.topic)
            if perplexity_source:
                sources_collected.append(perplexity_source)
                sources_by_type["perplexity"] = 1
                logger.info("  ✅ Perplexity source collected")
            
            # Add delay for free-tier rate limiting
            if request.batch_mode:
                import asyncio
                await asyncio.sleep(1)
        
        # 2. Collect from Google Custom Search
        if request.use_google_search:
            logger.info("  → Collecting from Google Custom Search...")
            google_sources = await collect_google_search_sources(request.topic, request.max_sources_per_type)
            sources_collected.extend(google_sources)
            sources_by_type["google_custom_search"] = len(google_sources)
            logger.info(f"  ✅ Collected {len(google_sources)} Google sources")
        
        # 3. Collect from Firecrawl (use top URLs from other sources)
        if request.use_firecrawl and sources_collected:
            logger.info("  → Collecting from Firecrawl...")
            firecrawl_sources = []
            
            # Use URLs from Perplexity and Google sources
            urls_to_scrape = []
            for source in sources_collected[:request.max_sources_per_type]:
                if source.source_url and source.source_url.startswith("http"):
                    urls_to_scrape.append(source.source_url)
            
            for url in urls_to_scrape[:request.max_sources_per_type]:
                firecrawl_source = await collect_firecrawl_source(url, request.topic)
                if firecrawl_source:
                    firecrawl_sources.append(firecrawl_source)
                
                # Rate limiting for free-tier
                if request.batch_mode:
                    import asyncio
                    await asyncio.sleep(2)  # 2-second delay between Firecrawl requests
            
            sources_collected.extend(firecrawl_sources)
            sources_by_type["firecrawl"] = len(firecrawl_sources)
            logger.info(f"  ✅ Collected {len(firecrawl_sources)} Firecrawl sources")
        
        # Update insight with collected sources
        insight.sources = sources_collected
        
        # Extract prospect targets if enabled
        prospect_targets = []
        if sources_collected:
            prospect_targets = extract_prospect_targets(sources_collected, request.topic, insight.pillar or "thought_leadership")
            insight.prospect_targets = prospect_targets
            logger.info(f"  → Extracted {len(prospect_targets)} prospect targets")
        
        # Calculate engagement signals
        insight.engagement_signals = calculate_engagement_signals(
            sources_collected,
            prospect_targets,
            request.topic,
        )
        
        # Extract tags from sources
        tags = set()
        for source in sources_collected:
            # Extract tags from summary and key points
            text = f"{source.summary} {' '.join(source.key_points)}"
            # Simple keyword extraction (in production, use better NLP)
            keywords = ["AI", "EdTech", "Education", "School", "Technology", "Innovation"]
            for keyword in keywords:
                if keyword.lower() in text.lower():
                    tags.add(keyword)
        insight.tags = list(tags)
        
        # Save updated insight
        save_insight_to_firestore(insight)
        
        logger.info(f"✅ Collected {len(sources_collected)} total sources")
        
        return MultiSourceResearchResponse(
            success=True,
            insight_id=request.insight_id,
            sources_collected=len(sources_collected),
            sources_by_type=sources_by_type,
            prospect_targets_extracted=len(prospect_targets),
            status="processing",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error collecting multi-source research: {e}")
        raise HTTPException(status_code=500, detail=f"Multi-source research failed: {str(e)}")


@router.post("/normalize", response_model=NormalizeInsightResponse)
async def normalize_insight_endpoint(request: NormalizeInsightRequest) -> Dict[str, Any]:
    """
    Step C: Normalization
    
    Deduplicate key points across sources
    Assign pillar tags
    Generate tags for future filtering/content targeting
    """
    try:
        logger.info(f"🔧 Normalizing insight: {request.insight_id}")
        
        # Load insight
        insight = load_insight_from_firestore(request.user_id, request.insight_id)
        if not insight:
            raise HTTPException(status_code=404, detail="Insight not found")
        
        # Normalize
        original_key_points_count = len([kp for source in insight.sources for kp in source.key_points])
        normalized_insight = normalize_insight(insight)
        
        deduplicated_count = original_key_points_count - len(normalized_insight.normalized_key_points)
        
        # Save normalized insight
        normalized_insight.status = InsightStatus.READY_FOR_CONTENT_GENERATION
        save_insight_to_firestore(normalized_insight)
        
        logger.info(f"  ✅ Deduplicated {deduplicated_count} key points, normalized {len(normalized_insight.normalized_tags)} tags")
        
        return NormalizeInsightResponse(
            success=True,
            insight_id=request.insight_id,
            deduplicated_key_points=deduplicated_count,
            normalized_tags=len(normalized_insight.normalized_tags),
            merged_sources=0,  # Not implemented yet
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error normalizing insight: {e}")
        raise HTTPException(status_code=500, detail=f"Normalization failed: {str(e)}")


@router.post("/extract-prospects", response_model=ProspectExtractionResponse)
async def extract_prospect_targets_endpoint(request: ProspectExtractionRequest) -> Dict[str, Any]:
    """
    Step D: Prospect Target Extraction
    
    Identify organizations, leaders, or publications mentioned in research
    Build prospect_targets array with roles, URLs, and pillar relevance
    """
    try:
        logger.info(f"👥 Extracting prospects: {request.insight_id}")
        
        # Load insight
        insight = load_insight_from_firestore(request.user_id, request.insight_id)
        if not insight:
            raise HTTPException(status_code=404, detail="Insight not found")
        
        # Extract prospects
        prospect_targets = extract_prospect_targets(
            insight.sources,
            insight.topic,
            insight.pillar or "thought_leadership",
        )
        
        # Filter by relevance score
        filtered_prospects = [
            p for p in prospect_targets
            if p.relevance_score and p.relevance_score >= request.min_relevance_score
        ]
        
        # Update insight
        insight.prospect_targets = filtered_prospects
        save_insight_to_firestore(insight)
        
        logger.info(f"  ✅ Extracted {len(filtered_prospects)} prospects (min score: {request.min_relevance_score})")
        
        return ProspectExtractionResponse(
            success=True,
            insight_id=request.insight_id,
            prospects_extracted=len(filtered_prospects),
            prospects=filtered_prospects,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error extracting prospects: {e}")
        raise HTTPException(status_code=500, detail=f"Prospect extraction failed: {str(e)}")


@router.post("/complete-workflow")
async def complete_research_workflow(
    user_id: str,
    topic: str,
    industry: Optional[str] = None,
    use_cached: bool = True,
) -> Dict[str, Any]:
    """
    Complete workflow: Steps A-F in one call
    
    This is the main endpoint that orchestrates the entire research pipeline.
    """
    try:
        logger.info(f"🚀 Complete research workflow: topic='{topic}'")
        
        # Step A: Topic Trigger
        trigger_response = await trigger_topic_research(TopicTriggerRequest(
            user_id=user_id,
            topic=topic,
            industry=industry,
            use_cached=use_cached,
        ))
        
        insight_id = trigger_response.insight_id
        
        # Step B: Multi-source Research
        research_response = await collect_multi_source_research(MultiSourceResearchRequest(
            user_id=user_id,
            insight_id=insight_id,
            topic=topic,
            use_perplexity=True,
            use_firecrawl=True,
            use_google_search=True,
            batch_mode=True,  # Free-tier optimization
        ))
        
        # Step C: Normalize
        normalize_response = await normalize_insight_endpoint(NormalizeInsightRequest(
            user_id=user_id,
            insight_id=insight_id,
        ))
        
        # Step D: Extract Prospects
        prospects_response = await extract_prospect_targets_endpoint(ProspectExtractionRequest(
            user_id=user_id,
            insight_id=insight_id,
            min_relevance_score=0.7,
        ))
        
        # Load final insight
        final_insight = load_insight_from_firestore(user_id, insight_id)
        
        logger.info(f"✅ Complete workflow finished: {insight_id}")
        
        return {
            "success": True,
            "insight_id": insight_id,
            "topic": topic,
            "pillar": trigger_response.pillar_assigned,
            "sources_collected": research_response.sources_collected,
            "prospects_extracted": prospects_response.prospects_extracted,
            "normalized_key_points": len(final_insight.normalized_key_points) if final_insight else 0,
            "status": "ready_for_content_generation",
            "workflow_steps_completed": [
                "topic_trigger",
                "multi_source_research",
                "normalization",
                "prospect_extraction",
            ],
        }
        
    except Exception as e:
        logger.exception(f"Error in complete workflow: {e}")
        raise HTTPException(status_code=500, detail=f"Complete workflow failed: {str(e)}")


@router.get("/insight/{insight_id}")
async def get_insight(
    user_id: str,
    insight_id: str,
) -> Dict[str, Any]:
    """Get insight object by ID."""
    try:
        insight = load_insight_from_firestore(user_id, insight_id)
        if not insight:
            raise HTTPException(status_code=404, detail="Insight not found")
        
        return {
            "success": True,
            "insight": insight.model_dump(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting insight: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get insight: {str(e)}")


@router.post("/auto-discover")
async def auto_discover_insights(
    user_id: str,
    pillar: Optional[str] = None,
    topic: Optional[str] = None,
    audiences: Optional[List[str]] = None,
    limit: int = 5,
) -> Dict[str, Any]:
    """
    Auto-discover insights ready for content generation or prospecting.
    
    Finds insights by audience + pillar - makes them immediately usable.
    """
    try:
        from app.services.rmk_automation import discover_insights_for_content
        
        insights = discover_insights_for_content(
            user_id=user_id,
            pillar=pillar,
            topic=topic,
            audiences=audiences,
            limit=limit,
        )
        
        return {
            "success": True,
            "insights_found": len(insights),
            "insight_ids": [insight.insight_id for insight in insights if insight.insight_id],
            "insights": [insight.model_dump() for insight in insights],
        }
    except Exception as e:
        logger.exception(f"Error auto-discovering insights: {e}")
        raise HTTPException(status_code=500, detail=f"Auto-discovery failed: {str(e)}")


@router.post("/schedule-topics")
async def schedule_research_topics(
    user_id: str,
    topics: List[str],
    frequency: str = "weekly",
    pillar: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Schedule automated research for topics.
    
    Creates scheduled topics that can be run automatically (weekly/monthly).
    """
    try:
        from app.services.rmk_automation import (
            ScheduledResearchTopic,
            AutomatedResearchConfig,
            save_automated_config,
            load_automated_config,
        )
        
        # Load existing config or create new
        config = load_automated_config(user_id) or AutomatedResearchConfig(user_id=user_id)
        
        # Add scheduled topics
        for topic in topics:
            scheduled_topic = ScheduledResearchTopic(
                topic=topic,
                pillar=pillar,
                frequency=frequency,
                enabled=True,
            )
            config.scheduled_topics.append(scheduled_topic)
        
        # Save config
        save_automated_config(user_id, config)
        
        logger.info(f"Scheduled {len(topics)} topics for user {user_id}, frequency={frequency}")
        
        return {
            "success": True,
            "topics_scheduled": len(topics),
            "frequency": frequency,
            "total_scheduled_topics": len(config.scheduled_topics),
        }
        
    except Exception as e:
        logger.exception(f"Error scheduling topics: {e}")
        raise HTTPException(status_code=500, detail=f"Scheduling failed: {str(e)}")


@router.post("/run-scheduled")
async def run_scheduled_research(
    user_id: str,
    frequency: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run scheduled research topics.
    
    This can be called via cron job or manually.
    Runs all enabled scheduled topics for the specified frequency.
    """
    try:
        from app.services.rmk_automation import load_automated_config
        
        config = load_automated_config(user_id)
        if not config or not config.auto_run_enabled:
            return {
                "success": False,
                "message": "Automated research not configured or disabled",
            }
        
        # Filter topics by frequency
        topics_to_run = [
            topic for topic in config.scheduled_topics
            if topic.enabled and (not frequency or topic.frequency == frequency)
        ]
        
        if not topics_to_run:
            return {
                "success": True,
                "topics_processed": 0,
                "message": "No scheduled topics to run",
            }
        
        # Run research for each topic
        insight_ids = []
        for scheduled_topic in topics_to_run:
            try:
                # Trigger research workflow
                trigger_response = await trigger_topic_research(TopicTriggerRequest(
                    user_id=user_id,
                    topic=scheduled_topic.topic,
                    industry=scheduled_topic.industry or config.default_industry,
                    use_cached=True,
                ))
                
                insight_id = trigger_response.insight_id
                
                # Collect research
                await collect_multi_source_research(MultiSourceResearchRequest(
                    user_id=user_id,
                    insight_id=insight_id,
                    topic=scheduled_topic.topic,
                    batch_mode=True,
                ))
                
                # Normalize
                await normalize_insight_endpoint(NormalizeInsightRequest(
                    user_id=user_id,
                    insight_id=insight_id,
                ))
                
                insight_ids.append(insight_id)
                logger.info(f"Processed scheduled topic: {scheduled_topic.topic} → {insight_id}")
                
            except Exception as e:
                logger.warning(f"Failed to process scheduled topic {scheduled_topic.topic}: {e}")
                continue
        
        return {
            "success": True,
            "topics_processed": len(insight_ids),
            "insight_ids": insight_ids,
            "frequency": frequency or "all",
        }
        
    except Exception as e:
        logger.exception(f"Error running scheduled research: {e}")
        raise HTTPException(status_code=500, detail=f"Scheduled research failed: {str(e)}")

