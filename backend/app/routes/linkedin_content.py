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
    ContentPillar,
    ContentStatus,
)

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
    """
    try:
        # Same logic as generate_content_drafts but return prompt instead
        research_insights = []
        if request.linked_research_ids:
            research_insights = get_research_insights(request.user_id, request.linked_research_ids)
        
        prompt_parts = [
            "You are an expert LinkedIn content creator specializing in B2B thought leadership.",
            f"\nGenerate {request.num_drafts} LinkedIn post variants for a PACER content strategy.",
            f"\nContent Pillar: {request.pillar.value}",
        ]
        
        if request.topic:
            prompt_parts.append(f"Topic: {request.topic}")
        
        # Add pillar-specific guidance
        pillar_guidance = {
            ContentPillar.REFERRAL: "Target: Private school admins, mental health pros. Goal: Build referral network.",
            ContentPillar.THOUGHT_LEADERSHIP: "Target: EdTech business leaders. Goal: Establish thought leadership.",
            ContentPillar.STEALTH_FOUNDER: "Target: Early adopters, investors. Use sparingly (5-10% of content).",
            ContentPillar.MIXED: "Target: Mixed audience across EdTech, AI, and education.",
        }
        prompt_parts.append(pillar_guidance.get(request.pillar, ""))
        
        if research_insights:
            prompt_parts.append("\nResearch Context:")
            for insight in research_insights:
                if insight.get("summary"):
                    prompt_parts.append(f"- {insight['summary']}")
                if insight.get("keywords"):
                    prompt_parts.append(f"- Keywords: {', '.join(insight['keywords'])}")
        
        prompt_parts.append(f"\nTone: {request.tone}")
        prompt_parts.append("\nOutput Format: JSON array with 'title', 'content', 'suggested_hashtags', 'engagement_hook'")
        
        full_prompt = "\n".join(prompt_parts)
        
        return {
            "success": True,
            "prompt": full_prompt,
            "instructions": "Copy this prompt into ChatGPT/Claude, then use POST /api/linkedin/content/drafts/store to save results",
        }
        
    except Exception as e:
        logger.exception(f"Error generating prompt: {e}")
        raise HTTPException(status_code=500, detail=f"Prompt generation failed: {str(e)}")


@router.post("/drafts/store")
async def store_content_drafts(
    user_id: str = Query(..., description="User ID"),
    drafts_json: List[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Store manually generated content drafts (after using ChatGPT/Claude with prompt).
    """
    try:
        stored_drafts = []
        current_time = time.time()
        
        for i, draft_data in enumerate(drafts_json):
            draft_id = f"draft_{int(current_time)}_{i}"
            
            draft = ContentDraft(
                draft_id=draft_id,
                user_id=user_id,
                title=draft_data.get("title", f"Draft {i+1}"),
                content=draft_data.get("content", ""),
                pillar=ContentPillar(draft_data.get("pillar", "mixed")),
                suggested_hashtags=draft_data.get("suggested_hashtags", []),
                engagement_hook=draft_data.get("engagement_hook"),
                stealth_founder_mention=draft_data.get("stealth_founder_mention", False),
                status=ContentStatus.DRAFT,
                created_at=current_time,
                updated_at=current_time,
            )
            
            doc_ref = db.collection("users").document(user_id).collection("content_drafts").document(draft_id)
            doc_ref.set(draft.model_dump())
            
            stored_drafts.append(draft)
        
        return {
            "success": True,
            "stored_count": len(stored_drafts),
            "drafts": [d.model_dump() for d in stored_drafts],
        }
        
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

