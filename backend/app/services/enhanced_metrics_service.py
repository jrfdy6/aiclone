"""
Enhanced Metrics & Learning Service

Core business logic for metrics tracking and learning pattern analysis.
"""

import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict

from app.services.firestore_client import db
from app.models.enhanced_metrics import (
    ContentMetricsDocument,
    ProspectMetricsDocument,
    LearningPattern,
    PatternType,
    SuccessMetric,
)

logger = logging.getLogger(__name__)


def calculate_engagement_rate(likes: int, comments: int, shares: int, impressions: int) -> float:
    """Calculate engagement rate: (likes + comments + shares) / impressions * 100"""
    if impressions == 0:
        return 0.0
    return round(((likes + comments + shares) / impressions) * 100, 2)


def calculate_reply_rate(dms: List[Dict[str, Any]]) -> float:
    """Calculate DM reply rate: positive_responses / total_dms_sent * 100"""
    if not dms:
        return 0.0
    
    total_dms = len(dms)
    positive_responses = sum(1 for dm in dms if dm.get("response_type") in ["positive", "neutral"])
    
    if total_dms == 0:
        return 0.0
    return round((positive_responses / total_dms) * 100, 2)


def calculate_meeting_rate(dms: List[Dict[str, Any]], meetings: List[Dict[str, Any]]) -> float:
    """Calculate meeting rate: meetings_booked / total_dms_sent * 100"""
    if not dms:
        return 0.0
    
    total_dms = len(dms)
    meetings_count = len(meetings)
    
    if total_dms == 0:
        return 0.0
    return round((meetings_count / total_dms) * 100, 2)


