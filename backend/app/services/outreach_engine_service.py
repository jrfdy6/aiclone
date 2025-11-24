"""
Outreach Engine Service

Complete outreach automation with:
- Prospect segmentation (50% referral, 50% thought leadership, 5% stealth founder)
- Sequence generation (connection requests, DMs, follow-ups)
- Scoring & prioritization
- Engagement tracking
- Calendar & cadence management
"""

import time
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone

from app.models.outreach_engine import (
    ProspectSegment,
    OutreachType,
    EngagementStatus,
    ProspectSegmentTag,
    OutreachSequence,
)
from app.models.prospect import Prospect
from app.services.firestore_client import db
from app.services.scoring import score_prospect
from app.services.perplexity_client import get_perplexity_client

logger = logging.getLogger(__name__)


# Segment Keywords Mapping
SEGMENT_KEYWORDS = {
    ProspectSegment.REFERRAL_NETWORK: [
        "private school", "school admin", "mental health", "treatment center",
        "referral", "school counselor", "student support", "special education",
        "neurodivergent", "adhd", "autism", "iep",
    ],
    ProspectSegment.THOUGHT_LEADERSHIP: [
        "edtech", "education technology", "ai", "artificial intelligence",
        "vp", "director", "chief", "business leader", "executive",
        "innovation", "transformation", "digital",
    ],
    ProspectSegment.STEALTH_FOUNDER: [
        "founder", "co-founder", "startup", "early stage", "stealth",
        "investor", "angel", "vc", "entrepreneur", "building",
    ],
}


def assign_segment_to_prospect(prospect: Dict[str, Any]) -> ProspectSegment:
    """
    Assign prospect to segment based on job title, company, industry.
    
    Default distribution: 50% referral, 50% thought leadership, 5% stealth founder
    """
    text = f"{prospect.get('job_title', '')} {prospect.get('company', '')} {prospect.get('industry', '')}".lower()
    
    # Check stealth founder first (smallest segment)
    if any(keyword in text for keyword in SEGMENT_KEYWORDS[ProspectSegment.STEALTH_FOUNDER]):
        return ProspectSegment.STEALTH_FOUNDER
    
    # Check referral network
    if any(keyword in text for keyword in SEGMENT_KEYWORDS[ProspectSegment.REFERRAL_NETWORK]):
        return ProspectSegment.REFERRAL_NETWORK
    
    # Default to thought leadership (largest segment)
    return ProspectSegment.THOUGHT_LEADERSHIP


def calculate_engagement_potential(prospect: Dict[str, Any]) -> float:
    """
    Calculate engagement potential score (0.0 - 1.0).
    
    Based on:
    - Job title seniority
    - Online presence (LinkedIn, website)
    - Signal strength
    """
    score = 0.5  # Base score
    
    # Job title seniority
    job_title = prospect.get("job_title", "").lower()
    high_value_titles = ["ceo", "founder", "president", "chief", "vp", "director"]
    if any(title in job_title for title in high_value_titles):
        score += 0.2
    
    # Online presence
    if prospect.get("linkedin"):
        score += 0.1
    if prospect.get("website") or prospect.get("email"):
        score += 0.1
    
    # Signal strength from scoring
    signal_strength = prospect.get("signal_strength", 0) or 0
    score += (signal_strength / 100) * 0.1
    
    return min(1.0, score)


def assign_pacer_relevance(segment: ProspectSegment) -> List[str]:
    """Assign PACER relevance based on segment."""
    mapping = {
        ProspectSegment.REFERRAL_NETWORK: ["referral"],
        ProspectSegment.THOUGHT_LEADERSHIP: ["thought_leadership"],
        ProspectSegment.STEALTH_FOUNDER: ["stealth_founder"],
    }
    return mapping.get(segment, [])


