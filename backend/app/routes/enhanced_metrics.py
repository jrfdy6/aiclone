"""
Enhanced Metrics & Learning Routes

Complete metrics tracking and learning system:
- Content Metrics (LinkedIn posts, reels, emails, DMs)
- Prospect & Outreach Metrics (connection requests, DMs, meetings)
- Learning Patterns (performance analysis)
- Weekly Reports (dashboard JSON)
"""

import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query

from app.models.enhanced_metrics import (
    ContentMetricsUpdateRequest,
    ContentMetricsResponse,
    ProspectMetricsUpdateRequest,
    ProspectMetricsResponse,
    UpdateLearningPatternsRequest,
    UpdateLearningPatternsResponse,
    WeeklyReportRequest,
    WeeklyReportResponse,
    OutreachSummary,
    PatternType,
)
from app.services.enhanced_metrics_service import (
    save_content_metrics,
    save_prospect_metrics,
    update_learning_patterns,
    generate_recommendations,
    calculate_engagement_rate,
)
from app.services.firestore_client import db

logger = logging.getLogger(__name__)
router = APIRouter()


# ====================
# Content Metrics Endpoints
# ====================

@router.post("/content/update", response_model=ContentMetricsResponse)
async def update_content_metrics(request: ContentMetricsUpdateRequest) -> Dict[str, Any]:
    """
    Update metrics for a post or reel.
    
    Records engagement data (likes, comments, shares, impressions, reactions, etc.)
    and calculates engagement rate.
    """
    try:
        logger.info(f"📊 Updating content metrics for content_id={request.content_id}, pillar={request.pillar}")
        
        # Prepare metrics data
        metrics_data = {
            "content_id": request.content_id,
            "pillar": request.pillar.value,
            "platform": request.platform.value,
            "post_type": request.post_type.value,
            "post_url": request.post_url,
            "publish_date": request.publish_date,
            "metrics": request.metrics.model_dump(),
            "top_hashtags": request.top_hashtags,
            "top_mentions": request.top_mentions,
            "audience_segment": request.audience_segment,
            "notes": request.notes or "",
        }
        
        # Save metrics
        metrics_id = save_content_metrics(request.user_id, metrics_data)
        
        # Calculate engagement rate
        engagement_rate = calculate_engagement_rate(
            likes=request.metrics.likes,
            comments=request.metrics.comments,
            shares=request.metrics.shares,
            impressions=request.metrics.impressions,
        )
        
        logger.info(f"  → Saved metrics_id={metrics_id}, engagement_rate={engagement_rate}%")
        
        return ContentMetricsResponse(
            success=True,
            metrics_id=metrics_id,
            engagement_rate=engagement_rate,
        )
        
    except Exception as e:
        logger.exception(f"Error updating content metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update content metrics: {str(e)}")


@router.get("/content/draft/{draft_id}")
async def get_content_metrics_for_draft(
    draft_id: str,
    user_id: str = Query(..., description="User identifier"),
) -> Dict[str, Any]:
    """
    Fetch metrics for a specific draft/content ID.
    """
    try:
        collection = db.collection("users").document(user_id).collection("content_metrics")
        query = collection.where("content_id", "==", draft_id).order_by("created_at", direction="DESCENDING")
        docs = query.get()
        
        metrics_list = [doc.to_dict() for doc in docs]
        
        return {
            "success": True,
            "content_id": draft_id,
            "metrics_count": len(metrics_list),
            "metrics": metrics_list,
        }
        
    except Exception as e:
        logger.exception(f"Error getting content metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get content metrics: {str(e)}")


