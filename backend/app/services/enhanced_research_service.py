"""
Enhanced Research & Knowledge Management Service

Multi-source research pipeline with:
- Perplexity research
- Firecrawl scraping
- Google Custom Search
- Prospect extraction
- Normalization and deduplication
- Free-tier optimizations
"""

import hashlib
import time
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from app.models.enhanced_research import (
    EnhancedResearchInsight,
    ResearchSourceDetail,
    ProspectTarget,
    EngagementSignals,
    InsightStatus,
    SourceType,
)
from app.services.perplexity_client import get_perplexity_client
from app.services.firecrawl_client import get_firecrawl_client
from app.services.search_client import get_search_client
from app.services.firestore_client import db
from app.models.linkedin_content import ContentPillar

logger = logging.getLogger(__name__)


def assign_pillar_to_topic(topic: str, industry: Optional[str] = None) -> str:
    """
    Auto-assign content pillar based on topic keywords.
    
    Returns: "referral", "thought_leadership", or "stealth_founder"
    """
    topic_lower = topic.lower()
    
    # Referral keywords
    referral_keywords = ["referral", "partner", "school", "mental health", "treatment", "support", "network"]
    if any(kw in topic_lower for kw in referral_keywords):
        return "referral"
    
    # Stealth founder keywords
    stealth_keywords = ["startup", "founder", "investor", "early adopter", "stealth", "building"]
    if any(kw in topic_lower for kw in stealth_keywords):
        return "stealth_founder"
    
    # Default to thought leadership
    return "thought_leadership"