def segment_prospects(
    user_id: str,
    prospect_ids: Optional[List[str]] = None,
    target_distribution: Optional[Dict[str, float]] = None,
) -> List[ProspectSegmentTag]:
    """
    Segment prospects according to distribution (50% referral, 50% thought leadership, 5% stealth founder).
    """
    # Load prospects
    collection = db.collection("users").document(user_id).collection("prospects")
    
    if prospect_ids:
        prospects_data = []
        for prospect_id in prospect_ids:
            doc = collection.document(prospect_id).get()
            if doc.exists:
                prospects_data.append(doc.to_dict())
    else:
        # Load all approved prospects
        query = collection.where("approval_status", "==", "approved")
        docs = query.get()
        prospects_data = [doc.to_dict() for doc in docs]
    
    # Assign segments
    segment_tags = []
    for prospect_data in prospects_data:
        segment = assign_segment_to_prospect(prospect_data)
        engagement_potential = calculate_engagement_potential(prospect_data)
        
        segment_tag = ProspectSegmentTag(
            segment=segment,
            industry=prospect_data.get("industry"),
            role=prospect_data.get("job_title"),
            location=prospect_data.get("location"),
            engagement_potential=engagement_potential,
            pacer_relevance=assign_pacer_relevance(segment),
            prospect_id=prospect_data.get("prospect_id") or prospect_data.get("id", ""),
        )
        segment_tags.append(segment_tag)
        
        # Update prospect with segment info
        doc_ref = collection.document(segment_tag.prospect_id)
        doc_ref.update({
            "segment": segment.value,
            "engagement_potential": engagement_potential,
            "pacer_relevance": assign_pacer_relevance(segment),
        })
    
    # Apply target distribution if specified
    if target_distribution:
        # Re-balance segments to match distribution
        # (In production, would re-assign to match target distribution)
        pass
    
    return segment_tags


def generate_connection_request_variants(
    prospect: Dict[str, Any],
    segment: ProspectSegment,
    num_variants: int = 3,
) -> List[Dict[str, str]]:
    """Generate connection request variants by segment."""
    name = prospect.get("name", "there")
    company = prospect.get("company", "")
    job_title = prospect.get("job_title", "")
    
    variants = []
    
    if segment == ProspectSegment.REFERRAL_NETWORK:
        variants = [
            {
                "variant": 1,
                "message": f"Hi {name}, I work with schools and partners supporting neurodivergent learners. I'd love to connect and share insights about referral partnerships.",
            },
            {
                "variant": 2,
                "message": f"Hi {name}, I noticed you're at {company} and work in {job_title}. I focus on building stronger referral networks between schools and support services. Would love to connect.",
            },
            {
                "variant": 3,
                "message": f"Hi {name}, I'd like to connect with fellow professionals supporting student mental health and educational support services.",
            },
        ]
    elif segment == ProspectSegment.THOUGHT_LEADERSHIP:
        variants = [
            {
                "variant": 1,
                "message": f"Hi {name}, I saw your work in {job_title} at {company}. I'm also focused on AI and EdTech innovation. Would love to connect and share insights.",
            },
            {
                "variant": 2,
                "message": f"Hi {name}, I'm building tools for education leaders and would value connecting with someone in your role at {company}.",
            },
            {
                "variant": 3,
                "message": f"Hi {name}, I noticed we're both working in the EdTech/AI space. Would love to connect and share perspectives.",
            },
        ]
    else:  # STEALTH_FOUNDER
        variants = [
            {
                "variant": 1,
                "message": f"Hi {name}, I'm also building in the EdTech space. Would love to connect with fellow founders.",
            },
            {
                "variant": 2,
                "message": f"Hi {name}, I noticed we're both working on {company if company else 'something in EdTech'}. Would value connecting with another builder.",
            },
            {
                "variant": 3,
                "message": f"Hi {name}, fellow founder here. Would love to connect and share experiences building in education.",
            },
        ]
    
    return variants[:num_variants]