@router.post("/content/update-learning-patterns")
async def update_content_learning_patterns(
    user_id: str = Query(..., description="User identifier"),
    draft_id: Optional[str] = Query(None, description="Optional: update patterns for specific draft"),
    date_range_days: int = Query(30, ge=1, le=365, description="Date range for analysis"),
) -> Dict[str, Any]:
    """
    Trigger pattern learning for content pillars, hashtags, and topics.
    
    Analyzes performance and stores patterns in learning_patterns collection.
    """
    try:
        logger.info(f"🧠 Updating content learning patterns for user {user_id}")
        
        # Update learning patterns
        patterns = update_learning_patterns(
            user_id=user_id,
            pattern_types=[
                PatternType.CONTENT_PILLAR,
                PatternType.HASHTAG,
                PatternType.TOPIC,
            ],
            date_range_days=date_range_days,
        )
        
        logger.info(f"  → Updated {len(patterns)} content learning patterns")
        
        return {
            "success": True,
            "patterns_updated": len(patterns),
            "message": "Content learning patterns updated",
        }
        
    except Exception as e:
        logger.exception(f"Error updating content learning patterns: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update learning patterns: {str(e)}")


# ====================
# Prospect Metrics Endpoints
# ====================

@router.post("/prospects/update", response_model=ProspectMetricsResponse)
async def update_prospect_metrics(request: ProspectMetricsUpdateRequest) -> Dict[str, Any]:
    """
    Record connection, DM, and meeting data for a prospect.
    
    Updates prospect metrics with:
    - Connection request sent/accepted
    - DM entries (sent, responses)
    - Meetings booked
    - Score updates
    """
    try:
        logger.info(f"📊 Updating prospect metrics for prospect_id={request.prospect_id}")
        
        # Prepare metrics data
        metrics_data = {
            "prospect_id": request.prospect_id,
            "sequence_id": request.sequence_id,
            "connection_request_sent": request.connection_request_sent,
            "connection_accepted": request.connection_accepted,
            "dm_sent": request.dm_sent,
            "meetings_booked": request.meetings_booked,
            "score_updates": request.score_updates.model_dump() if request.score_updates else None,
        }
        
        # Save metrics
        result = save_prospect_metrics(request.user_id, metrics_data)
        
        logger.info(f"  → Saved prospect_metric_id={result['prospect_metric_id']}, reply_rate={result.get('reply_rate', 0)}%, meeting_rate={result.get('meeting_rate', 0)}%")
        
        return ProspectMetricsResponse(
            success=True,
            prospect_metric_id=result["prospect_metric_id"],
            reply_rate=result.get("reply_rate"),
            meeting_rate=result.get("meeting_rate"),
        )
        
    except Exception as e:
        logger.exception(f"Error updating prospect metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update prospect metrics: {str(e)}")


@router.get("/prospects/{prospect_id}")
async def get_prospect_metrics(
    prospect_id: str,
    user_id: str = Query(..., description="User identifier"),
) -> Dict[str, Any]:
    """
    Fetch metrics for a single prospect.
    """
    try:
        collection = db.collection("users").document(user_id).collection("prospect_metrics")
        query = collection.where("prospect_id", "==", prospect_id).order_by("created_at", direction="DESCENDING")
        docs = query.get()
        
        metrics_list = [doc.to_dict() for doc in docs]
        
        # Calculate aggregated stats
        total_dms = sum(len(m.get("dm_sent", [])) for m in metrics_list)
        total_meetings = sum(len(m.get("meetings_booked", [])) for m in metrics_list)
        total_responses = sum(
            len([dm for dm in m.get("dm_sent", []) if dm.get("response_type") in ["positive", "neutral"]])
            for m in metrics_list
        )
        
        reply_rate = (total_responses / total_dms * 100) if total_dms > 0 else 0.0
        meeting_rate = (total_meetings / total_dms * 100) if total_dms > 0 else 0.0
        
        return {
            "success": True,
            "prospect_id": prospect_id,
            "metrics_count": len(metrics_list),
            "aggregated_stats": {
                "total_dms_sent": total_dms,
                "total_responses": total_responses,
                "total_meetings": total_meetings,
                "reply_rate": round(reply_rate, 2),
                "meeting_rate": round(meeting_rate, 2),
            },
            "metrics": metrics_list,
        }
        
    except Exception as e:
        logger.exception(f"Error getting prospect metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get prospect metrics: {str(e)}")


