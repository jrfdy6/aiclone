"""
Comprehensive Content Generation Routes

Generates 100+ variations across 20+ content types with support for:
- Human-ready format (copy/paste)
- JSON payloads (backend ingestion)  
- Both formats simultaneously
"""

import logging
import time
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta

from app.models.comprehensive_content import (
    ComprehensiveContentRequest,
    ComprehensiveContentResponse,
    ContentVariation,
    ContentType,
    ContentFormat,
    WeeklyCalendarRequest,
    WeeklyCalendarResponse,
    WeeklyCalendarPost,
    HashtagSetRequest,
    HashtagSetResponse,
    HashtagCategory,
    EngagementHookRequest,
    EngagementHookResponse,
    HookType,
)
from app.services.comprehensive_content_generator import (
    generate_content_variations,
    format_as_human_readable,
    format_as_json_payloads,
    generate_hashtag_set,
    generate_engagement_hooks,
)
from app.services.content_topic_library import get_topics_for_pillar, select_topic_for_generation
from app.models.linkedin_content import ContentPillar

logger = logging.getLogger(__name__)
router = APIRouter()


# Best posting times by day (EST)
BEST_POSTING_TIMES = {
    "Monday": ["8:00 AM", "12:00 PM", "5:00 PM"],
    "Tuesday": ["9:00 AM", "1:00 PM", "6:00 PM"],
    "Wednesday": ["8:00 AM", "2:00 PM", "5:00 PM"],
    "Thursday": ["9:00 AM", "12:00 PM", "6:00 PM"],
    "Friday": ["8:00 AM", "1:00 PM", "4:00 PM"],
}


@router.post("/generate", response_model=ComprehensiveContentResponse)
async def generate_comprehensive_content(request: ComprehensiveContentRequest) -> Dict[str, Any]:
    """
    Generate comprehensive content across 20+ types with 100+ variation support.
    
    Supports:
    - LinkedIn posts (multiple formats)
    - Reels/Shorts/TikTok scripts
    - Email newsletters
    - Outreach messages
    - Follow-up sequences
    - Content calendars
    - Hashtag sets
    - Engagement hooks
    
    Output formats:
    - A. Human-ready (copy/paste)
    - B. JSON payloads (backend ingestion)
    - C. Both
    """
    try:
        logger.info(f"🚀 Generating {request.num_variations} variations of {request.content_type.value} for user {request.user_id}")
        logger.info(f"  → Format: {request.format.value}")
        logger.info(f"  → Pillar: {request.pillar}, Topic: {request.topic}")
        
        # Auto-discover and link insights if not provided (immediate usability)
        auto_linked_insight_ids = []
        if request.pillar and not request.linked_research_ids:
            try:
                from app.services.rmk_automation import auto_link_insights_to_content_generation
                auto_linked_insight_ids = auto_link_insights_to_content_generation(
                    user_id=request.user_id,
                    pillar=request.pillar,
                    topic=request.topic,
                    limit=3,
                )
                logger.info(f"  → Auto-discovered {len(auto_linked_insight_ids)} insights for pillar={request.pillar}")
            except Exception as e:
                logger.warning(f"Auto-discovery failed: {e}")
        
        # Use auto-discovered or provided insight IDs
        final_insight_ids = request.linked_research_ids or auto_linked_insight_ids
        
        # Generate variations
        variations = generate_content_variations(
            content_type=request.content_type,
            num_variations=request.num_variations,
            pillar=request.pillar,
            topic=request.topic,
            hook_type=request.hook_type,
            hashtag_category=request.hashtag_category,
            tone=request.tone,
        )
        
        logger.info(f"  → Generated {len(variations)} variations")
        
        # Format output based on request
        human_readable = None
        json_payloads = None
        
        if request.format == ContentFormat.HUMAN_READY or request.format == ContentFormat.BOTH:
            human_readable = format_as_human_readable(request.content_type, variations)
            logger.info("  → Formatted as human-readable")
        
        if request.format == ContentFormat.JSON_PAYLOAD or request.format == ContentFormat.BOTH:
            json_payloads = format_as_json_payloads(request.content_type, variations, request.user_id)
            logger.info("  → Formatted as JSON payloads")
        
        return ComprehensiveContentResponse(
            success=True,
            content_type=request.content_type.value,
            format=request.format.value,
            variations_generated=len(variations),
            variations=variations,
            human_readable_content=human_readable,
            json_payloads=json_payloads,
            generation_metadata={
                "timestamp": time.time(),
                "pillar": request.pillar,
                "topic": request.topic,
                "auto_linked_insights": len(auto_linked_insight_ids) > 0,
                "linked_insight_ids": final_insight_ids,
            },
        )
        
    except Exception as e:
        logger.exception(f"Error generating comprehensive content: {e}")
        raise HTTPException(status_code=500, detail=f"Content generation failed: {str(e)}")