def generate_dm_variants(
    prospect: Dict[str, Any],
    segment: ProspectSegment,
    research_insights: Optional[List[Dict[str, Any]]] = None,
    num_variants: int = 3,
) -> List[Dict[str, str]]:
    """Generate DM variants by segment with research context."""
    name = prospect.get("name", "there")
    company = prospect.get("company", "")
    job_title = prospect.get("job_title", "")
    outreach_angle = prospect.get("best_outreach_angle", "value-focused approach")
    
    variants = []
    
    if segment == ProspectSegment.REFERRAL_NETWORK:
        # Relationship-building + value-sharing
        variants = [
            {
                "variant": 1,
                "message": f"Hi {name}, thanks for connecting. I work with schools and partners building referral networks. I've been researching best practices in student support transitions — would you be open to a quick 15-min chat to share insights?",
            },
            {
                "variant": 2,
                "message": f"Hi {name}, I noticed your work at {company}. I focus on simplifying referral pathways between schools and treatment centers. I have a one-pager with practical frameworks — worth sharing?",
            },
            {
                "variant": 3,
                "message": f"Hi {name}, I'd love to learn how {company} approaches referral partnerships. Could I send you a quick resource that's helped other schools streamline this process?",
            },
        ]
    elif segment == ProspectSegment.THOUGHT_LEADERSHIP:
        # Insights + engagement hooks
        research_context = ""
        if research_insights:
            research = research_insights[0] if research_insights else {}
            research_context = research.get("summary", "")[:150] or ""
        
        variants = [
            {
                "variant": 1,
                "message": f"Hi {name}, I've been researching {outreach_angle.lower()} and found some interesting patterns. Your perspective as {job_title} at {company} would be valuable. Worth a quick call?",
            },
            {
                "variant": 2,
                "message": f"Hi {name}, I saw your recent post about [topic]. I've been analyzing trends in EdTech AI adoption — curious about your take on [specific insight]. Open to a brief conversation?",
            },
            {
                "variant": 3,
                "message": f"Hi {name}, based on your role at {company}, I thought you'd find this relevant: [key insight from research]. Interested in exploring how this applies to your context?",
            },
        ]
    else:  # STEALTH_FOUNDER
        # Subtle mentions, curiosity-driven
        variants = [
            {
                "variant": 1,
                "message": f"Hi {name}, fellow builder here. I'm working on tools for educators and curious about your experience building {company if company else 'in EdTech'}. Open to a quick chat?",
            },
            {
                "variant": 2,
                "message": f"Hi {name}, I noticed we're both building in the education space. Would love to share what I've learned so far — interested in trading insights?",
            },
            {
                "variant": 3,
                "message": f"Hi {name}, I'm also building something in EdTech (still in stealth). Would value connecting with another founder navigating similar challenges.",
            },
        ]
    
    return variants[:num_variants]


def generate_followup_variants(
    prospect: Dict[str, Any],
    segment: ProspectSegment,
    step_number: int,
    num_variants: int = 2,
) -> List[Dict[str, str]]:
    """Generate follow-up variants (soft nudge style)."""
    name = prospect.get("name", "there")
    company = prospect.get("company", "")
    
    variants = []
    
    if step_number == 1:
        # First follow-up (gentle)
        variants = [
            {
                "variant": 1,
                "message": f"Hi {name}, following up on my previous message. I know you're busy, but thought this might be worth 5 minutes: [specific value]. Still interested?",
            },
            {
                "variant": 2,
                "message": f"Hi {name}, wanted to check in. I've been sharing [resource/insight] with other {segment.value.replace('_', ' ')} and getting positive feedback. Worth a quick look?",
            },
        ]
    elif step_number == 2:
        # Second follow-up (value-focused)
        variants = [
            {
                "variant": 1,
                "message": f"Hi {name}, I know inboxes get full. If this isn't the right time, no worries. But I wanted to share this one insight that might be relevant for {company}: [insight].",
            },
            {
                "variant": 2,
                "message": f"Hi {name}, last try — I have a case study that might be directly relevant. If interested, let me know. Otherwise, I'll let it go. Thanks!",
            },
        ]
    else:
        # Third follow-up (final, respectful)
        variants = [
            {
                "variant": 1,
                "message": f"Hi {name}, I understand this might not be a priority right now. If that changes, I'm here. Otherwise, I'll respect your time and step back.",
            },
        ]
    
    return variants[:num_variants]


