"""
LinkedIn Content Routes - PACER Strategy Integration

Endpoints for:
- Content drafting (using research + LinkedIn insights)
- Content calendar/scheduling
- Outreach generation (DMs, connection requests)
- Engagement metrics tracking
"""

import logging
import time
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.firestore_client import db
from app.services.perplexity_client import get_perplexity_client
from app.services.linkedin_client import get_linkedin_client
from app.models.linkedin_content import (
    ContentDraft,
    ContentDraftRequest,
    ContentDraftResponse,
    ContentCalendarEntry,
    ContentCalendarRequest,
    EngagementMetrics,
    EngagementMetricsUpdate,
    OutreachRequest,
    OutreachResponse,
    StoreDraftRequest,
    StoreDraftResponse,
    GenerateDailyPacerRequest,
    GenerateDailyPacerResponse,
    GenerateWeeklyPacerRequest,
    GenerateWeeklyPacerResponse,
    DraftSummary,
    EngagementDMRequest,
    EngagementDMResponse,
    WeeklySummaryRequest,
    WeeklySummaryResponse,
    ContentPillar,
    ContentStatus,
)
from app.services.content_topic_library import select_topic_for_generation, get_topics_for_pillar
from app.services.content_post_templates import get_template_for_pillar

logger = logging.getLogger(__name__)
router = APIRouter()


def get_research_insights(user_id: str, research_ids: List[str]) -> List[Dict[str, Any]]:
    """Fetch research insights from Firestore."""
    insights = []
    for research_id in research_ids:
        try:
            doc_ref = db.collection("users").document(user_id).collection("research_insights").document(research_id)
            doc = doc_ref.get()
            if doc.exists:
                insights.append(doc.to_dict())
        except Exception as e:
            logger.warning(f"Error fetching research {research_id}: {e}")
    return insights


def get_linkedin_post_insights(post_ids: List[str]) -> List[Dict[str, Any]]:
    """Fetch LinkedIn post insights (for now, return IDs - would need post storage)."""
    # In production, would fetch from stored posts
    return [{"post_id": pid} for pid in post_ids]


@router.post("/drafts/generate", response_model=ContentDraftResponse)
async def generate_content_drafts(request: ContentDraftRequest) -> Dict[str, Any]:
    """
    Generate LinkedIn content drafts based on:
    - Content pillar (referral, thought_leadership, stealth_founder)
    - Research insights
    - High-performing LinkedIn posts
    - PACER strategy guidelines
    """
    try:
        # Step 1: Gather context from research insights
        research_insights = []
        if request.linked_research_ids:
            research_insights = get_research_insights(request.user_id, request.linked_research_ids)
        
        # Step 2: Get LinkedIn post inspiration if needed
        linkedin_posts = []
        if not request.linked_research_ids:
            # Auto-search for high-performing posts in target niches
            linkedin_client = get_linkedin_client()
            
            pillar_queries = {
                ContentPillar.REFERRAL: "private school admin mental health treatment center education",
                ContentPillar.THOUGHT_LEADERSHIP: "EdTech business leader AI education technology",
                ContentPillar.STEALTH_FOUNDER: "stealth startup founder early adopter investor",
                ContentPillar.MIXED: "EdTech AI education technology startup",
            }
            
            query = pillar_queries.get(request.pillar, "EdTech AI education")
            posts_result = linkedin_client.search_posts(
                query=query,
                max_results=5,
                sort_by="engagement",
                min_engagement_score=10.0,
            )
            linkedin_posts = posts_result[:5]  # Top 5 posts
        
        # Step 3: Build generation prompt
        prompt_parts = [
            f"Generate {request.num_drafts} LinkedIn post draft variants for a PACER content strategy.",
            f"\nContent Pillar: {request.pillar.value}",
        ]
        
        if request.topic:
            prompt_parts.append(f"Topic: {request.topic}")
        
        if request.pillar == ContentPillar.REFERRAL:
            prompt_parts.append("\nTarget Audience: Private school administrators, mental health professionals, treatment centers")
            prompt_parts.append("Goal: Build referral network, share insights about educational support services")
        elif request.pillar == ContentPillar.THOUGHT_LEADERSHIP:
            prompt_parts.append("\nTarget Audience: EdTech business leaders, AI-savvy executives")
            prompt_parts.append("Goal: Establish thought leadership, share industry insights")
        elif request.pillar == ContentPillar.STEALTH_FOUNDER:
            prompt_parts.append("\nTarget Audience: Early adopters, investors, stealth founders")
            prompt_parts.append("Goal: Connect with like-minded entrepreneurs (use sparingly - 5-10% of content)")
        
        if research_insights:
            prompt_parts.append("\nResearch Insights:")
            for insight in research_insights[:2]:  # Use top 2 insights
                if insight.get("summary"):
                    prompt_parts.append(f"- {insight['summary'][:200]}")
                if insight.get("keywords"):
                    prompt_parts.append(f"- Keywords: {', '.join(insight['keywords'][:5])}")
        
        if linkedin_posts:
            prompt_parts.append("\nHigh-Performing Post Inspiration:")
            for post in linkedin_posts[:2]:
                prompt_parts.append(f"- Post snippet: {post.content[:150]}...")
                if post.hashtags:
                    prompt_parts.append(f"  Hashtags used: {', '.join(post.hashtags[:5])}")
        
        if request.include_stealth_founder:
            prompt_parts.append("\nIMPORTANT: Include a subtle stealth founder angle (authentic, not salesy)")
        
        prompt_parts.append(f"\nTone: {request.tone}")
        prompt_parts.append("\nRequirements:")
        prompt_parts.append("- Authentic, valuable content (not promotional)")
        prompt_parts.append("- Include 1-2 engagement hooks/questions")
        prompt_parts.append("- Suggest 3-8 relevant hashtags")
        prompt_parts.append("- LinkedIn-optimized length (1500-3000 chars ideal)")
        prompt_parts.append("- Professional but approachable voice")
        
        prompt_parts.append("\nRespond with JSON array of drafts:")
        prompt_parts.append("""
[
  {
    "title": "Brief title/headline",
    "content": "Full post content...",
    "suggested_hashtags": ["tag1", "tag2", ...],
    "engagement_hook": "Question or hook to drive comments"
  },
  ...
]""")
        
        generation_prompt = "\n".join(prompt_parts)
        
        # Step 4: For now, return prompt-based approach (can be enhanced with Perplexity)
        # In production, call Perplexity API or store prompt for manual generation
        
        # Create placeholder drafts that show the structure
        drafts = []
        current_time = time.time()
        
        for i in range(request.num_drafts):
            draft_id = f"draft_{int(current_time)}_{i}"
            
            # Build draft content (placeholder - would come from LLM)
            draft_content = f"[Draft {i+1} for {request.pillar.value} pillar]\n\n"
            draft_content += f"Topic: {request.topic or 'Industry insights'}\n\n"
            draft_content += "This is a placeholder. In production, this would be generated by an LLM "
            draft_content += "based on the research insights and LinkedIn post patterns.\n\n"
            draft_content += "Would include:\n"
            draft_content += "- Valuable insight or story\n"
            draft_content += "- Engagement hook/question\n"
            draft_content += "- Relevant hashtags"
            
            draft = ContentDraft(
                draft_id=draft_id,
                user_id=request.user_id,
                title=f"{request.pillar.value.title()} Content Draft {i+1}",
                content=draft_content,
                pillar=request.pillar,
                topic=request.topic,
                suggested_hashtags=["EdTech", "AI", "Education", "Startup"] if i == 0 else ["MentalHealth", "Education", "Support"],
                engagement_hook="What's your experience with this?",
                stealth_founder_mention=request.include_stealth_founder and i == 0,
                linked_research_ids=request.linked_research_ids,
                linked_post_ids=[post.post_id for post in linkedin_posts[:2]] if linkedin_posts else [],
                status=ContentStatus.DRAFT,
                created_at=current_time,
                updated_at=current_time,
            )
            
            # Store in Firestore
            doc_ref = db.collection("users").document(request.user_id).collection("content_drafts").document(draft_id)
            doc_ref.set(draft.model_dump())
            
            drafts.append(draft)
        
        # Return response with generation prompt for manual use
        return ContentDraftResponse(
            success=True,
            drafts=drafts,
            insights_used=[r.get("research_id", "") for r in research_insights]
        )
        
    except Exception as e:
        logger.exception(f"Error generating content drafts: {e}")
        raise HTTPException(status_code=500, detail=f"Content draft generation failed: {str(e)}")