@router.post("/prospects/update-learning-patterns")
async def update_prospect_learning_patterns(
    user_id: str = Query(..., description="User identifier"),
    prospect_id: Optional[str] = Query(None, description="Optional: update patterns for specific prospect"),
    date_range_days: int = Query(30, ge=1, le=365, description="Date range for analysis"),
) -> Dict[str, Any]:
    """
    Analyze outreach sequences for patterns and success.
    
    Identifies top-performing outreach sequences and audience segments.
    """
    try:
        logger.info(f"🧠 Updating prospect learning patterns for user {user_id}")
        
        # Update learning patterns
        patterns = update_learning_patterns(
            user_id=user_id,
            pattern_types=[
                PatternType.OUTREACH_SEQUENCE,
                PatternType.AUDIENCE_SEGMENT,
            ],
            date_range_days=date_range_days,
        )
        
        logger.info(f"  → Updated {len(patterns)} prospect learning patterns")
        
        return {
            "success": True,
            "patterns_updated": len(patterns),
            "message": "Prospect learning patterns updated",
        }
        
    except Exception as e:
        logger.exception(f"Error updating prospect learning patterns: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update learning patterns: {str(e)}")


# ====================
# Weekly Reports
# ====================

@router.post("/weekly-report", response_model=WeeklyReportResponse)
async def generate_weekly_report(request: WeeklyReportRequest) -> Dict[str, Any]:
    """
    Generate weekly JSON summary dashboard.
    
    Includes:
    - Total posts and average engagement rate
    - Best pillar, top hashtags, top audience segments
    - Outreach summary (connection accept rate, DM reply rate, meetings)
    - Recommendations for next week
    """
    try:
        logger.info(f"📈 Generating weekly report for user {request.user_id}")
        
        # Calculate week dates
        if request.week_start:
            week_start = request.week_start
        else:
            today = datetime.utcnow()
            monday = today - timedelta(days=today.weekday())
            week_start = monday.replace(hour=0, minute=0, second=0, microsecond=0)
        
        if request.week_end:
            week_end = request.week_end
        else:
            week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        
        logger.info(f"  → Week: {week_start.date()} to {week_end.date()}")
        
        # Get content metrics for the week
        content_collection = db.collection("users").document(request.user_id).collection("content_metrics")
        content_query = content_collection.where("created_at", ">=", week_start).where("created_at", "<=", week_end)
        content_docs = content_query.get()
        
        # Analyze content
        total_posts = len(content_docs)
        engagement_rates = []
        pillar_counts = {}
        all_hashtags = []
        all_segments = []
        
        for doc in content_docs:
            data = doc.to_dict()
            engagement_rate = data.get("engagement_rate", 0)
            engagement_rates.append(engagement_rate)
            
            pillar = data.get("pillar")
            if pillar:
                pillar_counts[pillar] = pillar_counts.get(pillar, 0) + 1
            
            hashtags = data.get("top_hashtags", [])
            all_hashtags.extend(hashtags)
            
            segments = data.get("audience_segment", [])
            all_segments.extend(segments)
        
        avg_engagement_rate = sum(engagement_rates) / len(engagement_rates) if engagement_rates else 0.0
        best_pillar = max(pillar_counts.items(), key=lambda x: x[1])[0] if pillar_counts else None
        
        # Get top hashtags (by frequency)
        hashtag_counts = {}
        for hashtag in all_hashtags:
            hashtag_counts[hashtag] = hashtag_counts.get(hashtag, 0) + 1
        top_hashtags = [h[0] for h in sorted(hashtag_counts.items(), key=lambda x: x[1], reverse=True)[:5]]
        
        # Get top audience segments (by frequency)
        segment_counts = {}
        for segment in all_segments:
            segment_counts[segment] = segment_counts.get(segment, 0) + 1
        top_segments = [s[0] for s in sorted(segment_counts.items(), key=lambda x: x[1], reverse=True)[:3]]
        
        # Get prospect metrics for the week
        prospect_collection = db.collection("users").document(request.user_id).collection("prospect_metrics")
        prospect_query = prospect_collection.where("created_at", ">=", week_start).where("created_at", "<=", week_end)
        prospect_docs = prospect_query.get()
        
        # Analyze outreach
        total_connection_requests = 0
        total_connections_accepted = 0
        total_dms_sent = 0
        total_responses = 0
        total_meetings = 0
        
        for doc in prospect_docs:
            data = doc.to_dict()
            if data.get("connection_request_sent"):
                total_connection_requests += 1
                if data.get("connection_accepted"):
                    total_connections_accepted += 1
            
            dms = data.get("dm_sent", [])
            total_dms_sent += len(dms)
            total_responses += len([dm for dm in dms if dm.get("response_type") in ["positive", "neutral"]])
            
            meetings = data.get("meetings_booked", [])
            total_meetings += len(meetings)
        
        connection_accept_rate = (total_connections_accepted / total_connection_requests * 100) if total_connection_requests > 0 else 0.0
        dm_reply_rate = (total_responses / total_dms_sent * 100) if total_dms_sent > 0 else 0.0
        
        outreach_summary = OutreachSummary(
            connection_accept_rate=round(connection_accept_rate, 2),
            dm_reply_rate=round(dm_reply_rate, 2),
            meetings_booked=total_meetings,
            total_connection_requests=total_connection_requests,
            total_dms_sent=total_dms_sent,
        )
        
        # Generate recommendations
        recommendations = generate_recommendations(request.user_id, week_start, week_end)
        
        logger.info(f"  → Report: {total_posts} posts, {avg_engagement_rate:.1f}% avg engagement, {total_meetings} meetings")
        
        return WeeklyReportResponse(
            success=True,
            week_start=week_start,
            week_end=week_end,
            total_posts=total_posts,
            avg_engagement_rate=round(avg_engagement_rate, 2),
            best_pillar=best_pillar,
            top_hashtags=top_hashtags,
            top_audience_segments=top_segments,
            outreach_summary=outreach_summary,
            recommendations=recommendations,
        )
        
    except Exception as e:
        logger.exception(f"Error generating weekly report: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate weekly report: {str(e)}")


