"""
Outreach Engine Routes

Complete outreach automation with:
- Prospect segmentation
- Sequence generation
- Scoring & prioritization
- Engagement tracking
- Calendar & cadence management
"""

import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException

from app.models.outreach_engine import (
    SegmentProspectsRequest,
    SegmentProspectsResponse,
    ProspectSegmentTag,
    GenerateSequenceRequest,
    GenerateSequenceResponse,
    OutreachSequence,
    PrioritizeProspectsRequest,
    PrioritizeProspectsResponse,
    TrackEngagementRequest,
    WeeklyCadenceRequest,
    WeeklyCadenceResponse,
    WeeklyCadenceEntry,
    OutreachMetricsRequest,
    OutreachMetricsResponse,
    ProspectSegment,
    OutreachType,
    EngagementStatus,
)
from app.services.outreach_engine_service import (
    segment_prospects,
    build_outreach_sequence,
    prioritize_prospects,
)
from app.services.firestore_client import db
from app.services.scoring import get_research_insights
from app.routes.learning import update_pattern

logger = logging.getLogger(__name__)
router = APIRouter()

# Weekly outreach distribution (days of week)
WEEKLY_OUTREACH_TIMES = {
    "Monday": ["9:00 AM", "2:00 PM"],
    "Tuesday": ["9:00 AM", "2:00 PM", "4:00 PM"],
    "Wednesday": ["9:00 AM", "2:00 PM"],
    "Thursday": ["9:00 AM", "1:00 PM", "3:00 PM"],
    "Friday": ["9:00 AM", "2:00 PM"],
}


@router.post("/segment", response_model=SegmentProspectsResponse)
async def segment_prospects_endpoint(request: SegmentProspectsRequest) -> Dict[str, Any]:
    """
    Segment prospects into audience segments.
    
    Distribution:
    - 50% Private school admins / mental health / referral network
    - 50% EdTech / AI-savvy leaders
    - 5% Stealth founder / early adopters
    
    Tags prospects with: industry, role, location, engagement potential, PACER relevance
    """
    try:
        logger.info(f"🏷️  Segmenting prospects for user {request.user_id}")
        
        segment_tags = segment_prospects(
            user_id=request.user_id,
            prospect_ids=request.prospect_ids,
            target_distribution=request.target_distribution,
        )
        
        # Count by segment
        segment_counts = {}
        for tag in segment_tags:
            segment_name = tag.segment.value
            segment_counts[segment_name] = segment_counts.get(segment_name, 0) + 1
        
        logger.info(f"  → Segmented {len(segment_tags)} prospects: {segment_counts}")
        
        return SegmentProspectsResponse(
            success=True,
            total_prospects=len(segment_tags),
            segments=segment_counts,
            tagged_prospects=segment_tags,
        )
        
    except Exception as e:
        logger.exception(f"Error segmenting prospects: {e}")
        raise HTTPException(status_code=500, detail=f"Segmentation failed: {str(e)}")