@router.post("/drafts/generate-prompt")
async def generate_content_draft_prompt(request: ContentDraftRequest) -> Dict[str, Any]:
    """
    Generate a prompt for manual content drafting in ChatGPT/Claude.
    
    Returns a formatted prompt that can be copy-pasted into an LLM for content generation.
    Includes research insights and LinkedIn post inspiration for better results.
    """
    try:
        # Step 1: Gather context from research insights
        research_insights = []
        if request.linked_research_ids:
            research_insights = get_research_insights(request.user_id, request.linked_research_ids)
        
        # Step 2: Get LinkedIn post inspiration if needed
        linkedin_posts = []
        if not request.linked_research_ids:
            # Auto-search for high-performing posts in target niches
            linkedin_client = get_linkedin_client()
            
            pillar_queries = {
                ContentPillar.REFERRAL: "private school admin mental health treatment center education",
                ContentPillar.THOUGHT_LEADERSHIP: "EdTech business leader AI education technology",
                ContentPillar.STEALTH_FOUNDER: "stealth startup founder early adopter investor",
                ContentPillar.MIXED: "EdTech AI education technology startup",
            }
            
            query = pillar_queries.get(request.pillar, "EdTech AI education")
            try:
                posts_result = linkedin_client.search_posts(
                    query=query,
                    max_results=5,
                    sort_by="engagement",
                    min_engagement_score=10.0,
                )
                linkedin_posts = posts_result[:5]  # Top 5 posts
            except Exception as e:
                logger.warning(f"LinkedIn search failed during prompt generation: {e}")
                linkedin_posts = []
        
        # Step 3: Build comprehensive prompt
        prompt_parts = [
            "You are an expert LinkedIn content creator specializing in B2B thought leadership and authentic engagement.",
            f"\nGenerate {request.num_drafts} LinkedIn post variants for a PACER content strategy.",
            f"\nContent Pillar: {request.pillar.value}",
        ]
        
        if request.topic:
            prompt_parts.append(f"\nTopic: {request.topic}")
        
        # Add pillar-specific guidance
        if request.pillar == ContentPillar.REFERRAL:
            prompt_parts.append("\nTarget Audience: Private school administrators, mental health professionals, treatment centers")
            prompt_parts.append("Goal: Build referral network, share insights about educational support services")
        elif request.pillar == ContentPillar.THOUGHT_LEADERSHIP:
            prompt_parts.append("\nTarget Audience: EdTech business leaders, AI-savvy executives")
            prompt_parts.append("Goal: Establish thought leadership, share industry insights")
        elif request.pillar == ContentPillar.STEALTH_FOUNDER:
            prompt_parts.append("\nTarget Audience: Early adopters, investors, stealth founders")
            prompt_parts.append("Goal: Connect with like-minded entrepreneurs (use sparingly - 5-10% of content)")
        
        if research_insights:
            prompt_parts.append("\nResearch Insights:")
            for insight in research_insights[:2]:  # Use top 2 insights
                if insight.get("summary"):
                    prompt_parts.append(f"- {insight['summary'][:200]}")
                if insight.get("keywords"):
                    prompt_parts.append(f"- Keywords: {', '.join(insight['keywords'][:5])}")
        
        if linkedin_posts:
            prompt_parts.append("\nHigh-Performing Post Inspiration:")
            for post in linkedin_posts[:2]:
                prompt_parts.append(f"- Post snippet: {post.content[:200]}...")
                if post.hashtags:
                    prompt_parts.append(f"  Hashtags used: {', '.join(post.hashtags[:5])}")
                if post.engagement_score:
                    prompt_parts.append(f"  Engagement score: {post.engagement_score}")
        
        if request.include_stealth_founder:
            prompt_parts.append("\nIMPORTANT: Include a subtle stealth founder angle (authentic, not salesy)")
        
        prompt_parts.append(f"\nTone: {request.tone}")
        prompt_parts.append("\nRequirements:")
        prompt_parts.append("- Authentic, valuable content (not promotional)")
        prompt_parts.append("- Include 1-2 engagement hooks/questions")
        prompt_parts.append("- Suggest 3-8 relevant hashtags")
        prompt_parts.append("- LinkedIn-optimized length (1500-3000 chars ideal)")
        prompt_parts.append("- Professional but approachable voice")
        
        prompt_parts.append("\nRespond with JSON array of drafts:")
        prompt_parts.append("""
[
  {
    "title": "Brief title/headline",
    "content": "Full post content...",
    "suggested_hashtags": ["tag1", "tag2", ...],
    "engagement_hook": "Question or hook to drive comments",
    "pillar": "referral" or "thought_leadership" or "stealth_founder" or "mixed"
  },
  ...
]""")
        
        full_prompt = "\n".join(prompt_parts)
        
        return {
            "success": True,
            "prompt": full_prompt,
            "instructions": "Copy this prompt into ChatGPT/Claude. After generating drafts, use POST /api/linkedin/content/drafts/store to save them.",
            "has_linkedin_inspiration": len(linkedin_posts) > 0,
            "has_research_context": len(research_insights) > 0,
        }
        
    except Exception as e:
        logger.exception(f"Error generating prompt: {e}")
        raise HTTPException(status_code=500, detail=f"Prompt generation failed: {str(e)}")