# ====================
# Learning Patterns Endpoints
# ====================

@router.post("/learning/update-patterns", response_model=UpdateLearningPatternsResponse)
async def update_learning_patterns_endpoint(request: UpdateLearningPatternsRequest) -> Dict[str, Any]:
    """
    Update all learning patterns based on recent metrics.
    
    Analyzes performance across:
    - Content pillars
    - Hashtags
    - Topics
    - Outreach sequences
    - Audience segments
    """
    try:
        logger.info(f"🧠 Updating learning patterns for user {request.user_id}")
        
        patterns = update_learning_patterns(
            user_id=request.user_id,
            pattern_types=[request.pattern_type] if request.pattern_type else None,
            date_range_days=request.date_range_days,
        )
        
        logger.info(f"  → Updated {len(patterns)} learning patterns")
        
        return UpdateLearningPatternsResponse(
            success=True,
            patterns_updated=len(patterns),
            patterns=patterns,
        )
        
    except Exception as e:
        logger.exception(f"Error updating learning patterns: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update learning patterns: {str(e)}")


@router.get("/learning/patterns")
async def get_learning_patterns(
    user_id: str = Query(..., description="User identifier"),
    pattern_type: Optional[str] = Query(None, description="Filter by pattern type"),
    limit: int = Query(20, ge=1, le=100, description="Limit results"),
) -> Dict[str, Any]:
    """
    Get learning patterns, optionally filtered by type.
    
    Returns patterns ordered by average performance (descending).
    """
    try:
        collection = db.collection("users").document(user_id).collection("learning_patterns")
        
        if pattern_type:
            query = collection.where("pattern_type", "==", pattern_type).order_by("average_performance", direction="DESCENDING").limit(limit)
        else:
            query = collection.order_by("average_performance", direction="DESCENDING").limit(limit)
        
        docs = query.get()
        patterns = [doc.to_dict() for doc in docs]
        
        return {
            "success": True,
            "patterns_count": len(patterns),
            "patterns": patterns,
        }
        
    except Exception as e:
        logger.exception(f"Error getting learning patterns: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get learning patterns: {str(e)}")

