"""
RMK Automation Service

Automates research insight ingestion with:
- Scheduled topic research
- Audience + pillar tagging
- Auto-discovery for content generation
- Immediate usability for drafts and prospecting
"""

import time
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from app.models.enhanced_research import EnhancedResearchInsight, AudienceType, InsightStatus
from app.models.linkedin_content import ContentPillar
from app.services.enhanced_research_service import (
    assign_pillar_to_topic,
    save_insight_to_firestore,
    load_insight_from_firestore,
)
from app.services.firestore_client import db

logger = logging.getLogger(__name__)


# Pillar to Audience Mapping
PILLAR_TO_AUDIENCES = {
    "referral": [
        AudienceType.PRIVATE_SCHOOL_ADMINS.value,
        AudienceType.MENTAL_HEALTH_PROFESSIONALS.value,
        AudienceType.TREATMENT_CENTERS.value,
        AudienceType.SCHOOL_COUNSELORS.value,
    ],
    "thought_leadership": [
        AudienceType.EDTECH_BUSINESS_LEADERS.value,
        AudienceType.AI_SAVVY_EXECUTIVES.value,
        AudienceType.EDUCATORS.value,
    ],
    "stealth_founder": [
        AudienceType.EARLY_ADOPTERS.value,
        AudienceType.INVESTORS.value,
        AudienceType.STEALTH_FOUNDERS.value,
    ],
}


def assign_audiences_from_pillar(pillar: str) -> List[str]:
    """
    Auto-assign audiences based on pillar.
    
    Args:
        pillar: Content pillar (referral, thought_leadership, stealth_founder)
        
    Returns:
        List of audience types
    """
    return PILLAR_TO_AUDIENCES.get(pillar.lower(), [])


def discover_insights_for_content(
    user_id: str,
    pillar: Optional[str] = None,
    topic: Optional[str] = None,
    audiences: Optional[List[str]] = None,
    limit: int = 5,
) -> List[EnhancedResearchInsight]:
    """
    Auto-discover insights ready for content generation.
    
    Queries by audience + pillar to find immediately usable insights.
    
    Args:
        user_id: User ID
        pillar: Optional pillar filter
        topic: Optional topic keyword filter
        audiences: Optional audience filter
        limit: Maximum insights to return
        
    Returns:
        List of insights ready for content generation
    """
    try:
        collection = db.collection("users").document(user_id).collection("research_insights")
        query = collection.where("status", "==", InsightStatus.READY_FOR_CONTENT_GENERATION.value)
        
        # Filter by pillar if provided
        if pillar:
            query = query.where("pillar", "==", pillar)
        
        # Filter by audience if provided
        if audiences:
            # Firestore array-contains-any query
            for audience in audiences[:1]:  # Firestore only supports one array-contains
                query = query.where("audiences", "array-contains", audience)
        
        # Order by date (most recent first)
        query = query.order_by("date_collected", direction="DESCENDING").limit(limit)
        
        docs = query.get()
        insights = []
        
        for doc in docs:
            try:
                data = doc.to_dict()
                # Additional topic filtering if needed
                if topic and topic.lower() not in data.get("topic", "").lower():
                    continue
                
                insight = load_insight_from_firestore(user_id, data.get("insight_id"))
                if insight:
                    insights.append(insight)
            except Exception as e:
                logger.warning(f"Error loading insight {doc.id}: {e}")
                continue
        
        logger.info(f"Discovered {len(insights)} insights for content generation (pillar={pillar}, audiences={audiences})")
        return insights
        
    except Exception as e:
        logger.error(f"Error discovering insights: {e}")
        return []


def auto_link_insights_to_content_generation(
    user_id: str,
    pillar: str,
    topic: Optional[str] = None,
    limit: int = 3,
) -> List[str]:
    """
    Automatically find and link relevant insights for content generation.
    
    This makes insights "immediately usable" without manual linking.
    
    Args:
        user_id: User ID
        pillar: Content pillar
        topic: Optional topic keyword
        limit: Maximum insights to link
        
    Returns:
        List of insight_ids ready for content generation
    """
    # Get audiences for this pillar
    audiences = assign_audiences_from_pillar(pillar)
    
    # Discover insights
    insights = discover_insights_for_content(
        user_id=user_id,
        pillar=pillar,
        topic=topic,
        audiences=audiences,
        limit=limit,
    )
    
    # Return insight IDs
    insight_ids = [insight.insight_id for insight in insights if insight.insight_id]
    
    logger.info(f"Auto-linked {len(insight_ids)} insights for pillar={pillar}, topic={topic}")
    return insight_ids


class ScheduledResearchTopic(BaseModel):
    """Configuration for scheduled research topics."""
    topic: str
    industry: Optional[str] = None
    pillar: Optional[str] = None
    frequency: str = Field(..., description="weekly, monthly, daily")
    enabled: bool = Field(True)


class AutomatedResearchConfig(BaseModel):
    """Configuration for automated research ingestion."""
    user_id: str
    scheduled_topics: List[ScheduledResearchTopic] = Field(default_factory=list)
    auto_run_enabled: bool = Field(True)
    default_industry: Optional[str] = None


def save_automated_config(user_id: str, config: AutomatedResearchConfig) -> None:
    """Save automated research configuration."""
    collection = db.collection("users").document(user_id).collection("rmk_config")
    doc_ref = collection.document("automated_research")
    doc_ref.set(config.model_dump())
    logger.info(f"Saved automated research config for user {user_id}")


def load_automated_config(user_id: str) -> Optional[AutomatedResearchConfig]:
    """Load automated research configuration."""
    try:
        doc_ref = db.collection("users").document(user_id).collection("rmk_config").document("automated_research")
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            return AutomatedResearchConfig(**data)
    except Exception as e:
        logger.warning(f"Error loading automated config: {e}")
    return None

