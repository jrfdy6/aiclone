"""
Prospect Scoring Service

Multi-dimensional scoring using cached insights + Firestore research queries.
"""

from typing import Dict, Any, List, Optional
from app.services.firestore_client import db
from app.models.prospect import Prospect, CachedInsights
from app.models.research import ResearchInsight
import time


def get_research_insights(user_id: str, research_ids: List[str]) -> List[Dict[str, Any]]:
    """
    Retrieve research insights from Firestore by research IDs.
    
    Args:
        user_id: User identifier
        research_ids: List of research IDs to retrieve
        
    Returns:
        List of research insight dictionaries
    """
    insights = []
    
    for research_id in research_ids:
        try:
            doc_ref = db.collection("users").document(user_id).collection("research_insights").document(research_id)
            doc = doc_ref.get()
            
            if doc.exists:
                insights.append(doc.to_dict())
        except Exception as e:
            print(f"Error fetching research insight {research_id}: {e}", flush=True)
            continue
    
    return insights


def get_research_by_industry(user_id: str, industry: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve research insights by industry.
    
    Args:
        user_id: User identifier
        industry: Industry name
        
    Returns:
        Research insight dictionary or None
    """
    try:
        collection = db.collection("users").document(user_id).collection("research_insights")
        query = collection.where("industry", "==", industry).order_by("created_at", direction="DESCENDING").limit(1)
        docs = query.get()
        
        if docs:
            return docs[0].to_dict()
    except Exception as e:
        print(f"Error fetching research by industry {industry}: {e}", flush=True)
    
    return None


def merge_insights(cached: Optional[CachedInsights], research: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Merge cached insights with fresh research insights.
    
    Args:
        cached: Cached insights from prospect
        research: Research insights from Firestore
        
    Returns:
        Merged insights dictionary
    """
    merged = {
        "industry_trends": [],
        "trending_pains": [],
        "signal_keywords": [],
        "referral_patterns": [],
    }
    
    # Add cached insights
    if cached:
        merged["industry_trends"].extend(cached.industry_trends or [])
        merged["trending_pains"].extend(cached.trending_pains or [])
        merged["signal_keywords"].extend(cached.signal_keywords or [])
        merged["referral_patterns"].extend(cached.referral_patterns or [])
    
    # Add research insights
    if research:
        # Extract from research summary or keywords
        if research.get("keywords"):
            merged["signal_keywords"].extend(research["keywords"])
        if research.get("summary"):
            # Simple extraction - in production, use LLM to extract structured data
            summary = research["summary"].lower()
            # Look for common pain indicators
            pain_indicators = ["challenge", "problem", "struggle", "difficulty", "pain"]
            for indicator in pain_indicators:
                if indicator in summary:
                    merged["trending_pains"].append(indicator)
    
    # Remove duplicates
    for key in merged:
        merged[key] = list(set(merged[key]))
    
    return merged


def calculate_fit_score(
    prospect: Dict[str, Any],
    merged_insights: Dict[str, Any],
    audience_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Calculate multi-dimensional fit score for a prospect.
    
    Args:
        prospect: Prospect data dictionary
        merged_insights: Merged research insights
        audience_profile: Audience profile for context
        
    Returns:
        Dictionary with scores and reasoning
    """
    fit_score = 50  # Base score
    referral_capacity = 50
    signal_strength = 50
    reasoning_parts = []
    
    # Job title scoring
    job_title = prospect.get("job_title", "").lower()
    high_value_titles = ["vp", "director", "head", "chief", "founder", "ceo", "president"]
    title_score = 0
    for title in high_value_titles:
        if title in job_title:
            title_score = 30
            reasoning_parts.append(f"High-value job title: {prospect.get('job_title')}")
            break
    
    fit_score += title_score
    
    # Industry alignment
    industry = prospect.get("company", "").lower()
    if merged_insights.get("industry_trends"):
        # If industry matches research trends, boost score
        fit_score += 10
        reasoning_parts.append("Industry aligns with research trends")
    
    # Signal keywords
    signal_keywords = merged_insights.get("signal_keywords", [])
    if signal_keywords:
        # Check if prospect data contains signal keywords
        prospect_text = f"{prospect.get('company', '')} {prospect.get('job_title', '')}".lower()
        matches = sum(1 for keyword in signal_keywords if keyword.lower() in prospect_text)
        if matches > 0:
            signal_strength = min(100, 50 + (matches * 15))
            reasoning_parts.append(f"Found {matches} signal keyword(s) in prospect profile")
        else:
            signal_strength = 30
    else:
        signal_strength = 50
    
    # Referral capacity (based on job title and industry)
    if title_score > 0:
        referral_capacity = 70
    else:
        referral_capacity = 40
    
    # Audience profile alignment
    if audience_profile:
        target_pains = audience_profile.get("target_pain_points", [])
        if target_pains and merged_insights.get("trending_pains"):
            # If research pains align with target pains, boost score
            fit_score += 10
            reasoning_parts.append("Research pains align with target audience")
    
    # Clamp scores to 0-100
    fit_score = max(0, min(100, fit_score))
    referral_capacity = max(0, min(100, referral_capacity))
    signal_strength = max(0, min(100, signal_strength))
    
    # Determine best outreach angle
    outreach_angle = "Focus on industry trends and value proposition"
    if merged_insights.get("trending_pains"):
        outreach_angle = f"Address pain points: {', '.join(merged_insights['trending_pains'][:2])}"
    elif signal_keywords:
        outreach_angle = f"Leverage signal keywords: {', '.join(signal_keywords[:2])}"
    
    reasoning = ". ".join(reasoning_parts) if reasoning_parts else "Standard prospect profile"
    
    return {
        "fit_score": fit_score,
        "referral_capacity": referral_capacity,
        "signal_strength": signal_strength,
        "best_outreach_angle": outreach_angle,
        "scoring_reasoning": reasoning,
    }


def score_prospect(
    prospect: Dict[str, Any],
    user_id: str,
    audience_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Score a prospect using hybrid approach (cached + query).
    
    Args:
        prospect: Prospect data dictionary
        user_id: User identifier
        audience_profile: Audience profile for context
        
    Returns:
        Updated prospect dictionary with scores
    """
    # Get cached insights
    cached_insights = None
    if prospect.get("cached_insights"):
        cached_data = prospect["cached_insights"]
        cached_insights = CachedInsights(**cached_data) if isinstance(cached_data, dict) else cached_data
    
    # Get research insights
    research = None
    research_ids = prospect.get("linked_research_ids", [])
    
    if research_ids:
        # Query by research IDs
        research_list = get_research_insights(user_id, research_ids)
        if research_list:
            research = research_list[0]  # Use most recent
    else:
        # Try to find research by industry
        industry = prospect.get("company", "").split()[0] if prospect.get("company") else None
        if industry:
            research = get_research_by_industry(user_id, industry)
            if research:
                # Link this research to prospect
                if "linked_research_ids" not in prospect:
                    prospect["linked_research_ids"] = []
                if research.get("research_id") not in prospect["linked_research_ids"]:
                    prospect["linked_research_ids"].append(research.get("research_id"))
    
    # Merge insights
    merged_insights = merge_insights(cached_insights, research)
    
    # Calculate scores
    scores = calculate_fit_score(prospect, merged_insights, audience_profile)
    
    # Update prospect with scores
    prospect.update(scores)
    prospect["scored_at"] = time.time()
    
    # Cache key insights back to prospect
    prospect["cached_insights"] = {
        "industry_trends": merged_insights.get("industry_trends", [])[:5],  # Limit to top 5
        "trending_pains": merged_insights.get("trending_pains", [])[:5],
        "signal_keywords": merged_insights.get("signal_keywords", [])[:10],
        "referral_patterns": merged_insights.get("referral_patterns", [])[:5],
        "last_updated": time.time(),
    }
    
    return prospect


