"""
Predictive Analytics Service
ML-based predictions for conversions, content performance, etc.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from app.services.firestore_client import db
from app.models.predictive import (
    ConversionPrediction, ContentEngagementPrediction,
    OptimalPostingTime, PredictionType
)

logger = logging.getLogger(__name__)


def predict_prospect_conversion(prospect_data: Dict[str, Any]) -> ConversionPrediction:
    """
    Predict prospect conversion probability based on features.
    
    Features considered:
    - fit_score, referral_capacity, signal_strength
    - Industry, job_title
    - Engagement history
    - Outreach response rates
    """
    # Extract features
    fit_score = prospect_data.get("fit_score", 0.0)
    referral_capacity = prospect_data.get("referral_capacity", 0.0)
    signal_strength = prospect_data.get("signal_strength", 0.0)
    
    # Simple weighted model (can be replaced with ML model)
    base_score = (fit_score * 0.4 + referral_capacity * 0.3 + signal_strength * 0.3)
    
    # Adjust based on industry (if available)
    industry = prospect_data.get("industry", "")
    industry_multiplier = 1.0
    high_conversion_industries = ["education", "edtech", "healthcare", "technology"]
    if industry.lower() in high_conversion_industries:
        industry_multiplier = 1.2
    
    # Calculate probability
    conversion_probability = min(0.95, base_score * industry_multiplier)
    
    # Confidence based on data completeness
    confidence = 0.7  # Default confidence
    if all([fit_score, referral_capacity, signal_strength, industry]):
        confidence = 0.9
    
    # Key factors
    key_factors = []
    if fit_score > 0.7:
        key_factors.append("High fit score indicates strong alignment")
    if referral_capacity > 0.6:
        key_factors.append("Good referral network potential")
    if signal_strength > 0.7:
        key_factors.append("Strong buying signals detected")
    
    # Recommended actions
    recommended_actions = []
    if conversion_probability < 0.5:
        recommended_actions.append("Gather more information about prospect needs")
        recommended_actions.append("Focus on building relationship before pitch")
    elif conversion_probability < 0.7:
        recommended_actions.append("Schedule a discovery call")
        recommended_actions.append("Share relevant case studies")
    else:
        recommended_actions.append("Move to proposal stage")
        recommended_actions.append("Prepare custom demo")
    
    return ConversionPrediction(
        prospect_id=prospect_data.get("id", ""),
        conversion_probability=conversion_probability,
        confidence=confidence,
        key_factors=key_factors,
        recommended_actions=recommended_actions
    )


def predict_content_engagement(content_data: Dict[str, Any], user_id: str) -> ContentEngagementPrediction:
    """
    Predict content engagement based on:
    - Content length
    - Hashtags
    - Pillar type
    - Historical performance
    - Posting time
    """
    content_preview = content_data.get("content", "")[:200]
    content_length = len(content_data.get("content", ""))
    pillar = content_data.get("pillar", "")
    hashtags = content_data.get("hashtags", [])
    
    # Base engagement rate
    base_engagement = 0.03  # 3% baseline
    
    # Adjust for content length (optimal: 500-1500 chars)
    if 500 <= content_length <= 1500:
        base_engagement *= 1.3
    elif content_length > 2000:
        base_engagement *= 0.8
    
    # Adjust for pillar type
    pillar_multipliers = {
        "referral": 1.2,
        "thought_leadership": 1.1,
        "stealth_founder": 1.0
    }
    base_engagement *= pillar_multipliers.get(pillar, 1.0)
    
    # Get historical performance for this user
    try:
        # Query recent content drafts for this user
        query = db.collection("users").document(user_id).collection("content_drafts")
        query = query.where("status", "==", "published").limit(10)
        docs = query.stream()
        
        total_engagement = 0
        count = 0
        for doc in docs:
            data = doc.to_dict()
            if data:
                views = data.get("views", 0)
                engagements = data.get("engagements", 0)
                if views > 0:
                    total_engagement += engagements / views
                    count += 1
        
        if count > 0:
            avg_engagement = total_engagement / count
            # Blend with historical average
            base_engagement = (base_engagement * 0.6 + avg_engagement * 0.4)
    except Exception as e:
        logger.warning(f"Could not fetch historical data: {e}")
    
    # Confidence based on data available
    confidence = 0.6
    if content_length > 100 and pillar:
        confidence = 0.8
    if hashtags:
        confidence = 0.85
    
    # Recommended improvements
    improvements = []
    if content_length < 300:
        improvements.append("Consider adding more detail (optimal: 500-1500 characters)")
    if not hashtags or len(hashtags) < 3:
        improvements.append("Add 3-5 relevant hashtags for better reach")
    if not pillar:
        improvements.append("Categorize content by pillar for better targeting")
    
    # Optimal hashtags suggestion (simple - can be enhanced with ML)
    optimal_hashtags = hashtags[:5] if hashtags else []
    
    return ContentEngagementPrediction(
        content_id=content_data.get("id"),
        content_preview=content_preview,
        predicted_engagement_rate=base_engagement,
        predicted_views=int(1000 * base_engagement / 0.03) if base_engagement > 0 else None,
        confidence=confidence,
        recommended_improvements=improvements,
        optimal_hashtags=optimal_hashtags
    )


def predict_optimal_posting_time(user_id: str) -> List[OptimalPostingTime]:
    """
    Predict optimal posting times based on historical engagement.
    """
    try:
        # Get historical content performance
        query = db.collection("users").document(user_id).collection("content_drafts")
        query = query.where("status", "==", "published")
        docs = query.stream()
        
        # Aggregate engagement by day/hour
        engagement_by_time: Dict[tuple, float] = {}  # (day_of_week, hour) -> avg_engagement
        
        for doc in docs:
            data = doc.to_dict()
            if not data:
                continue
            
            scheduled_at = data.get("scheduled_at") or data.get("created_at")
            if not scheduled_at:
                continue
            
            try:
                dt = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
                day_of_week = dt.strftime("%A")
                hour = dt.hour
                
                views = data.get("views", 0)
                engagements = data.get("engagements", 0)
                if views > 0:
                    engagement_rate = engagements / views
                    key = (day_of_week, hour)
                    if key not in engagement_by_time:
                        engagement_by_time[key] = []
                    engagement_by_time[key].append(engagement_rate)
            except Exception as e:
                logger.warning(f"Error parsing date: {e}")
                continue
        
        # Calculate averages
        avg_by_time: Dict[tuple, float] = {}
        for key, rates in engagement_by_time.items():
            avg_by_time[key] = sum(rates) / len(rates)
        
        # If no historical data, return defaults
        if not avg_by_time:
            return [
                OptimalPostingTime(day_of_week="Tuesday", hour=9, predicted_engagement_multiplier=1.2),
                OptimalPostingTime(day_of_week="Wednesday", hour=10, predicted_engagement_multiplier=1.15),
                OptimalPostingTime(day_of_week="Thursday", hour=11, predicted_engagement_multiplier=1.1),
            ]
        
        # Calculate overall average
        overall_avg = sum(avg_by_time.values()) / len(avg_by_time) if avg_by_time else 1.0
        
        # Get top times
        sorted_times = sorted(avg_by_time.items(), key=lambda x: x[1], reverse=True)[:5]
        
        results = []
        for (day, hour), engagement_rate in sorted_times:
            multiplier = engagement_rate / overall_avg if overall_avg > 0 else 1.0
            results.append(OptimalPostingTime(
                day_of_week=day,
                hour=hour,
                predicted_engagement_multiplier=multiplier
            ))
        
        return results
        
    except Exception as e:
        logger.error(f"Error predicting optimal posting time: {e}")
        # Return defaults
        return [
            OptimalPostingTime(day_of_week="Tuesday", hour=9, predicted_engagement_multiplier=1.2),
        ]