def build_outreach_sequence(
    prospect: Dict[str, Any],
    segment: ProspectSegment,
    sequence_type: str = "3-step",
    research_insights: Optional[List[Dict[str, Any]]] = None,
) -> OutreachSequence:
    """
    Build complete outreach sequence for a prospect.
    
    Sequence types: 3-step, 5-step, 7-step, soft_nudge, direct_cta
    """
    # Generate connection request
    connection_variants = generate_connection_request_variants(prospect, segment, 3)
    
    # Generate initial DM
    dm_variants = generate_dm_variants(prospect, segment, research_insights, 3)
    
    # Generate follow-ups based on sequence type
    num_followups = {
        "3-step": 2,
        "5-step": 4,
        "7-step": 6,
        "soft_nudge": 2,
        "direct_cta": 1,
    }.get(sequence_type, 2)
    
    followup_1 = None
    followup_2 = None
    followup_3 = None
    
    if num_followups >= 1:
        followup_1_variants = generate_followup_variants(prospect, segment, 1, 2)
        followup_1 = {"variants": followup_1_variants}
    
    if num_followups >= 2:
        followup_2_variants = generate_followup_variants(prospect, segment, 2, 2)
        followup_2 = {"variants": followup_2_variants}
    
    if num_followups >= 3:
        followup_3_variants = generate_followup_variants(prospect, segment, 3, 2)
        followup_3 = {"variants": followup_3_variants}
    
    # Calculate send dates (connection request: day 0, DM: day 2, follow-ups: day 5, 10, 15)
    current_time = time.time()
    send_dates = {
        "connection_request": current_time,
        "initial_dm": current_time + (2 * 24 * 60 * 60),  # 2 days later
        "followup_1": current_time + (5 * 24 * 60 * 60),  # 5 days later
        "followup_2": current_time + (10 * 24 * 60 * 60) if num_followups >= 2 else None,
        "followup_3": current_time + (15 * 24 * 60 * 60) if num_followups >= 3 else None,
    }
    
    sequence = OutreachSequence(
        prospect_id=prospect.get("prospect_id") or prospect.get("id", ""),
        segment=segment,
        sequence_type=sequence_type,
        connection_request={"variants": connection_variants},
        initial_dm={"variants": dm_variants},
        followup_1=followup_1,
        followup_2=followup_2,
        followup_3=followup_3,
        send_dates={k: v for k, v in send_dates.items() if v},
        current_step=0,
        status=EngagementStatus.NOT_SENT,
    )
    
    return sequence


def prioritize_prospects(
    user_id: str,
    min_fit_score: int = 70,
    min_referral_capacity: int = 60,
    min_signal_strength: int = 50,
    segment: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    Prioritize prospects by scoring criteria.
    
    Returns top-tier prospects sorted by combined score.
    """
    collection = db.collection("users").document(user_id).collection("prospects")
    query = collection.where("approval_status", "==", "approved")
    
    if segment:
        query = query.where("segment", "==", segment)
    
    docs = query.get()
    prospects = []
    
    for doc in docs:
        data = doc.to_dict()
        
        # Filter by score thresholds
        fit_score = data.get("fit_score", 0) or 0
        referral_capacity = data.get("referral_capacity", 0) or 0
        signal_strength = data.get("signal_strength", 0) or 0
        
        if (fit_score >= min_fit_score and
            referral_capacity >= min_referral_capacity and
            signal_strength >= min_signal_strength):
            
            # Calculate combined priority score
            priority_score = (fit_score * 0.4) + (referral_capacity * 0.35) + (signal_strength * 0.25)
            
            prospects.append({
                **data,
                "priority_score": round(priority_score, 2),
            })
    
    # Sort by priority score (highest first)
    prospects.sort(key=lambda p: p.get("priority_score", 0), reverse=True)
    
    return prospects[:limit]