@router.post("/drafts/store", response_model=StoreDraftResponse)
async def store_content_drafts(request: StoreDraftRequest) -> Dict[str, Any]:
    """
    Store manually generated content drafts (after using ChatGPT/Claude with prompt).
    
    Accepts a list of draft objects and stores them in Firestore.
    """
    try:
        if not request.drafts:
            raise HTTPException(status_code=400, detail="Drafts list cannot be empty")
        
        stored_drafts = []
        current_time = time.time()
        
        for i, draft_data in enumerate(request.drafts):
            # Generate unique draft ID
            draft_id = f"draft_{int(current_time)}_{i}"
            
            # Validate required fields
            if not draft_data.get("content"):
                logger.warning(f"Draft {i} missing content, skipping")
                continue
            
            # Parse pillar with validation
            pillar_str = draft_data.get("pillar", "mixed")
            try:
                pillar = ContentPillar(pillar_str)
            except ValueError:
                logger.warning(f"Invalid pillar '{pillar_str}', defaulting to 'mixed'")
                pillar = ContentPillar.MIXED
            
            # Create draft object
            draft = ContentDraft(
                draft_id=draft_id,
                user_id=request.user_id,
                title=draft_data.get("title"),
                content=draft_data.get("content", ""),
                pillar=pillar,
                topic=draft_data.get("topic"),
                suggested_hashtags=draft_data.get("suggested_hashtags", []),
                engagement_hook=draft_data.get("engagement_hook"),
                stealth_founder_mention=draft_data.get("stealth_founder_mention", False),
                linked_research_ids=draft_data.get("linked_research_ids", []),
                linked_post_ids=draft_data.get("linked_post_ids", []),
                status=ContentStatus.DRAFT,
                created_at=current_time,
                updated_at=current_time,
            )
            
            # Store in Firestore
            doc_ref = db.collection("users").document(request.user_id).collection("content_drafts").document(draft_id)
            doc_ref.set(draft.model_dump())
            
            stored_drafts.append(draft)
        
        if not stored_drafts:
            raise HTTPException(status_code=400, detail="No valid drafts to store")
        
        return StoreDraftResponse(
            success=True,
            stored_count=len(stored_drafts),
            drafts=stored_drafts,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error storing drafts: {e}")
        raise HTTPException(status_code=500, detail=f"Draft storage failed: {str(e)}")


@router.get("/drafts")
async def list_content_drafts(
    user_id: str = Query(..., description="User ID"),
    pillar: Optional[str] = Query(None, description="Filter by pillar"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    """List content drafts for a user."""
    try:
        collection = db.collection("users").document(user_id).collection("content_drafts")
        query = collection.order_by("created_at", direction="DESCENDING").limit(limit)
        
        if pillar:
            query = query.where("pillar", "==", pillar)
        if status:
            query = query.where("status", "==", status)
        
        docs = query.get()
        drafts = [ContentDraft(**doc.to_dict()) for doc in docs]
        
        return {
            "success": True,
            "drafts": [d.model_dump() for d in drafts],
            "total": len(drafts),
        }
        
    except Exception as e:
        logger.exception(f"Error listing drafts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list drafts: {str(e)}")


@router.post("/calendar/schedule")
async def schedule_content(request: ContentCalendarRequest) -> Dict[str, Any]:
    """Schedule a content draft for publishing."""
    try:
        # Verify draft exists
        draft_ref = db.collection("users").document(request.user_id).collection("content_drafts").document(request.draft_id)
        draft_doc = draft_ref.get()
        
        if not draft_doc.exists:
            raise HTTPException(status_code=404, detail="Content draft not found")
        
        draft_data = draft_doc.to_dict()
        
        # Create calendar entry
        calendar_id = f"calendar_{int(time.time())}"
        calendar_entry = ContentCalendarEntry(
            calendar_id=calendar_id,
            user_id=request.user_id,
            draft_id=request.draft_id,
            scheduled_date=request.scheduled_date,
            pillar=ContentPillar(draft_data.get("pillar", "mixed")),
            status="scheduled",
            notes=request.notes,
            created_at=time.time(),
        )
        
        # Store calendar entry
        calendar_ref = db.collection("users").document(request.user_id).collection("content_calendar").document(calendar_id)
        calendar_ref.set(calendar_entry.model_dump())
        
        # Update draft status
        draft_ref.update({"status": ContentStatus.SCHEDULED.value, "scheduled_date": request.scheduled_date})
        
        return {
            "success": True,
            "calendar_id": calendar_id,
            "scheduled_date": request.scheduled_date,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error scheduling content: {e}")
        raise HTTPException(status_code=500, detail=f"Scheduling failed: {str(e)}")


@router.get("/calendar")
async def get_content_calendar(
    user_id: str = Query(..., description="User ID"),
    start_date: Optional[float] = Query(None, description="Start timestamp"),
    end_date: Optional[float] = Query(None, description="End timestamp"),
) -> Dict[str, Any]:
    """Get content calendar entries."""
    try:
        collection = db.collection("users").document(user_id).collection("content_calendar")
        query = collection.order_by("scheduled_date", direction="ASCENDING")
        
        if start_date:
            query = query.where("scheduled_date", ">=", start_date)
        if end_date:
            query = query.where("scheduled_date", "<=", end_date)
        
        docs = query.get()
        entries = [ContentCalendarEntry(**doc.to_dict()) for doc in docs]
        
        return {
            "success": True,
            "entries": [e.model_dump() for e in entries],
            "total": len(entries),
        }
        
    except Exception as e:
        logger.exception(f"Error getting calendar: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get calendar: {str(e)}")


@router.post("/outreach/generate", response_model=OutreachResponse)
async def generate_outreach(request: OutreachRequest) -> Dict[str, Any]:
    """
    Generate personalized outreach (connection requests, DMs, follow-ups).
    
    Uses prospect data, research insights, and scoring to create personalized messages.
    """
    try:
        # Fetch prospect data
        prospect_ref = db.collection("users").document(request.user_id).collection("prospects").document(request.prospect_id)
        prospect_doc = prospect_ref.get()
        
        if not prospect_doc.exists:
            raise HTTPException(status_code=404, detail="Prospect not found")
        
        prospect_data = prospect_doc.to_dict()
        
        # Get research insights if needed
        research_insights = []
        if request.use_research_insights and prospect_data.get("linked_research_ids"):
            research_insights = get_research_insights(request.user_id, prospect_data.get("linked_research_ids", []))
        
        # Build outreach prompt
        prompt_parts = [
            f"Generate personalized LinkedIn {request.outreach_type} for a prospect.",
            f"\nProspect: {prospect_data.get('name', 'Unknown')}",
            f"Title: {prospect_data.get('job_title', 'Unknown')}",
            f"Company: {prospect_data.get('company', 'Unknown')}",
        ]
        
        if prospect_data.get("best_outreach_angle"):
            prompt_parts.append(f"Suggested Angle: {prospect_data['best_outreach_angle']}")
        
        if research_insights:
            prompt_parts.append("\nResearch Context:")
            for insight in research_insights[:1]:
                if insight.get("summary"):
                    prompt_parts.append(f"- {insight['summary'][:200]}")
        
        if request.outreach_type == "connection_request":
            prompt_parts.append("\nGenerate 3 connection request variants (2-3 sentences, authentic, personalized)")
        elif request.outreach_type == "dm":
            prompt_parts.append("\nGenerate 3 DM variants (concise, value-focused, with clear CTA)")
        elif request.outreach_type == "follow_up":
            prompt_parts.append("\nGenerate 2 follow-up DM variants (if no response to initial outreach)")
        
        prompt_parts.append(f"\nTone: {request.tone}")
        prompt_parts.append("\nOutput: JSON array with 'variant' number and 'message' text")
        
        full_prompt = "\n".join(prompt_parts)
        
        # For now, return prompt-based approach
        # In production, could use Perplexity or return structured variants
        
        variants = [
            {
                "variant": 1,
                "message": f"Hi {prospect_data.get('name', 'there')}, [Personalized message would be generated here based on research insights and outreach angle]",
            },
            {
                "variant": 2,
                "message": f"Hi {prospect_data.get('name', 'there')}, [Alternative variant message]",
            },
        ]
        
        return OutreachResponse(
            success=True,
            prospect_id=request.prospect_id,
            outreach_type=request.outreach_type,
            variants=variants,
            suggested_timing="Tuesday-Thursday, 9-11am or 2-4pm",
            personalization_notes="Message includes references to research insights and suggested outreach angle",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error generating outreach: {e}")
        raise HTTPException(status_code=500, detail=f"Outreach generation failed: {str(e)}")


@router.post("/metrics/update")
async def update_engagement_metrics(request: EngagementMetricsUpdate) -> Dict[str, Any]:
    """Update engagement metrics for a published LinkedIn post."""
    try:
        # Calculate engagement rate
        engagement_rate = None
        if request.impressions and request.impressions > 0:
            total_engagement = request.likes + request.comments + request.shares
            engagement_rate = round((total_engagement / request.impressions) * 100, 2)
        
        metrics = EngagementMetrics(
            post_url=request.post_url,
            draft_id=request.draft_id,
            likes=request.likes,
            comments=request.comments,
            shares=request.shares,
            reactions=request.reactions,
            profile_views=request.profile_views,
            impressions=request.impressions,
            engagement_rate=engagement_rate,
            recorded_at=time.time(),
            updated_at=time.time(),
        )
        
        # Store metrics
        metrics_id = f"metrics_{request.draft_id}_{int(time.time())}"
        metrics_ref = db.collection("users").document(request.user_id).collection("linkedin_metrics").document(metrics_id)
        metrics_ref.set(metrics.model_dump())
        
        # Update draft status if not already published
        draft_ref = db.collection("users").document(request.user_id).collection("content_drafts").document(request.draft_id)
        draft_doc = draft_ref.get()
        if draft_doc.exists:
            draft_ref.update({"status": ContentStatus.PUBLISHED.value})
        
        return {
            "success": True,
            "metrics_id": metrics_id,
            "engagement_rate": engagement_rate,
        }
        
    except Exception as e:
        logger.exception(f"Error updating metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Metrics update failed: {str(e)}")


@router.get("/metrics/draft/{draft_id}")
async def get_draft_metrics(
    draft_id: str,
    user_id: str = Query(..., description="User ID"),
) -> Dict[str, Any]:
    """Get engagement metrics for a specific draft/post."""
    try:
        collection = db.collection("users").document(user_id).collection("linkedin_metrics")
        query = collection.where("draft_id", "==", draft_id).order_by("recorded_at", direction="DESCENDING").limit(10)
        
        docs = query.get()
        metrics_list = [EngagementMetrics(**doc.to_dict()) for doc in docs]
        
        return {
            "success": True,
            "draft_id": draft_id,
            "metrics": [m.model_dump() for m in metrics_list],
            "latest": metrics_list[0].model_dump() if metrics_list else None,
        }
        
    except Exception as e:
        logger.exception(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")


@router.post("/metrics/update-learning-patterns")
async def update_learning_patterns_from_content(
    user_id: str = Query(..., description="User ID"),
    draft_id: str = Query(..., description="Content draft ID"),
) -> Dict[str, Any]:
    """
    Update learning patterns based on content performance.
    
    Tracks which content pillars, topics, hashtags, and posting times perform best.
    Integrates with the existing learning patterns system.
    """
    try:
        # Get draft data
        draft_ref = db.collection("users").document(user_id).collection("content_drafts").document(draft_id)
        draft_doc = draft_ref.get()
        
        if not draft_doc.exists:
            raise HTTPException(status_code=404, detail="Content draft not found")
        
        draft_data = draft_doc.to_dict()
        
        # Get latest metrics
        metrics_collection = db.collection("users").document(user_id).collection("linkedin_metrics")
        metrics_query = metrics_collection.where("draft_id", "==", draft_id).order_by("recorded_at", direction="DESCENDING").limit(1)
        metrics_docs = metrics_query.get()
        
        if not metrics_docs:
            raise HTTPException(status_code=404, detail="No metrics found for this draft")
        
        latest_metrics = metrics_docs[0].to_dict()
        
        # Calculate engagement score (simple: likes + comments * 2 + shares * 3)
        engagement_score = (
            latest_metrics.get("likes", 0) +
            latest_metrics.get("comments", 0) * 2 +
            latest_metrics.get("shares", 0) * 3
        )
        
        # Update learning patterns - use a simple pattern tracking for LinkedIn content
        # Store content performance patterns separately
        updated_patterns = []
        
        # Track pillar performance
        pillar = draft_data.get("pillar", "mixed")
        pattern_id = f"content_pillar_{pillar.lower()}"
        pattern_ref = db.collection("users").document(user_id).collection("learning_patterns").document(pattern_id)
        pattern_doc = pattern_ref.get()
        
        if pattern_doc.exists:
            pattern_data = pattern_doc.to_dict()
            total_engagement = pattern_data.get("total_engagement", 0) + engagement_score
            post_count = pattern_data.get("post_count", 0) + 1
            avg_engagement = total_engagement / post_count if post_count > 0 else 0
            
            pattern_ref.update({
                "total_engagement": total_engagement,
                "post_count": post_count,
                "avg_engagement": avg_engagement,
                "updated_at": time.time(),
            })
        else:
            pattern_ref.set({
                "pattern_id": pattern_id,
                "user_id": user_id,
                "content_pillar": pillar,
                "total_engagement": engagement_score,
                "post_count": 1,
                "avg_engagement": engagement_score,
                "created_at": time.time(),
                "updated_at": time.time(),
            })
        
        # Track hashtag performance
        hashtags = draft_data.get("suggested_hashtags", [])
        for hashtag in hashtags[:5]:
            hashtag_id = f"hashtag_{hashtag.lower().replace('#', '').replace(' ', '_')}"
            hashtag_ref = db.collection("users").document(user_id).collection("learning_patterns").document(hashtag_id)
            hashtag_doc = hashtag_ref.get()
            
            if hashtag_doc.exists:
                hashtag_data = hashtag_doc.to_dict()
                total_engagement = hashtag_data.get("total_engagement", 0) + engagement_score
                post_count = hashtag_data.get("post_count", 0) + 1
                avg_engagement = total_engagement / post_count if post_count > 0 else 0
                
                hashtag_ref.update({
                    "total_engagement": total_engagement,
                    "post_count": post_count,
                    "avg_engagement": avg_engagement,
                    "updated_at": time.time(),
                })
            else:
                hashtag_ref.set({
                    "pattern_id": hashtag_id,
                    "user_id": user_id,
                    "hashtag": hashtag,
                    "total_engagement": engagement_score,
                    "post_count": 1,
                    "avg_engagement": engagement_score,
                    "created_at": time.time(),
                    "updated_at": time.time(),
                })
        
        updated_patterns.append({"pattern_type": "content_pillar", "value": pillar, "engagement_score": engagement_score})
        
        return {
            "success": True,
            "draft_id": draft_id,
            "engagement_score": engagement_score,
            "patterns_updated": len(updated_patterns),
            "patterns": [p.model_dump() if hasattr(p, 'model_dump') else dict(p) for p in updated_patterns],
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error updating learning patterns: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update learning patterns: {str(e)}")


def get_recent_draft_topics(user_id: str, days: int = 30) -> List[str]:
    """Get topics from recently created drafts to avoid duplicates."""
    try:
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        collection = db.collection("users").document(user_id).collection("content_drafts")
        query = collection.where("created_at", ">=", cutoff_time).order_by("created_at", direction="DESCENDING").limit(50)
        docs = query.get()
        topics = []
        for doc in docs:
            data = doc.to_dict()
            if data.get("topic"):
                topics.append(data["topic"])
        return topics
    except Exception as e:
        logger.warning(f"Error fetching recent draft topics: {e}")
        return []


def get_preferred_topics_from_research(user_id: str) -> List[str]:
    """Get preferred topics from recent research insights."""
    try:
        collection = db.collection("users").document(user_id).collection("research_insights")
        query = collection.order_by("created_at", direction="DESCENDING").limit(5)
        docs = query.get()
        topics = []
        for doc in docs:
            data = doc.to_dict()
            if data.get("summary"):
                keywords = data.get("keywords", [])
                topics.extend(keywords[:3])
        return topics
    except Exception as e:
        logger.warning(f"Error fetching preferred topics from research: {e}")
        return []


def get_top_hashtags_from_learning(user_id: str, limit: int = 10) -> List[str]:
    """Get top-performing hashtags from learning patterns."""
    try:
        collection = db.collection("users").document(user_id).collection("learning_patterns")
        docs = collection.stream()
        hashtag_patterns = []
        for doc in docs:
            data = doc.to_dict()
            pattern_id = data.get("pattern_id", "")
            if pattern_id.startswith("hashtag_"):
                avg_engagement = data.get("avg_engagement", 0)
                hashtag_patterns.append({
                    "hashtag": data.get("hashtag", ""),
                    "avg_engagement": avg_engagement,
                })
        hashtag_patterns.sort(key=lambda x: x["avg_engagement"], reverse=True)
        return [h["hashtag"] for h in hashtag_patterns[:limit] if h["hashtag"]]
    except Exception as e:
        logger.warning(f"Error fetching top hashtags from learning: {e}")
        return []


def build_structured_llm_prompt(
    pillar: ContentPillar,
    topic: str,
    audience: str,
    primary_goal: str,
    top_hashtags: List[str] = None,
    research_context: str = None,
    avoid_stealth_keywords: bool = False,
) -> str:
    """
    Build a structured, deterministic LLM prompt for LinkedIn post generation.
    Uses the enhanced template from the spec.
    """
    system_prompt = """You are an expert LinkedIn copywriter who writes concise, high-engagement posts for education leaders. Tone: expert, direct, inspiring. Max 180 words. Output JSON only."""
    
    # Pillar-specific defaults
    pillar_configs = {
        ContentPillar.REFERRAL: {
            "audience": "private school administrators, mental health professionals, treatment centers",
            "primary_goal": "drive referrals and build partnership networks",
            "cta_type": "question",
        },
        ContentPillar.THOUGHT_LEADERSHIP: {
            "audience": "EdTech business leaders, AI-savvy executives",
            "primary_goal": "establish thought leadership and start meaningful conversations",
            "cta_type": "question",
        },
        ContentPillar.STEALTH_FOUNDER: {
            "audience": "early adopters, investors, stealth founders",
            "primary_goal": "connect authentically with like-minded entrepreneurs",
            "cta_type": "question",
        },
    }
    
    config = pillar_configs.get(pillar, pillar_configs[ContentPillar.THOUGHT_LEADERSHIP])
    
    user_prompt_parts = [
        "{",
        f'  "pillar": "{pillar.value}",',
        f'  "topic": "{topic}",',
        f'  "audience": "{audience or config["audience"]}",',
        f'  "primary_goal": "{primary_goal or config["primary_goal"]}",',
        "  \"constraints\": {",
        "    \"length_words_max\": 180,",
        "    \"include_hashtags\": true,",
        "    \"hashtags_max\": 5,",
        f'    "avoid_stealth_keywords": {str(avoid_stealth_keywords).lower()},',
        f'    "cta_type": "{config["cta_type"]}"',
        "  }",
        "}",
        "",
        "TASK:",
        "1) Output JSON only (no extra text) with fields:",
        "{",
        '  "content": "<post text>",',
        '  "suggested_hashtags": ["#...", "#..."],',
        '  "engagement_hook": "<question or CTA>",',
        '  "estimated_read_time_secs": 10',
        "}",
        "",
        "2) Use template structure: Hook -> Insight -> Practical takeaways (1–3 bullets) -> CTA",
        "",
        "3) Keep founder mentions subtle when pillar=stealth_founder (if enabled)",
    ]
    
    if research_context:
        user_prompt_parts.insert(-3, f"\nResearch Context: {research_context[:300]}")
    
    if top_hashtags:
        user_prompt_parts.insert(-3, f"\nConsider these high-performing hashtags: {', '.join(top_hashtags[:5])}")
    
    user_prompt = "\n".join(user_prompt_parts)
    
    return f"{system_prompt}\n\nUSER:\n{user_prompt}\n\nEND"


@router.post("/drafts/generate_daily_pacer", response_model=GenerateDailyPacerResponse)
async def generate_daily_pacer(request: GenerateDailyPacerRequest) -> Dict[str, Any]:
    """
    Generate daily PACER content mix (40% referral, 50% thought leadership, 10% stealth founder).
    
    This is the scrape-free version that uses:
    - Topic libraries (pre-built topics per pillar)
    - Post templates (proven LinkedIn frameworks)
    - Research insights from Firestore
    - Learning patterns from engagement data
    - LLM generation via Perplexity
    
    No LinkedIn scraping required.
    """
    try:
        logger.info(f"🚀 Generating daily PACER content for user {request.user_id}, num_posts={request.num_posts}")
        
        # Step 1: Calculate PACER pillar distribution
        num_referral = int(request.num_posts * 0.4)
        num_thought_leadership = int(request.num_posts * 0.5)
        num_stealth_founder = int(request.num_posts * 0.1) if request.include_stealth_founder else 0
        
        total_assigned = num_referral + num_thought_leadership + num_stealth_founder
        if total_assigned < request.num_posts:
            num_thought_leadership += (request.num_posts - total_assigned)
        
        pillar_distribution = {
            "referral": num_referral,
            "thought_leadership": num_thought_leadership,
            "stealth_founder": num_stealth_founder,
        }
        
        logger.info(f"  → Pillar distribution: {pillar_distribution}")
        
        # Step 2: Gather context for topic selection
        recent_topics = get_recent_draft_topics(request.user_id)
        preferred_topics = get_preferred_topics_from_research(request.user_id)
        top_hashtags = get_top_hashtags_from_learning(request.user_id)
        
        logger.info(f"  → Found {len(recent_topics)} recent topics, {len(preferred_topics)} preferred topics, {len(top_hashtags)} top hashtags")
        
        # Step 3: Auto-discover research insights by pillar (immediate usability)
        research_insights = []
        try:
            from app.services.rmk_automation import discover_insights_for_content
            
            # Discover insights for each pillar we're generating
            for pillar, count in pillar_posts:
                if count > 0 and pillar:
                    insights = discover_insights_for_content(
                        user_id=request.user_id,
                        pillar=pillar.value if hasattr(pillar, 'value') else pillar,
                        limit=2,  # Get top 2 per pillar
                    )
                    research_insights.extend([insight.model_dump() if hasattr(insight, 'model_dump') else insight for insight in insights])
            
            # Remove duplicates by insight_id
            seen_ids = set()
            unique_insights = []
            for insight in research_insights:
                insight_id = insight.get("insight_id") or insight.get("research_id")
                if insight_id and insight_id not in seen_ids:
                    seen_ids.add(insight_id)
                    unique_insights.append(insight)
            research_insights = unique_insights[:5]  # Limit to top 5
            
            logger.info(f"  → Auto-discovered {len(research_insights)} insights for content generation")
        except Exception as e:
            logger.warning(f"Auto-discovery failed, falling back to recent insights: {e}")
            # Fallback to recent insights
            try:
                collection = db.collection("users").document(request.user_id).collection("research_insights")
                query = collection.order_by("date_collected", direction="DESCENDING").limit(3)
                docs = query.get()
                research_insights = [doc.to_dict() for doc in docs]
            except Exception as e2:
                logger.warning(f"Error fetching fallback research insights: {e2}")
        
        # Step 4: Generate posts for each pillar
        generated_drafts = []
        draft_ids = []
        current_time = time.time()
        perplexity_client = get_perplexity_client()
        
        pillar_posts = [
            (ContentPillar.REFERRAL, num_referral),
            (ContentPillar.THOUGHT_LEADERSHIP, num_thought_leadership),
            (ContentPillar.STEALTH_FOUNDER, num_stealth_founder),
        ]
        
        for pillar, count in pillar_posts:
            if count == 0:
                continue
            
            logger.info(f"  → Generating {count} posts for pillar: {pillar.value}")
            
            for i in range(count):
                # Select topic
                topic = select_topic_for_generation(
                    pillar=pillar,
                    used_topics=recent_topics,
                    preferred_topics=preferred_topics if preferred_topics else None,
                )
                
                # Select template
                template = get_template_for_pillar(pillar.value, used_templates=[])
                
                logger.info(f"    → Post {i+1}/{count}: topic='{topic[:50]}...', template='{template['name']}'")
                
                # Build generation prompt for Perplexity
                prompt_parts = [
                    f"You are an expert LinkedIn content creator. Generate a LinkedIn post using the following template and topic.",
                    f"\nTemplate Structure: {template['structure']}",
                    f"\nTopic: {topic}",
                    f"\nContent Pillar: {pillar.value}",
                ]
                
                # Add pillar-specific guidance
                if pillar == ContentPillar.REFERRAL:
                    prompt_parts.append("\nTarget Audience: Private school administrators, mental health professionals, treatment centers")
                    prompt_parts.append("Goal: Build referral network, share insights about educational support services")
                    prompt_parts.append("Tone: Helpful, empathetic, professional")
                elif pillar == ContentPillar.THOUGHT_LEADERSHIP:
                    prompt_parts.append("\nTarget Audience: EdTech business leaders, AI-savvy executives")
                    prompt_parts.append("Goal: Establish thought leadership, share industry insights")
                    prompt_parts.append("Tone: Insightful, forward-thinking, authoritative")
                elif pillar == ContentPillar.STEALTH_FOUNDER:
                    prompt_parts.append("\nTarget Audience: Early adopters, investors, stealth founders")
                    prompt_parts.append("Goal: Connect with like-minded entrepreneurs (authentic, not salesy)")
                    prompt_parts.append("Tone: Authentic, vulnerable, genuine")
                
                # Add research insights if available
                if research_insights:
                    prompt_parts.append("\nResearch Context:")
                    for insight in research_insights[:2]:
                        if insight.get("summary"):
                            prompt_parts.append(f"- {insight['summary'][:200]}")
                        if insight.get("keywords"):
                            prompt_parts.append(f"- Keywords: {', '.join(insight['keywords'][:5])}")
                
                # Add hashtag suggestions if available
                if top_hashtags:
                    prompt_parts.append(f"\nConsider using these high-performing hashtags: {', '.join(top_hashtags[:5])}")
                
                prompt_parts.append("\nRequirements:")
                prompt_parts.append("- Fill in the template with engaging, authentic content based on the topic")
                prompt_parts.append("- Keep it LinkedIn-optimized (1500-3000 characters ideal)")
                prompt_parts.append("- Include 1-2 engagement hooks/questions")
                prompt_parts.append("- Suggest 5-8 relevant hashtags")
                prompt_parts.append("- Make it valuable, not promotional")
                prompt_parts.append("- Ensure it matches the template structure but adapt it naturally")
                
                prompt_parts.append("\nRespond with ONLY a JSON object in this format:")
                prompt_parts.append("""{
  "content": "Full post content with template filled in...",
  "suggested_hashtags": ["tag1", "tag2", ...],
  "engagement_hook": "Question or hook to drive comments"
}""")
                
                generation_prompt = "\n".join(prompt_parts)
                
                # Generate content using Perplexity
                try:
                    logger.info(f"      → Calling Perplexity API for content generation...")
                    result = perplexity_client.search(
                        query=generation_prompt,
                        model="sonar",
                        return_sources=False,
                    )
                    
                    # Parse JSON response
                    import json
                    import re
                    answer = result.answer
                    json_match = re.search(r'\{.*\}', answer, re.DOTALL)
                    if json_match:
                        content_data = json.loads(json_match.group())
                    else:
                        content_data = {
                            "content": answer,
                            "suggested_hashtags": top_hashtags[:5] if top_hashtags else ["EdTech", "Education", "AI"],
                            "engagement_hook": "What's your take on this?",
                        }
                    
                    post_content = content_data.get("content", answer)
                    suggested_hashtags = content_data.get("suggested_hashtags", top_hashtags[:5] if top_hashtags else ["EdTech", "Education", "AI"])
                    engagement_hook = content_data.get("engagement_hook", "What's your experience with this?")
                    
                except Exception as e:
                    logger.warning(f"      ⚠️ Perplexity generation failed: {e}, using fallback")
                    post_content = f"[{pillar.value.title()} Post: {topic}]\n\nThis is a placeholder. In production, this would be fully generated content based on the template and topic."
                    suggested_hashtags = top_hashtags[:5] if top_hashtags else ["EdTech", "Education"]
                    engagement_hook = "What's your experience with this?"
                
                # Create draft
                draft_id = f"draft_{int(current_time)}_{pillar.value}_{i}"
                draft = ContentDraft(
                    draft_id=draft_id,
                    user_id=request.user_id,
                    title=f"{pillar.value.replace('_', ' ').title()} - {topic[:50]}",
                    content=post_content,
                    pillar=pillar,
                    topic=topic,
                    suggested_hashtags=suggested_hashtags,
                    engagement_hook=engagement_hook,
                    stealth_founder_mention=(pillar == ContentPillar.STEALTH_FOUNDER),
                    linked_research_ids=[r.get("research_id") for r in research_insights if r.get("research_id")],
                    linked_post_ids=[],
                    metadata={
                        "template_used": template["id"],
                        "template_name": template["name"],
                        "generation_method": "daily_pacer_scrape_free",
                        "generated_at": current_time,
                    },
                    status=ContentStatus.DRAFT,
                    created_at=current_time,
                    updated_at=current_time,
                )
                
                # Store in Firestore
                try:
                    doc_ref = db.collection("users").document(request.user_id).collection("content_drafts").document(draft_id)
                    doc_ref.set(draft.model_dump())
                    logger.info(f"      ✅ Saved draft {draft_id}")
                except Exception as e:
                    logger.error(f"      ❌ Error saving draft to Firestore: {e}")
                    raise
                
                generated_drafts.append(draft)
                draft_ids.append(draft_id)
                recent_topics.append(topic)
        
        logger.info(f"✅ Successfully generated {len(generated_drafts)} drafts")
        
        return GenerateDailyPacerResponse(
            success=True,
            posts_generated=len(generated_drafts),
            draft_ids=draft_ids,
            drafts=generated_drafts,
            pillar_distribution=pillar_distribution,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error generating daily PACER content: {e}")
        raise HTTPException(status_code=500, detail=f"Daily PACER generation failed: {str(e)}")


@router.post("/drafts/generate_weekly_pacer", response_model=GenerateWeeklyPacerResponse)
async def generate_weekly_pacer(request: GenerateWeeklyPacerRequest) -> Dict[str, Any]:
    """
    Generate weekly PACER content mix with enhanced options.
    
    Enhanced features:
    - topic_overrides: Prioritize specific topics
    - use_cached_research: Prefer Firestore cache to save API calls
    - Structured LLM prompt for deterministic output
    - Enhanced response with summary array
    """
    try:
        logger.info(f"🚀 Generating weekly PACER content for user {request.user_id}, num_posts={request.num_posts}")
        
        # Step 1: Calculate PACER pillar distribution
        num_referral = int(request.num_posts * 0.4)
        num_thought_leadership = int(request.num_posts * 0.5)
        num_stealth_founder = int(request.num_posts * 0.1) if request.include_stealth_founder else 0
        
        total_assigned = num_referral + num_thought_leadership + num_stealth_founder
        if total_assigned < request.num_posts:
            num_thought_leadership += (request.num_posts - total_assigned)
        
        logger.info(f"  → Pillar distribution: referral={num_referral}, thought_leadership={num_thought_leadership}, stealth_founder={num_stealth_founder}")
        
        # Step 2: Gather context
        recent_topics = get_recent_draft_topics(request.user_id, days=7)  # Weekly: last 7 days
        preferred_topics = request.topic_overrides if request.topic_overrides else get_preferred_topics_from_research(request.user_id)
        top_hashtags = get_top_hashtags_from_learning(request.user_id)
        
        # Step 3: Get research insights (cached if requested)
        research_insights = []
        research_context = ""
        if request.use_cached_research:
            try:
                collection = db.collection("users").document(request.user_id).collection("research_insights")
                query = collection.order_by("created_at", direction="DESCENDING").limit(3)
                docs = query.get()
                research_insights = [doc.to_dict() for doc in docs]
                if research_insights:
                    # Build research context string
                    context_parts = []
                    for insight in research_insights[:2]:
                        if insight.get("summary"):
                            context_parts.append(insight["summary"][:200])
                        if insight.get("keywords"):
                            context_parts.append(f"Keywords: {', '.join(insight['keywords'][:5])}")
                    research_context = " | ".join(context_parts)
                    logger.info(f"  → Using cached research insights (use_cached_research=True)")
            except Exception as e:
                logger.warning(f"Error fetching cached research: {e}")
        
        # Step 4: Generate posts
        generated_drafts = []
        draft_ids = []
        summary_list = []
        current_time = time.time()
        perplexity_client = get_perplexity_client()
        
        pillar_posts = [
            (ContentPillar.REFERRAL, num_referral),
            (ContentPillar.THOUGHT_LEADERSHIP, num_thought_leadership),
            (ContentPillar.STEALTH_FOUNDER, num_stealth_founder),
        ]
        
        for pillar, count in pillar_posts:
            if count == 0:
                continue
            
            logger.info(f"  → Generating {count} posts for pillar: {pillar.value}")
            
            for i in range(count):
                # Select topic (prioritize overrides if provided)
                if preferred_topics and i < len(preferred_topics):
                    topic = preferred_topics[i]
                else:
                    topic = select_topic_for_generation(
                        pillar=pillar,
                        used_topics=recent_topics,
                        preferred_topics=preferred_topics if preferred_topics else None,
                    )
                
                logger.info(f"    → Post {i+1}/{count}: topic='{topic[:50]}...'")
                
                # Build structured prompt
                pillar_configs = {
                    ContentPillar.REFERRAL: ("private school administrators, mental health professionals, treatment centers", "drive referrals and build partnership networks"),
                    ContentPillar.THOUGHT_LEADERSHIP: ("EdTech business leaders, AI-savvy executives", "establish thought leadership and start meaningful conversations"),
                    ContentPillar.STEALTH_FOUNDER: ("early adopters, investors, stealth founders", "connect authentically with like-minded entrepreneurs"),
                }
                
                audience, goal = pillar_configs.get(pillar, pillar_configs[ContentPillar.THOUGHT_LEADERSHIP])
                
                generation_prompt = build_structured_llm_prompt(
                    pillar=pillar,
                    topic=topic,
                    audience=audience,
                    primary_goal=goal,
                    top_hashtags=top_hashtags,
                    research_context=research_context if research_context else None,
                    avoid_stealth_keywords=not request.include_stealth_founder and pillar != ContentPillar.STEALTH_FOUNDER,
                )
                
                # Generate content using Perplexity
                try:
                    logger.info(f"      → Calling Perplexity API...")
                    result = perplexity_client.search(
                        query=generation_prompt,
                        model="sonar",
                        return_sources=False,
                    )
                    
                    # Parse JSON response
                    import json
                    import re
                    answer = result.answer
                    
                    # Extract JSON (handle markdown code blocks)
                    json_match = re.search(r'\{[\s\S]*\}', answer)
                    if json_match:
                        content_data = json.loads(json_match.group())
                    else:
                        # Fallback
                        content_data = {
                            "content": answer,
                            "suggested_hashtags": top_hashtags[:5] if top_hashtags else ["EdTech", "Education", "AI"],
                            "engagement_hook": "What's your take on this?",
                            "estimated_read_time_secs": 10,
                        }
                    
                    post_content = content_data.get("content", answer)
                    suggested_hashtags = content_data.get("suggested_hashtags", top_hashtags[:5] if top_hashtags else ["EdTech", "Education", "AI"])
                    engagement_hook = content_data.get("engagement_hook", "What's your experience with this?")
                    
                except Exception as e:
                    logger.warning(f"      ⚠️ Perplexity generation failed: {e}, using fallback")
                    post_content = f"[{pillar.value.replace('_', ' ').title()} Post: {topic}]\n\nThis is a placeholder. In production, this would be fully generated content based on the structured template."
                    suggested_hashtags = top_hashtags[:5] if top_hashtags else ["EdTech", "Education"]
                    engagement_hook = "What's your experience with this?"
                
                # Create draft
                draft_id = f"draft_{int(current_time)}_{pillar.value}_{i}"
                draft = ContentDraft(
                    draft_id=draft_id,
                    user_id=request.user_id,
                    title=f"{pillar.value.replace('_', ' ').title()} - {topic[:50]}",
                    content=post_content,
                    pillar=pillar,
                    topic=topic,
                    suggested_hashtags=suggested_hashtags,
                    engagement_hook=engagement_hook,
                    stealth_founder_mention=(pillar == ContentPillar.STEALTH_FOUNDER),
                    linked_research_ids=[r.get("research_id") for r in research_insights if r.get("research_id")],
                    linked_post_ids=[],
                    metadata={
                        "generation_method": "weekly_pacer_enhanced",
                        "generated_at": current_time,
                        "use_cached_research": request.use_cached_research,
                        "topic_override": i < len(request.topic_overrides) if request.topic_overrides else False,
                    },
                    status=ContentStatus.DRAFT,
                    created_at=current_time,
                    updated_at=current_time,
                )
                
                # Store in Firestore
                try:
                    doc_ref = db.collection("users").document(request.user_id).collection("content_drafts").document(draft_id)
                    doc_ref.set(draft.model_dump())
                    logger.info(f"      ✅ Saved draft {draft_id}")
                except Exception as e:
                    logger.error(f"      ❌ Error saving draft: {e}")
                    raise
                
                generated_drafts.append(draft)
                draft_ids.append(draft_id)
                summary_list.append(DraftSummary(
                    draft_id=draft_id,
                    pillar=pillar.value,
                    topic=topic,
                ))
                recent_topics.append(topic)
        
        logger.info(f"✅ Successfully generated {len(generated_drafts)} drafts")
        
        return GenerateWeeklyPacerResponse(
            success=True,
            generated=len(generated_drafts),
            draft_ids=draft_ids,
            summary=summary_list,
            drafts=generated_drafts,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error generating weekly PACER content: {e}")
        raise HTTPException(status_code=500, detail=f"Weekly PACER generation failed: {str(e)}")


@router.post("/engagement/generate_dm", response_model=EngagementDMResponse)
async def generate_engagement_dm(request: EngagementDMRequest) -> Dict[str, Any]:
    """
    Generate DM templates for engagement conversion.
    
    Converts LinkedIn engagement (comments, connections, likes) into personalized DM templates
    for moving conversations forward.
    """
    try:
        logger.info(f"📩 Generating DM templates for {request.engagement_type} engagement, prospect: {request.prospect_name}")
        
        variants = []
        
        if request.engagement_type == "comment":
            # Comment → Move to DM variants
            variants = [
                {
                    "variant": 1,
                    "message": f"Hi {request.prospect_name}, thanks for the comment — I appreciated your perspective on {request.topic or 'that topic'}. If you're open, I'd love a 15-minute chat to learn how your team approaches this and share a resource we've used. Would next Wed or Thu work?"
                },
                {
                    "variant": 2,
                    "message": f"Thanks, {request.prospect_name}. Your note made me think — we've tested a small intervention that helped similar schools. Want a quick call so I can share the one-pager?"
                },
            ]
            
        elif request.engagement_type == "connection":
            # New connection (referral network)
            variants = [
                {
                    "variant": 1,
                    "message": f"Hi {request.prospect_name}, appreciate the connect. I work with schools and partners supporting neurodivergent learners — curious how your org is approaching referrals right now. Can I send a quick resource that might be helpful?"
                },
                {
                    "variant": 2,
                    "message": f"Thanks for connecting, {request.prospect_name}. Would you be open to a short intro call to explore alignment? I focus on partnership models that simplify referral pathways."
                },
            ]
            
        elif request.engagement_type == "like":
            # Like → Gentle engagement
            variants = [
                {
                    "variant": 1,
                    "message": f"Hi {request.prospect_name}, noticed you liked my post about {request.topic or 'that topic'}. Sounds like it resonated. If you're interested, I'd be happy to share more resources on this. What's your biggest challenge in this area right now?"
                },
                {
                    "variant": 2,
                    "message": f"Thanks for the like, {request.prospect_name}. If you're exploring {request.topic or 'this topic'} for your team, I have a one-pager that might be helpful. Interested?"
                },
            ]
        
        else:
            # Generic engagement
            variants = [
                {
                    "variant": 1,
                    "message": f"Hi {request.prospect_name}, thanks for the engagement. Would love to connect and learn more about your work. Open to a quick call?"
                },
            ]
        
        # Limit to requested number of variants
        variants = variants[:request.num_variants]
        
        return EngagementDMResponse(
            success=True,
            engagement_type=request.engagement_type,
            variants=variants,
        )
        
    except Exception as e:
        logger.exception(f"Error generating engagement DM: {e}")
        raise HTTPException(status_code=500, detail=f"DM generation failed: {str(e)}")


@router.post("/metrics/generate-weekly-summary", response_model=WeeklySummaryResponse)
async def generate_weekly_summary(request: WeeklySummaryRequest) -> Dict[str, Any]:
    """
    Generate weekly summary of content performance and learning insights.
    
    Run every Sunday night to analyze:
    - Top pillar performance
    - Top hashtags
    - Suggested topics for next week
    - Average engagement rates
    """
    try:
        logger.info(f"📊 Generating weekly summary for user {request.user_id}")
        
        # Calculate week range
        if request.week_start_date:
            week_start = request.week_start_date
            week_end = week_start + (7 * 24 * 60 * 60)
        else:
            # Default: last 7 days
            week_end = time.time()
            week_start = week_end - (7 * 24 * 60 * 60)
        
        # Get published posts from this week
        collection = db.collection("users").document(request.user_id).collection("content_drafts")
        query = collection.where("created_at", ">=", week_start).where("created_at", "<=", week_end)
        docs = query.get()
        
        posts = []
        pillar_engagement = {}
        hashtag_engagement = {}
        total_engagement = 0
        total_impressions = 0
        
        for doc in docs:
            draft_data = doc.to_dict()
            if draft_data.get("status") == "published":
                posts.append(draft_data)
                pillar = draft_data.get("pillar", "unknown")
                
                # Get metrics for this draft
                metrics_collection = db.collection("users").document(request.user_id).collection("linkedin_metrics")
                metrics_query = metrics_collection.where("draft_id", "==", doc.id).order_by("recorded_at", direction="DESCENDING").limit(1)
                metrics_docs = metrics_query.get()
                
                if metrics_docs:
                    metrics = metrics_docs[0].to_dict()
                    engagement = metrics.get("likes", 0) + metrics.get("comments", 0) * 2 + metrics.get("shares", 0) * 3
                    impressions = metrics.get("impressions", 0)
                    
                    # Track pillar performance
                    if pillar not in pillar_engagement:
                        pillar_engagement[pillar] = {"total": 0, "count": 0, "impressions": 0}
                    pillar_engagement[pillar]["total"] += engagement
                    pillar_engagement[pillar]["count"] += 1
                    pillar_engagement[pillar]["impressions"] += impressions
                    
                    # Track hashtag performance
                    hashtags = draft_data.get("suggested_hashtags", [])
                    for hashtag in hashtags:
                        hashtag_clean = hashtag.replace("#", "").lower()
                        if hashtag_clean not in hashtag_engagement:
                            hashtag_engagement[hashtag_clean] = {"total": 0, "count": 0}
                        hashtag_engagement[hashtag_clean]["total"] += engagement
                        hashtag_engagement[hashtag_clean]["count"] += 1
                    
                    total_engagement += engagement
                    total_impressions += impressions if impressions else 0
        
        # Determine top pillar
        top_pillar = None
        top_pillar_avg = 0
        for pillar, data in pillar_engagement.items():
            avg = data["total"] / data["count"] if data["count"] > 0 else 0
            if avg > top_pillar_avg:
                top_pillar_avg = avg
                top_pillar = pillar
        
        # Get top hashtags
        top_hashtags = []
        for hashtag, data in sorted(hashtag_engagement.items(), key=lambda x: x[1]["total"], reverse=True)[:10]:
            avg_engagement = data["total"] / data["count"] if data["count"] > 0 else 0
            top_hashtags.append({
                "hashtag": f"#{hashtag}",
                "total_engagement": data["total"],
                "avg_engagement": round(avg_engagement, 2),
                "used_in_posts": data["count"],
            })
        
        # Calculate average engagement rate
        avg_engagement_rate = None
        if total_impressions > 0:
            avg_engagement_rate = round((total_engagement / total_impressions) * 100, 2)
        
        # Generate suggested topics (based on top-performing pillar)
        suggested_topics = []
        if top_pillar:
            try:
                pillar_enum = ContentPillar(top_pillar)
                topics = get_topics_for_pillar(pillar_enum, limit=5)
                suggested_topics = topics
            except Exception as e:
                logger.warning(f"Error getting suggested topics: {e}")
        
        logger.info(f"  → Summary: {len(posts)} posts, top pillar: {top_pillar}, top hashtags: {len(top_hashtags)}")
        
        return WeeklySummaryResponse(
            success=True,
            week_start=week_start,
            week_end=week_end,
            total_posts=len(posts),
            top_pillar=top_pillar,
            top_hashtags=top_hashtags,
            suggested_topics=suggested_topics,
            avg_engagement_rate=avg_engagement_rate,
        )
        
    except Exception as e:
        logger.exception(f"Error generating weekly summary: {e}")
        raise HTTPException(status_code=500, detail=f"Weekly summary generation failed: {str(e)}")