async def collect_perplexity_source(
    topic: str,
    max_key_points: int = 5,
) -> Optional[ResearchSourceDetail]:
    """Collect research from Perplexity."""
    try:
        perplexity = get_perplexity_client()
        research_result = perplexity.research_topic(
            topic=topic,
            num_results=3,
            include_comparison=False,
        )
        
        summary = research_result.get("summary", "")
        sources = research_result.get("sources", [])
        source_url = sources[0].get("url", "") if sources else ""
        
        # Extract key points (simple extraction - in production use LLM)
        key_points = []
        sentences = summary.split(". ")
        key_points = [s.strip() for s in sentences[:max_key_points] if len(s) > 50]
        
        return ResearchSourceDetail(
            type=SourceType.PERPLEXITY,
            source_name="Perplexity AI",
            summary=summary[:500],  # Limit length
            key_points=key_points,
            source_url=source_url or "https://perplexity.ai",
            date_collected=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:
        logger.warning(f"Perplexity collection failed: {e}")
        return None


async def collect_firecrawl_source(
    url: str,
    topic: str,
) -> Optional[ResearchSourceDetail]:
    """Collect research from Firecrawl scraping."""
    try:
        firecrawl = get_firecrawl_client()
        scraped = firecrawl.scrape_url(url)
        
        # Extract key points (simple extraction)
        content = scraped.content or scraped.markdown or ""
        sentences = content.split(". ")
        key_points = [s.strip() for s in sentences[:5] if len(s) > 50 and len(s) < 200]
        
        return ResearchSourceDetail(
            type=SourceType.FIRECRAWL,
            source_name=scraped.title or "Scraped Content",
            summary=content[:500],
            key_points=key_points[:5],
            source_url=url,
            date_collected=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:
        logger.warning(f"Firecrawl collection failed for {url}: {e}")
        return None


async def collect_google_search_sources(
    topic: str,
    max_results: int = 5,
) -> List[ResearchSourceDetail]:
    """Collect research from Google Custom Search."""
    sources = []
    try:
        search_client = get_search_client()
        results = search_client.search(
            query=topic,
            num_results=max_results,
        )
        
        for result in results[:max_results]:
            # Extract key points from snippet
            snippet = result.snippet
            key_points = []
            if snippet:
                sentences = snippet.split(". ")
                key_points = [s.strip() for s in sentences if len(s) > 30]
            
            sources.append(ResearchSourceDetail(
                type=SourceType.GOOGLE_CUSTOM_SEARCH,
                source_name=result.title or "Google Search Result",
                summary=snippet[:500],
                key_points=key_points[:3],
                source_url=result.link,
                date_collected=datetime.now(timezone.utc).isoformat(),
            ))
    except Exception as e:
        logger.warning(f"Google Custom Search collection failed: {e}")
    
    return sources


def extract_prospect_targets(
    sources: List[ResearchSourceDetail],
    topic: str,
    pillar: str,
) -> List[ProspectTarget]:
    """
    Extract prospect targets from research sources.
    
    Uses simple pattern matching. In production, use LLM for better extraction.
    """
    prospects = []
    
    # Keywords that indicate prospect mentions
    role_keywords = ["director", "vp", "vp of", "chief", "head of", "founder", "ceo", "president"]
    org_keywords = ["school", "institute", "company", "startup", "organization", "district"]
    
    for source in sources:
        text = f"{source.summary} {' '.join(source.key_points)}"
        text_lower = text.lower()
        
        # Simple extraction (in production, use LLM or NER)
        # Look for patterns like "John Doe, Director of..."
        sentences = text.split(". ")
        
        for sentence in sentences:
            # Check if sentence contains role keywords
            if any(role in sentence.lower() for role in role_keywords):
                # Try to extract name and role (simplified)
                # In production, use proper NLP/LLM extraction
                words = sentence.split()
                
                # Look for capitalized names followed by role
                for i, word in enumerate(words):
                    if word[0].isupper() and i < len(words) - 1:
                        next_word = words[i + 1] if i + 1 < len(words) else ""
                        if any(role in next_word.lower() for role in role_keywords):
                            # Potential prospect found (simplified extraction)
                            name = word  # Simplified - just first word
                            role_start_idx = i + 1
                            role = " ".join(words[role_start_idx:role_start_idx + 3])
                            
                            # Extract organization if mentioned
                            org = ""
                            for org_kw in org_keywords:
                                if org_kw in text_lower:
                                    # Find organization name (simplified)
                                    org = "Organization"  # Placeholder
                            
                            prospects.append(ProspectTarget(
                                name=name,
                                role=role[:100],  # Limit length
                                organization=org or "Unknown",
                                pillar_relevance=[pillar],
                                relevance_score=0.7,  # Default score
                            ))
                            break
    
    # Deduplicate by name (simplified)
    seen_names = set()
    unique_prospects = []
    for prospect in prospects:
        if prospect.name not in seen_names:
            seen_names.add(prospect.name)
            unique_prospects.append(prospect)
    
    return unique_prospects[:10]  # Limit to 10 prospects


def normalize_insight(
    insight: EnhancedResearchInsight,
) -> EnhancedResearchInsight:
    """
    Normalize and deduplicate insight.
    
    - Deduplicate key points across sources
    - Normalize tags
    - Merge similar sources
    """
    # Collect all key points
    all_key_points = []
    for source in insight.sources:
        all_key_points.extend(source.key_points)
    
    # Deduplicate key points (simple approach - in production use semantic similarity)
    seen_points = set()
    normalized_key_points = []
    
    for point in all_key_points:
        # Simple hash-based deduplication
        point_lower = point.lower().strip()
        point_hash = hashlib.md5(point_lower.encode()).hexdigest()
        
        if point_hash not in seen_points:
            seen_points.add(point_hash)
            normalized_key_points.append(point)
    
    # Normalize tags (deduplicate and sort)
    normalized_tags = sorted(list(set([tag.lower().strip() for tag in insight.tags])))
    
    # Update insight
    insight.normalized_key_points = normalized_key_points[:20]  # Limit
    insight.normalized_tags = normalized_tags
    
    # Create deduplication hash
    content_hash = hashlib.md5(
        f"{insight.topic}{''.join(normalized_key_points)}".encode()
    ).hexdigest()
    insight.deduplication_hash = content_hash
    
    return insight


def calculate_engagement_signals(
    sources: List[ResearchSourceDetail],
    prospect_targets: List[ProspectTarget],
    topic: str,
) -> EngagementSignals:
    """
    Calculate engagement signals (relevance, trend, urgency scores).
    
    Simple heuristic-based approach. In production, use ML model.
    """
    # Relevance: based on number of sources and key points
    relevance_score = min(1.0, (len(sources) * 0.2) + (len(prospect_targets) * 0.1))
    
    # Trend: based on recent dates and keyword frequency
    recent_count = sum(1 for s in sources if "2024" in s.date_collected or "2025" in s.date_collected)
    trend_score = min(1.0, (recent_count / max(len(sources), 1)) * 0.8)
    
    # Urgency: based on prospect count and relevance
    urgency_score = min(1.0, len(prospect_targets) * 0.15) if prospect_targets else None
    
    return EngagementSignals(
        relevance_score=round(relevance_score, 2),
        trend_score=round(trend_score, 2),
        urgency_score=round(urgency_score, 2) if urgency_score else None,
    )


def assign_audiences_to_insight(insight: EnhancedResearchInsight) -> EnhancedResearchInsight:
    """Auto-assign audiences based on pillar."""
    from app.services.rmk_automation import assign_audiences_from_pillar
    
    if insight.pillar and not insight.audiences:
        insight.audiences = assign_audiences_from_pillar(insight.pillar)
    
    return insight


def save_insight_to_firestore(insight: EnhancedResearchInsight) -> str:
    """Save enhanced research insight to Firestore."""
    if not insight.insight_id:
        insight.insight_id = f"insight_{int(time.time())}"
    
    # Auto-assign audiences if not set
    insight = assign_audiences_to_insight(insight)
    
    collection = db.collection("users").document(insight.user_id).collection("research_insights")
    doc_ref = collection.document(insight.insight_id)
    
    # Convert to Firestore-compatible format
    doc_data = {
        "user_id": insight.user_id,
        "insight_id": insight.insight_id,
        "topic": insight.topic,
        "pillar": insight.pillar,
        "audiences": insight.audiences,  # Add audiences field
        "sources": [
            {
                "type": source.type,
                "source_name": source.source_name,
                "summary": source.summary,
                "key_points": source.key_points,
                "source_url": source.source_url,
                "date_collected": source.date_collected,
            }
            for source in insight.sources
        ],
        "prospect_targets": [
            {
                "name": prospect.name,
                "role": prospect.role,
                "organization": prospect.organization,
                "contact_url": prospect.contact_url,
                "pillar_relevance": prospect.pillar_relevance,
                "relevance_score": prospect.relevance_score,
            }
            for prospect in insight.prospect_targets
        ],
        "tags": insight.tags,
        "engagement_signals": {
            "relevance_score": insight.engagement_signals.relevance_score,
            "trend_score": insight.engagement_signals.trend_score,
            "urgency_score": insight.engagement_signals.urgency_score,
        },
        "date_collected": insight.date_collected,
        "status": insight.status,
        "linked_research_ids": insight.linked_research_ids,
        "normalized_key_points": insight.normalized_key_points,
        "normalized_tags": insight.normalized_tags,
        "deduplication_hash": insight.deduplication_hash,
    }
    
    doc_ref.set(doc_data)
    logger.info(f"Saved insight {insight.insight_id} to Firestore")
    
    return insight.insight_id


def load_insight_from_firestore(user_id: str, insight_id: str) -> Optional[EnhancedResearchInsight]:
    """Load enhanced research insight from Firestore."""
    try:
        doc_ref = db.collection("users").document(user_id).collection("research_insights").document(insight_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return None
        
        data = doc.to_dict()
        
        # Reconstruct insight object
        insight = EnhancedResearchInsight(
            user_id=data["user_id"],
            insight_id=data["insight_id"],
            topic=data["topic"],
            pillar=data.get("pillar"),
            sources=[
                ResearchSourceDetail(**source_data)
                for source_data in data.get("sources", [])
            ],
            prospect_targets=[
                ProspectTarget(**prospect_data)
                for prospect_data in data.get("prospect_targets", [])
            ],
            tags=data.get("tags", []),
            engagement_signals=EngagementSignals(**data.get("engagement_signals", {})),
            date_collected=data["date_collected"],
            status=data.get("status", InsightStatus.COLLECTING),
            linked_research_ids=data.get("linked_research_ids", []),
            normalized_key_points=data.get("normalized_key_points", []),
            normalized_tags=data.get("normalized_tags", []),
            deduplication_hash=data.get("deduplication_hash"),
        )
        
        return insight
    except Exception as e:
        logger.error(f"Error loading insight {insight_id}: {e}")
        return None