def save_content_metrics(
    user_id: str,
    metrics_data: Dict[str, Any],
) -> str:
    """
    Save content metrics to Firestore.
    
    Returns: metrics_id
    """
    metrics_id = f"content_metrics_{int(time.time())}_{hash(str(metrics_data))}"
    
    # Calculate engagement rate
    metrics = metrics_data.get("metrics", {})
    engagement_rate = calculate_engagement_rate(
        likes=metrics.get("likes", 0),
        comments=metrics.get("comments", 0),
        shares=metrics.get("shares", 0),
        impressions=metrics.get("impressions", 1),
    )
    
    # Create document
    doc_data = {
        "metrics_id": metrics_id,
        "user_id": user_id,
        "content_id": metrics_data.get("content_id"),
        "pillar": metrics_data.get("pillar"),
        "platform": metrics_data.get("platform"),
        "post_type": metrics_data.get("post_type"),
        "post_url": metrics_data.get("post_url"),
        "publish_date": metrics_data.get("publish_date"),
        "metrics": metrics,
        "engagement_rate": engagement_rate,
        "top_hashtags": metrics_data.get("top_hashtags", []),
        "top_mentions": metrics_data.get("top_mentions", []),
        "audience_segment": metrics_data.get("audience_segment", []),
        "notes": metrics_data.get("notes", ""),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    
    # Save to Firestore
    doc_ref = db.collection("users").document(user_id).collection("content_metrics").document(metrics_id)
    doc_ref.set(doc_data)
    
    return metrics_id


def save_prospect_metrics(
    user_id: str,
    metrics_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Save prospect metrics to Firestore.
    
    Returns: {prospect_metric_id, reply_rate, meeting_rate}
    """
    prospect_metric_id = f"prospect_metrics_{int(time.time())}_{hash(str(metrics_data))}"
    
    dm_entries = metrics_data.get("dm_sent", [])
    meeting_entries = metrics_data.get("meetings_booked", [])
    
    # Convert to dict format for Firestore
    dm_dicts = [dm.model_dump() if hasattr(dm, "model_dump") else dm for dm in dm_entries]
    meeting_dicts = [meeting.model_dump() if hasattr(meeting, "model_dump") else meeting for meeting in meeting_entries]
    
    # Calculate rates
    reply_rate = calculate_reply_rate(dm_dicts)
    meeting_rate = calculate_meeting_rate(dm_dicts, meeting_dicts)
    
    # Create document
    doc_data = {
        "prospect_metric_id": prospect_metric_id,
        "user_id": user_id,
        "prospect_id": metrics_data.get("prospect_id"),
        "sequence_id": metrics_data.get("sequence_id"),
        "connection_request_sent": metrics_data.get("connection_request_sent"),
        "connection_accepted": metrics_data.get("connection_accepted"),
        "dm_sent": dm_dicts,
        "meetings_booked": meeting_dicts,
        "score_updates": metrics_data.get("score_updates"),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    
    # Save to Firestore
    doc_ref = db.collection("users").document(user_id).collection("prospect_metrics").document(prospect_metric_id)
    doc_ref.set(doc_data)
    
    return {
        "prospect_metric_id": prospect_metric_id,
        "reply_rate": reply_rate,
        "meeting_rate": meeting_rate,
    }


def update_learning_patterns(
    user_id: str,
    pattern_types: Optional[List[PatternType]] = None,
    date_range_days: int = 30,
) -> List[LearningPattern]:
    """
    Analyze metrics and update learning patterns.
    
    Identifies top-performing:
    - Content pillars
    - Hashtags
    - Topics
    - Outreach sequences
    - Audience segments
    """
    cutoff_date = datetime.utcnow() - timedelta(days=date_range_days)
    
    patterns = []
    
    # If no pattern types specified, analyze all
    if not pattern_types:
        pattern_types = [
            PatternType.CONTENT_PILLAR,
            PatternType.HASHTAG,
            PatternType.TOPIC,
            PatternType.OUTREACH_SEQUENCE,
            PatternType.AUDIENCE_SEGMENT,
        ]
    
    # Analyze Content Pillars
    if PatternType.CONTENT_PILLAR in pattern_types:
        pillar_patterns = analyze_content_pillars(user_id, cutoff_date)
        patterns.extend(pillar_patterns)
    
    # Analyze Hashtags
    if PatternType.HASHTAG in pattern_types:
        hashtag_patterns = analyze_hashtags(user_id, cutoff_date)
        patterns.extend(hashtag_patterns)
    
    # Analyze Topics (from content drafts)
    if PatternType.TOPIC in pattern_types:
        topic_patterns = analyze_topics(user_id, cutoff_date)
        patterns.extend(topic_patterns)
    
    # Analyze Outreach Sequences
    if PatternType.OUTREACH_SEQUENCE in pattern_types:
        sequence_patterns = analyze_outreach_sequences(user_id, cutoff_date)
        patterns.extend(sequence_patterns)
    
    # Analyze Audience Segments
    if PatternType.AUDIENCE_SEGMENT in pattern_types:
        segment_patterns = analyze_audience_segments(user_id, cutoff_date)
        patterns.extend(segment_patterns)
    
    # Save patterns to Firestore
    for pattern in patterns:
        save_learning_pattern(user_id, pattern)
    
    return patterns


def analyze_content_pillars(user_id: str, cutoff_date: datetime) -> List[LearningPattern]:
    """Analyze content pillar performance."""
    patterns = []
    
    # Get content metrics
    collection = db.collection("users").document(user_id).collection("content_metrics")
    query = collection.where("created_at", ">=", cutoff_date)
    docs = query.get()
    
    pillar_performance = defaultdict(lambda: {"total_engagement": 0, "total_impressions": 0, "count": 0, "rates": []})
    
    for doc in docs:
        data = doc.to_dict()
        pillar = data.get("pillar")
        metrics = data.get("metrics", {})
        engagement_rate = data.get("engagement_rate", 0)
        
        if pillar:
            pillar_performance[pillar]["total_engagement"] += metrics.get("likes", 0) + metrics.get("comments", 0) + metrics.get("shares", 0)
            pillar_performance[pillar]["total_impressions"] += metrics.get("impressions", 1)
            pillar_performance[pillar]["count"] += 1
            pillar_performance[pillar]["rates"].append(engagement_rate)
    
    # Create patterns
    for pillar, perf in pillar_performance.items():
        avg_performance = sum(perf["rates"]) / len(perf["rates"]) if perf["rates"] else 0.0
        best_performance = max(perf["rates"]) if perf["rates"] else 0.0
        
        pattern = LearningPattern(
            pattern_id=f"pillar_{pillar}",
            user_id=user_id,
            pattern_type=PatternType.CONTENT_PILLAR,
            pattern_key=pillar,
            success_metric=SuccessMetric.ENGAGEMENT_RATE,
            average_performance=round(avg_performance, 2),
            best_performance_variant=str(best_performance),
            last_updated=datetime.utcnow(),
            sample_size=perf["count"],
            performance_history=perf["rates"][-10:],  # Last 10 data points
        )
        patterns.append(pattern)
    
    return patterns


def analyze_hashtags(user_id: str, cutoff_date: datetime) -> List[LearningPattern]:
    """Analyze hashtag performance."""
    patterns = []
    
    # Get content metrics
    collection = db.collection("users").document(user_id).collection("content_metrics")
    query = collection.where("created_at", ">=", cutoff_date)
    docs = query.get()
    
    hashtag_performance = defaultdict(lambda: {"rates": [], "count": 0})
    
    for doc in docs:
        data = doc.to_dict()
        hashtags = data.get("top_hashtags", [])
        engagement_rate = data.get("engagement_rate", 0)
        
        for hashtag in hashtags:
            hashtag_performance[hashtag]["rates"].append(engagement_rate)
            hashtag_performance[hashtag]["count"] += 1
    
    # Create patterns (top 20 hashtags)
    sorted_hashtags = sorted(hashtag_performance.items(), key=lambda x: sum(x[1]["rates"]) / len(x[1]["rates"]) if x[1]["rates"] else 0, reverse=True)[:20]
    
    for hashtag, perf in sorted_hashtags:
        avg_performance = sum(perf["rates"]) / len(perf["rates"]) if perf["rates"] else 0.0
        best_performance = max(perf["rates"]) if perf["rates"] else 0.0
        
        pattern = LearningPattern(
            pattern_id=f"hashtag_{hashtag.replace('#', '').replace(' ', '_').lower()}",
            user_id=user_id,
            pattern_type=PatternType.HASHTAG,
            pattern_key=hashtag,
            success_metric=SuccessMetric.ENGAGEMENT_RATE,
            average_performance=round(avg_performance, 2),
            best_performance_variant=str(best_performance),
            last_updated=datetime.utcnow(),
            sample_size=perf["count"],
            performance_history=perf["rates"][-10:],
        )
        patterns.append(pattern)
    
    return patterns


def analyze_topics(user_id: str, cutoff_date: datetime) -> List[LearningPattern]:
    """Analyze topic performance from content drafts."""
    patterns = []
    
    # Get content metrics linked to drafts
    metrics_collection = db.collection("users").document(user_id).collection("content_metrics")
    metrics_query = metrics_collection.where("created_at", ">=", cutoff_date)
    metrics_docs = metrics_query.get()
    
    # Get drafts collection
    drafts_collection = db.collection("users").document(user_id).collection("content_drafts")
    
    topic_performance = defaultdict(lambda: {"rates": [], "count": 0})
    
    for metrics_doc in metrics_docs:
        metrics_data = metrics_doc.to_dict()
        content_id = metrics_data.get("content_id")
        engagement_rate = metrics_data.get("engagement_rate", 0)
        
        # Get draft to find topic
        try:
            draft_doc = drafts_collection.document(content_id).get()
            if draft_doc.exists:
                draft_data = draft_doc.to_dict()
                topic = draft_data.get("topic")
                if topic:
                    topic_performance[topic]["rates"].append(engagement_rate)
                    topic_performance[topic]["count"] += 1
        except:
            pass
    
    # Create patterns (top 15 topics)
    sorted_topics = sorted(topic_performance.items(), key=lambda x: sum(x[1]["rates"]) / len(x[1]["rates"]) if x[1]["rates"] else 0, reverse=True)[:15]
    
    for topic, perf in sorted_topics:
        avg_performance = sum(perf["rates"]) / len(perf["rates"]) if perf["rates"] else 0.0
        best_performance = max(perf["rates"]) if perf["rates"] else 0.0
        
        pattern = LearningPattern(
            pattern_id=f"topic_{hash(topic) % 10000}",
            user_id=user_id,
            pattern_type=PatternType.TOPIC,
            pattern_key=topic,
            success_metric=SuccessMetric.ENGAGEMENT_RATE,
            average_performance=round(avg_performance, 2),
            best_performance_variant=str(best_performance),
            last_updated=datetime.utcnow(),
            sample_size=perf["count"],
            performance_history=perf["rates"][-10:],
        )
        patterns.append(pattern)
    
    return patterns


def analyze_outreach_sequences(user_id: str, cutoff_date: datetime) -> List[LearningPattern]:
    """Analyze outreach sequence performance."""
    patterns = []
    
    # Get prospect metrics
    collection = db.collection("users").document(user_id).collection("prospect_metrics")
    query = collection.where("created_at", ">=", cutoff_date)
    docs = query.get()
    
    sequence_performance = defaultdict(lambda: {"reply_rates": [], "meeting_rates": [], "count": 0})
    
    for doc in docs:
        data = doc.to_dict()
        sequence_id = data.get("sequence_id")
        dm_sent = data.get("dm_sent", [])
        meetings = data.get("meetings_booked", [])
        
        if sequence_id:
            reply_rate = calculate_reply_rate(dm_sent)
            meeting_rate = calculate_meeting_rate(dm_sent, meetings)
            
            sequence_performance[sequence_id]["reply_rates"].append(reply_rate)
            sequence_performance[sequence_id]["meeting_rates"].append(meeting_rate)
            sequence_performance[sequence_id]["count"] += 1
    
    # Create patterns
    for sequence_id, perf in sequence_performance.items():
        avg_reply_rate = sum(perf["reply_rates"]) / len(perf["reply_rates"]) if perf["reply_rates"] else 0.0
        avg_meeting_rate = sum(perf["meeting_rates"]) / len(perf["meeting_rates"]) if perf["meeting_rates"] else 0.0
        
        # Use meeting rate as primary metric
        pattern = LearningPattern(
            pattern_id=f"sequence_{sequence_id}",
            user_id=user_id,
            pattern_type=PatternType.OUTREACH_SEQUENCE,
            pattern_key=sequence_id,
            success_metric=SuccessMetric.MEETING_RATE,
            average_performance=round(avg_meeting_rate, 2),
            best_performance_variant=str(max(perf["meeting_rates"]) if perf["meeting_rates"] else 0.0),
            last_updated=datetime.utcnow(),
            sample_size=perf["count"],
            performance_history=perf["meeting_rates"][-10:],
        )
        patterns.append(pattern)
    
    return patterns


def analyze_audience_segments(user_id: str, cutoff_date: datetime) -> List[LearningPattern]:
    """Analyze audience segment performance."""
    patterns = []
    
    # Get content metrics
    collection = db.collection("users").document(user_id).collection("content_metrics")
    query = collection.where("created_at", ">=", cutoff_date)
    docs = query.get()
    
    segment_performance = defaultdict(lambda: {"rates": [], "count": 0})
    
    for doc in docs:
        data = doc.to_dict()
        segments = data.get("audience_segment", [])
        engagement_rate = data.get("engagement_rate", 0)
        
        for segment in segments:
            segment_performance[segment]["rates"].append(engagement_rate)
            segment_performance[segment]["count"] += 1
    
    # Create patterns
    for segment, perf in segment_performance.items():
        avg_performance = sum(perf["rates"]) / len(perf["rates"]) if perf["rates"] else 0.0
        best_performance = max(perf["rates"]) if perf["rates"] else 0.0
        
        pattern = LearningPattern(
            pattern_id=f"segment_{segment.replace(' ', '_').lower()}",
            user_id=user_id,
            pattern_type=PatternType.AUDIENCE_SEGMENT,
            pattern_key=segment,
            success_metric=SuccessMetric.ENGAGEMENT_RATE,
            average_performance=round(avg_performance, 2),
            best_performance_variant=str(best_performance),
            last_updated=datetime.utcnow(),
            sample_size=perf["count"],
            performance_history=perf["rates"][-10:],
        )
        patterns.append(pattern)
    
    return patterns


def save_learning_pattern(user_id: str, pattern: LearningPattern) -> None:
    """Save learning pattern to Firestore."""
    doc_ref = db.collection("users").document(user_id).collection("learning_patterns").document(pattern.pattern_id)
    doc_ref.set(pattern.model_dump())


def generate_recommendations(
    user_id: str,
    week_start: datetime,
    week_end: datetime,
) -> List[str]:
    """
    Generate recommendations based on learning patterns.
    
    Returns actionable recommendations for content and outreach optimization.
    """
    recommendations = []
    
    # Get learning patterns
    patterns_collection = db.collection("users").document(user_id).collection("learning_patterns")
    patterns_docs = patterns_collection.order_by("average_performance", direction="DESCENDING").limit(50).get()
    
    # Analyze patterns
    best_pillar = None
    best_pillar_perf = 0.0
    best_hashtags = []
    best_segments = []
    
    for doc in patterns_docs:
        pattern_data = doc.to_dict()
        pattern_type = pattern_data.get("pattern_type")
        pattern_key = pattern_data.get("pattern_key")
        avg_perf = pattern_data.get("average_performance", 0.0)
        
        if pattern_type == "content_pillar" and avg_perf > best_pillar_perf:
            best_pillar = pattern_key
            best_pillar_perf = avg_perf
        
        elif pattern_type == "hashtag" and len(best_hashtags) < 5:
            best_hashtags.append(pattern_key)
        
        elif pattern_type == "audience_segment" and len(best_segments) < 3:
            best_segments.append(pattern_key)
    
    # Generate recommendations
    if best_pillar:
        recommendations.append(f"Increase {best_pillar} posts (currently performing at {best_pillar_perf:.1f}% engagement)")
    
    if best_segments:
        recommendations.append(f"Target {', '.join(best_segments[:2])} audience segments for higher engagement")
    
    if best_hashtags:
        recommendations.append(f"Use top-performing hashtags: {', '.join(best_hashtags[:3])}")
    
    # Add outreach recommendations
    # (Check prospect metrics for outreach patterns)
    prospect_collection = db.collection("users").document(user_id).collection("prospect_metrics")
    prospect_query = prospect_collection.where("created_at", ">=", week_start).where("created_at", "<=", week_end)
    prospect_docs = prospect_query.get()
    
    if prospect_docs:
        total_dms = sum(len(doc.to_dict().get("dm_sent", [])) for doc in prospect_docs)
        total_meetings = sum(len(doc.to_dict().get("meetings_booked", [])) for doc in prospect_docs)
        
        if total_dms > 0:
            meeting_rate = (total_meetings / total_dms) * 100
            if meeting_rate < 5:
                recommendations.append("Meeting rate is below target (5%). Test new outreach message variants for EdTech leads")
    
    return recommendations