@router.post("/sequence/generate", response_model=GenerateSequenceResponse)
async def generate_outreach_sequence(request: GenerateSequenceRequest) -> Dict[str, Any]:
    """
    Generate complete outreach sequence for a prospect.
    
    Variations per audience segment:
    - Referral network: relationship-building + value-sharing
    - Thought leadership: insights + engagement hooks
    - Stealth founder: subtle mentions, curiosity-driven
    """
    try:
        logger.info(f"📝 Generating outreach sequence for prospect {request.prospect_id}")
        
        # Load prospect
        collection = db.collection("users").document(request.user_id).collection("prospects")
        doc = collection.document(request.prospect_id).get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Prospect not found")
        
        prospect_data = doc.to_dict()
        
        # Get segment
        segment_str = prospect_data.get("segment", "thought_leadership")
        try:
            segment = ProspectSegment(segment_str)
        except:
            segment = ProspectSegment.THOUGHT_LEADERSHIP
        
        # Get research insights
        research_insights = []
        if prospect_data.get("linked_research_ids"):
            research_insights = get_research_insights(request.user_id, prospect_data.get("linked_research_ids", []))
        
        # Build sequence
        sequence = build_outreach_sequence(
            prospect=prospect_data,
            segment=segment,
            sequence_type=request.sequence_type,
            research_insights=research_insights,
        )
        
        # Extract all variants for response
        variants = {}
        if sequence.connection_request:
            variants["connection_request"] = sequence.connection_request.get("variants", [])
        if sequence.initial_dm:
            variants["initial_dm"] = sequence.initial_dm.get("variants", [])
        if sequence.followup_1:
            variants["followup_1"] = sequence.followup_1.get("variants", [])
        if sequence.followup_2:
            variants["followup_2"] = sequence.followup_2.get("variants", [])
        if sequence.followup_3:
            variants["followup_3"] = sequence.followup_3.get("variants", [])
        
        # Store sequence in Firestore
        sequence_ref = db.collection("users").document(request.user_id).collection("outreach_sequences").document(request.prospect_id)
        sequence_ref.set(sequence.model_dump())
        
        logger.info(f"  → Generated {request.sequence_type} sequence for {segment.value} segment")
        
        return GenerateSequenceResponse(
            success=True,
            prospect_id=request.prospect_id,
            segment=segment.value,
            sequence_type=request.sequence_type,
            sequence=sequence,
            variants=variants,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error generating sequence: {e}")
        raise HTTPException(status_code=500, detail=f"Sequence generation failed: {str(e)}")


@router.post("/prioritize", response_model=PrioritizeProspectsResponse)
async def prioritize_prospects_endpoint(request: PrioritizeProspectsRequest) -> Dict[str, Any]:
    """
    Score and prioritize prospects.
    
    Focus manual effort on top-tier prospects based on:
    - Fit (role relevance / audience type)
    - Referral capacity (how likely they are to refer or respond)
    - Signal strength (engagement / online presence)
    """
    try:
        logger.info(f"🎯 Prioritizing prospects for user {request.user_id}")
        logger.info(f"  → Min scores: fit={request.min_fit_score}, referral={request.min_referral_capacity}, signal={request.min_signal_strength}")
        
        prospects = prioritize_prospects(
            user_id=request.user_id,
            min_fit_score=request.min_fit_score,
            min_referral_capacity=request.min_referral_capacity,
            min_signal_strength=request.min_signal_strength,
            segment=request.segment,
            limit=request.limit,
        )
        
        top_tier_count = len([p for p in prospects if p.get("priority_score", 0) >= 80])
        
        logger.info(f"  → Found {len(prospects)} prioritized prospects ({top_tier_count} top-tier)")
        
        return PrioritizeProspectsResponse(
            success=True,
            total_scored=len(prospects),
            top_tier_count=top_tier_count,
            prospects=prospects,
        )
        
    except Exception as e:
        logger.exception(f"Error prioritizing prospects: {e}")
        raise HTTPException(status_code=500, detail=f"Prioritization failed: {str(e)}")


@router.post("/track-engagement")
async def track_engagement(request: TrackEngagementRequest) -> Dict[str, Any]:
    """
    Track engagement from DMs and follow-ups.
    
    Records: replies, meeting bookings, email responses
    Feeds results into learning patterns
    """
    try:
        logger.info(f"📊 Tracking engagement for prospect {request.prospect_id}")
        
        # Load sequence
        sequence_ref = db.collection("users").document(request.user_id).collection("outreach_sequences").document(request.prospect_id)
        sequence_doc = sequence_ref.get()
        
        if not sequence_doc.exists:
            # Create sequence if doesn't exist
            sequence_data = {
                "prospect_id": request.prospect_id,
                "current_step": 0,
                "status": request.engagement_status.value,
                "engagement_data": {},
            }
        else:
            sequence_data = sequence_doc.to_dict()
        
        # Update engagement data
        engagement_data = sequence_data.get("engagement_data", {})
        engagement_data[request.outreach_type.value] = {
            "status": request.engagement_status.value,
            "data": request.engagement_data,
            "tracked_at": time.time(),
        }
        
        # Update status
        if request.engagement_status == EngagementStatus.REPLIED:
            sequence_data["status"] = EngagementStatus.REPLIED.value
        elif request.engagement_status == EngagementStatus.MEETING_BOOKED:
            sequence_data["status"] = EngagementStatus.MEETING_BOOKED.value
        
        # Update sequence
        sequence_data["engagement_data"] = engagement_data
        sequence_data["updated_at"] = time.time()
        sequence_ref.set(sequence_data)
        
        # Feed into learning patterns (update learning patterns)
        try:
            # Get prospect data
            prospect_ref = db.collection("users").document(request.user_id).collection("prospects").document(request.prospect_id)
            prospect_doc = prospect_ref.get()
            
            if prospect_doc.exists:
                prospect_data = prospect_doc.to_dict()
                
                # Map engagement status to learning data
                engagement_data = {
                    "email_sent": 1 if request.outreach_type in [OutreachType.CONNECTION_REQUEST, OutreachType.INITIAL_DM] else 0,
                    "email_responded": 1 if request.engagement_status == EngagementStatus.REPLIED else 0,
                    "meeting_booked": 1 if request.engagement_status == EngagementStatus.MEETING_BOOKED else 0,
                }
                
                # Update patterns for this prospect
                industry = prospect_data.get("company", "").split()[0] if prospect_data.get("company") else None
                if industry:
                    update_pattern(request.user_id, "industry", industry, engagement_data)
                
                outreach_angle = prospect_data.get("best_outreach_angle")
                if outreach_angle:
                    update_pattern(request.user_id, "outreach_angle", outreach_angle, engagement_data)
        except Exception as e:
            logger.warning(f"Failed to update learning patterns: {e}")
        
        logger.info(f"  → Tracked engagement: {request.engagement_status.value} for {request.outreach_type.value}")
        
        return {
            "success": True,
            "prospect_id": request.prospect_id,
            "engagement_status": request.engagement_status.value,
            "learning_patterns_updated": True,
        }
        
    except Exception as e:
        logger.exception(f"Error tracking engagement: {e}")
        raise HTTPException(status_code=500, detail=f"Engagement tracking failed: {str(e)}")


@router.post("/cadence/weekly", response_model=WeeklyCadenceResponse)
async def generate_weekly_cadence(request: WeeklyCadenceRequest) -> Dict[str, Any]:
    """
    Build weekly outreach cadence:
    - Connection requests: 30-50/week
    - Follow-ups: 2-3 rounds per prospect
    - Check-ins: quarterly re-engagement for dormant contacts
    """
    try:
        logger.info(f"📅 Generating weekly outreach cadence for user {request.user_id}")
        logger.info(f"  → Target: {request.target_connection_requests} connection requests, {request.target_followups} follow-ups")
        
        # Calculate week dates
        if request.week_start_date:
            week_start = datetime.fromtimestamp(request.week_start_date)
        else:
            today = datetime.now()
            monday = today - timedelta(days=today.weekday())
            week_start = monday
        
        week_end = week_start + timedelta(days=6)
        week_start_str = week_start.strftime("%Y-%m-%d")
        week_end_str = week_end.strftime("%Y-%m-%d")
        
        # Get prioritized prospects
        prioritized = prioritize_prospects(
            user_id=request.user_id,
            min_fit_score=70,
            min_referral_capacity=60,
            limit=request.target_connection_requests + 20,  # Extra for variety
        )
        
        # Segment prospects to match distribution (50% referral, 50% thought leadership, 5% stealth)
        segment_counts = {"referral_network": 0, "thought_leadership": 0, "stealth_founder": 0}
        target_ref = int(request.target_connection_requests * 0.5)
        target_tl = int(request.target_connection_requests * 0.5)
        target_sf = int(request.target_connection_requests * 0.05)
        
        cadence_entries = []
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        day_index = 0
        time_index = 0
        
        # Add connection requests
        for prospect in prioritized:
            if len(cadence_entries) >= request.target_connection_requests:
                break
            
            segment = prospect.get("segment", "thought_leadership")
            
            # Apply distribution limits
            if segment == "referral_network" and segment_counts["referral_network"] >= target_ref:
                continue
            if segment == "thought_leadership" and segment_counts["thought_leadership"] >= target_tl:
                continue
            if segment == "stealth_founder" and segment_counts["stealth_founder"] >= target_sf:
                continue
            
            day = days[day_index % len(days)]
            times = WEEKLY_OUTREACH_TIMES[day]
            time_slot = times[time_index % len(times)]
            
            # Calculate date
            day_offset = day_index
            entry_date = (week_start + timedelta(days=day_offset)).strftime("%Y-%m-%d")
            
            cadence_entries.append(WeeklyCadenceEntry(
                day=day,
                date=entry_date,
                time=time_slot,
                prospect_id=prospect.get("prospect_id") or prospect.get("id", ""),
                prospect_name=prospect.get("name", "Unknown"),
                segment=segment,
                outreach_type=OutreachType.CONNECTION_REQUEST,
                sequence_step=0,
                message_variant=1,
                priority_score=prospect.get("priority_score", 0.0),
            ))
            
            segment_counts[segment] = segment_counts.get(segment, 0) + 1
            day_index += 1
            if day_index % len(days) == 0:
                time_index += 1
        
        # Add follow-ups (from previous weeks' connection requests)
        # Get prospects who received connection requests but haven't replied
        collection = db.collection("users").document(request.user_id).collection("outreach_sequences")
        sequences_docs = collection.where("status", "in", ["sent", "delivered", "opened"]).limit(request.target_followups).get()
        
        followup_count = 0
        for seq_doc in sequences_docs:
            if followup_count >= request.target_followups:
                break
            
            seq_data = seq_doc.to_dict()
            prospect_id = seq_data.get("prospect_id")
            
            # Get prospect data
            prospect_ref = db.collection("users").document(request.user_id).collection("prospects").document(prospect_id)
            prospect_doc = prospect_ref.get()
            
            if not prospect_doc.exists:
                continue
            
            prospect_data = prospect_doc.to_dict()
            current_step = seq_data.get("current_step", 0)
            
            # Add follow-up
            day = days[day_index % len(days)]
            times = WEEKLY_OUTREACH_TIMES[day]
            time_slot = times[time_index % len(times)]
            day_offset = day_index
            entry_date = (week_start + timedelta(days=day_offset)).strftime("%Y-%m-%d")
            
            cadence_entries.append(WeeklyCadenceEntry(
                day=day,
                date=entry_date,
                time=time_slot,
                prospect_id=prospect_id,
                prospect_name=prospect_data.get("name", "Unknown"),
                segment=prospect_data.get("segment", "thought_leadership"),
                outreach_type=OutreachType.FOLLOWUP_1 if current_step == 0 else OutreachType.FOLLOWUP_2,
                sequence_step=current_step + 1,
                message_variant=1,
                priority_score=prospect_data.get("priority_score", 0.0),
            ))
            
            followup_count += 1
            day_index += 1
            if day_index % len(days) == 0:
                time_index += 1
        
        logger.info(f"  → Created {len(cadence_entries)} cadence entries")
        
        return WeeklyCadenceResponse(
            success=True,
            week_start=week_start_str,
            week_end=week_end_str,
            total_outreach=len(cadence_entries),
            entries=cadence_entries,
            distribution=segment_counts,
        )
        
    except Exception as e:
        logger.exception(f"Error generating weekly cadence: {e}")
        raise HTTPException(status_code=500, detail=f"Cadence generation failed: {str(e)}")


@router.post("/metrics", response_model=OutreachMetricsResponse)
async def get_outreach_metrics(request: OutreachMetricsRequest) -> Dict[str, Any]:
    """
    Track engagement from DMs and follow-ups.
    
    Feed results into learning patterns:
    - Which messages, formats, or angles get the best response per audience segment
    """
    try:
        logger.info(f"📊 Getting outreach metrics for user {request.user_id}, last {request.date_range_days} days")
        
        cutoff_time = time.time() - (request.date_range_days * 24 * 60 * 60)
        
        # Get all outreach sequences
        collection = db.collection("users").document(request.user_id).collection("outreach_sequences")
        docs = collection.where("updated_at", ">=", cutoff_time).get()
        
        total_outreach = 0
        connection_requests_sent = 0
        dms_sent = 0
        followups_sent = 0
        replies_received = 0
        meetings_booked = 0
        
        segment_performance = {}
        sequence_performances = []
        
        for doc in docs:
            seq_data = doc.to_dict()
            total_outreach += 1
            
            # Count by type
            engagement_data = seq_data.get("engagement_data", {})
            
            # Check connection requests
            if "connection_request" in engagement_data:
                connection_requests_sent += 1
            
            # Check DMs
            if "initial_dm" in engagement_data:
                dms_sent += 1
            
            # Check follow-ups
            if any(k.startswith("followup") for k in engagement_data.keys()):
                followups_sent += 1
            
            # Check replies
            if seq_data.get("status") == EngagementStatus.REPLIED.value:
                replies_received += 1
            
            # Check meetings
            if seq_data.get("status") == EngagementStatus.MEETING_BOOKED.value:
                meetings_booked += 1
            
            # Track by segment
            segment = seq_data.get("segment", "unknown")
            if segment not in segment_performance:
                segment_performance[segment] = {
                    "total": 0,
                    "replies": 0,
                    "meetings": 0,
                }
            
            segment_performance[segment]["total"] += 1
            if seq_data.get("status") == EngagementStatus.REPLIED.value:
                segment_performance[segment]["replies"] += 1
            if seq_data.get("status") == EngagementStatus.MEETING_BOOKED.value:
                segment_performance[segment]["meetings"] += 1
            
            # Track sequence performance
            if seq_data.get("status") in [EngagementStatus.REPLIED.value, EngagementStatus.MEETING_BOOKED.value]:
                sequence_performances.append({
                    "prospect_id": seq_data.get("prospect_id"),
                    "segment": segment,
                    "sequence_type": seq_data.get("sequence_type"),
                    "status": seq_data.get("status"),
                })
        
        # Calculate rates
        reply_rate = (replies_received / total_outreach * 100) if total_outreach > 0 else 0.0
        meeting_rate = (meetings_booked / total_outreach * 100) if total_outreach > 0 else 0.0
        
        # Calculate segment rates
        for segment, perf in segment_performance.items():
            perf["reply_rate"] = (perf["replies"] / perf["total"] * 100) if perf["total"] > 0 else 0.0
            perf["meeting_rate"] = (perf["meetings"] / perf["total"] * 100) if perf["total"] > 0 else 0.0
        
        # Top performing sequences (by reply/meeting rate)
        top_performing = sorted(sequence_performances, key=lambda x: 1 if x["status"] == EngagementStatus.MEETING_BOOKED.value else 0.5, reverse=True)[:10]
        
        logger.info(f"  → Metrics: {total_outreach} total, {replies_received} replies ({reply_rate:.1f}%), {meetings_booked} meetings ({meeting_rate:.1f}%)")
        
        return OutreachMetricsResponse(
            success=True,
            date_range_days=request.date_range_days,
            total_outreach=total_outreach,
            connection_requests_sent=connection_requests_sent,
            dms_sent=dms_sent,
            followups_sent=followups_sent,
            replies_received=replies_received,
            meetings_booked=meetings_booked,
            reply_rate=round(reply_rate, 2),
            meeting_rate=round(meeting_rate, 2),
            segment_performance=segment_performance,
            top_performing_sequences=top_performing,
        )
        
    except Exception as e:
        logger.exception(f"Error getting outreach metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Metrics retrieval failed: {str(e)}")


@router.get("/sequence/{prospect_id}")
async def get_outreach_sequence(
    user_id: str,
    prospect_id: str,
) -> Dict[str, Any]:
    """Get outreach sequence for a prospect."""
    try:
        sequence_ref = db.collection("users").document(user_id).collection("outreach_sequences").document(prospect_id)
        sequence_doc = sequence_ref.get()
        
        if not sequence_doc.exists:
            raise HTTPException(status_code=404, detail="Outreach sequence not found")
        
        return {
            "success": True,
            "sequence": sequence_doc.to_dict(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting sequence: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get sequence: {str(e)}")