@router.post("/calendar/weekly", response_model=WeeklyCalendarResponse)
async def generate_weekly_calendar(request: WeeklyCalendarRequest) -> Dict[str, Any]:
    """
    Generate a weekly content calendar with optimal posting times and hashtags.
    
    Creates a balanced calendar based on 5-pillar distribution:
    - 40% Referral
    - 50% Thought Leadership
    - 10% Stealth Founder (optional)
    """
    try:
        logger.info(f"📅 Generating weekly calendar for user {request.user_id}, {request.num_posts} posts")
        
        # Calculate pillar distribution
        if request.pillar_distribution:
            pillar_dist = request.pillar_distribution
        else:
            # Default PACER distribution
            num_referral = int(request.num_posts * 0.4)
            num_thought_leadership = int(request.num_posts * 0.5)
            num_stealth_founder = int(request.num_posts * 0.1)
            remainder = request.num_posts - (num_referral + num_thought_leadership + num_stealth_founder)
            num_thought_leadership += remainder  # Add remainder to thought leadership
            
            pillar_dist = {
                "referral": num_referral,
                "thought_leadership": num_thought_leadership,
                "stealth_founder": num_stealth_founder,
            }
        
        # Days of week for posting
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        
        # Generate posts
        calendar_posts = []
        post_count = 0
        
        # Assign posts to days
        pillar_posts = []
        for pillar, count in pillar_dist.items():
            for _ in range(count):
                pillar_posts.append(pillar)
        
        # Generate topics for each pillar
        topics_by_pillar = {}
        for pillar_name, count in pillar_dist.items():
            if count > 0:
                try:
                    pillar_enum = ContentPillar(pillar_name)
                    topics = get_topics_for_pillar(pillar_enum, limit=count)
                    topics_by_pillar[pillar_name] = topics[:count]
                except:
                    topics_by_pillar[pillar_name] = [f"{pillar_name} topic {i+1}" for i in range(count)]
        
        # Create calendar entries
        day_index = 0
        for pillar_name in pillar_posts:
            if post_count >= request.num_posts:
                break
            
            day = days[day_index % len(days)]
            time_slot = BEST_POSTING_TIMES[day][post_count % len(BEST_POSTING_TIMES[day])] if request.include_posting_times else "TBD"
            
            # Get topic for this pillar
            topics = topics_by_pillar.get(pillar_name, [])
            topic = topics[post_count % len(topics)] if topics else f"{pillar_name} content"
            
            # Generate content preview (placeholder - in production would be actual generated content)
            content_preview = f"[{pillar_name.replace('_', ' ').title()}] {topic[:80]}..."
            
            # Get hashtags
            hashtags = []
            if request.include_hashtags:
                if pillar_name == "referral":
                    hashtags = generate_hashtag_set(HashtagCategory.REFERRAL_PARTNER, 5)
                elif pillar_name == "thought_leadership":
                    hashtags = generate_hashtag_set(HashtagCategory.AI_LEADERSHIP, 5)
                else:
                    hashtags = generate_hashtag_set(HashtagCategory.INDUSTRY, 5)
            
            calendar_posts.append(WeeklyCalendarPost(
                day=day,
                time=time_slot,
                pillar=pillar_name,
                topic=topic,
                content_preview=content_preview,
                suggested_hashtags=hashtags,
                keywords=[pillar_name, topic.split()[0]] if request.include_keywords else [],
            ))
            
            post_count += 1
            day_index += 1
        
        # Calculate week dates
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        week_start = monday.strftime("%Y-%m-%d")
        week_end = (monday + timedelta(days=6)).strftime("%Y-%m-%d")
        
        logger.info(f"  → Created {len(calendar_posts)} calendar entries")
        
        return WeeklyCalendarResponse(
            success=True,
            week_start_date=week_start,
            week_end_date=week_end,
            total_posts=len(calendar_posts),
            posts=calendar_posts,
            pillar_distribution=pillar_dist,
            best_posting_times=BEST_POSTING_TIMES if request.include_posting_times else {},
        )
        
    except Exception as e:
        logger.exception(f"Error generating weekly calendar: {e}")
        raise HTTPException(status_code=500, detail=f"Calendar generation failed: {str(e)}")


@router.post("/hashtags/generate", response_model=HashtagSetResponse)
async def generate_hashtag_sets(request: HashtagSetRequest) -> Dict[str, Any]:
    """Generate hashtag sets for specified categories."""
    try:
        logger.info(f"🏷️  Generating hashtag sets for user {request.user_id}, categories: {[c.value for c in request.categories]}")
        
        sets = {}
        for category in request.categories:
            hashtags = generate_hashtag_set(category, request.num_per_category)
            sets[category.value] = hashtags
        
        logger.info(f"  → Generated {len(sets)} hashtag sets")
        
        return HashtagSetResponse(
            success=True,
            sets=sets,
        )
        
    except Exception as e:
        logger.exception(f"Error generating hashtag sets: {e}")
        raise HTTPException(status_code=500, detail=f"Hashtag generation failed: {str(e)}")


@router.post("/hooks/generate", response_model=EngagementHookResponse)
async def generate_engagement_hooks_endpoint(request: EngagementHookRequest) -> Dict[str, Any]:
    """Generate engagement hooks of specified types."""
    try:
        logger.info(f"🎣 Generating engagement hooks for user {request.user_id}, types: {[h.value for h in request.hook_types]}")
        
        hooks = {}
        for hook_type in request.hook_types:
            generated_hooks = generate_engagement_hooks(hook_type, request.num_per_type, request.topic)
            hooks[hook_type.value] = generated_hooks
        
        logger.info(f"  → Generated {len(hooks)} hook sets")
        
        return EngagementHookResponse(
            success=True,
            hooks=hooks,
        )
        
    except Exception as e:
        logger.exception(f"Error generating engagement hooks: {e}")
        raise HTTPException(status_code=500, detail=f"Hook generation failed: {str(e)}")

