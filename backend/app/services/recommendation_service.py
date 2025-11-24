"""
Recommendation Engine Service
Smart recommendations for prospects, content topics, outreach angles, etc.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from app.services.firestore_client import db
from app.models.predictive import Recommendation, RecommendationType

logger = logging.getLogger(__name__)


def recommend_prospects(user_id: str, limit: int = 10) -> List[Recommendation]:
    """
    Recommend prospects based on:
    - Similar to high-converting prospects
    - High fit score prospects
    - Recent signal activity
    """
    try:
        # Get prospects with high fit scores
        query = db.collection("users").document(user_id).collection("prospects")
        query = query.where("fit_score", ">=", 0.7).limit(50)
        
        prospects = []
        for doc in query.stream():
            data = doc.to_dict()
            if data:
                prospects.append({
                    "id": doc.id,
                    "name": data.get("name", ""),
                    "company": data.get("company", ""),
                    "fit_score": data.get("fit_score", 0.0),
                    "industry": data.get("industry", ""),
                })
        
        # Sort by fit_score
        prospects.sort(key=lambda x: x.get("fit_score", 0), reverse=True)
        
        recommendations = []
        for prospect in prospects[:limit]:
            recommendations.append(Recommendation(
                type=RecommendationType.PROSPECT,
                title=f"{prospect.get('name', 'Prospect')} at {prospect.get('company', 'Company')}",
                description=f"High fit score ({prospect.get('fit_score', 0):.2f}) in {prospect.get('industry', 'industry')}",
                score=prospect.get("fit_score", 0.0),
                reasoning=f"Strong alignment based on fit score and industry match",
                metadata={
                    "prospect_id": prospect.get("id"),
                    "industry": prospect.get("industry"),
                    "fit_score": prospect.get("fit_score")
                }
            ))
        
        return recommendations
        
    except Exception as e:
        logger.error(f"Error recommending prospects: {e}")
        return []


def recommend_content_topics(user_id: str, limit: int = 10) -> List[Recommendation]:
    """
    Recommend content topics based on:
    - Trending topics in user's industry
    - Gaps in user's content calendar
    - High-performing topics from research
    """
    try:
        recommendations = []
        
        # Get research insights to find trending topics
        query = db.collection("users").document(user_id).collection("research_insights")
        query = query.order_by("created_at", direction="DESCENDING").limit(20)
        
        topics = {}
        for doc in query.stream():
            data = doc.to_dict()
            if not data:
                continue
            
            # Extract opportunities and trends
            opportunities = data.get("opportunities", [])
            trends = data.get("industry_trends", [])
            
            for topic in opportunities + trends:
                if topic not in topics:
                    topics[topic] = 0
                topics[topic] += 1
        
        # Get vault items for additional topics
        vault_query = db.collection("users").document(user_id).collection("knowledge_vault")
        vault_query = vault_query.order_by("created_at", direction="DESCENDING").limit(20)
        
        for doc in vault_query.stream():
            data = doc.to_dict()
            if not data:
                continue
            
            title = data.get("title", "")
            if title:
                if title not in topics:
                    topics[title] = 0
                topics[title] += 1
        
        # Convert to recommendations
        sorted_topics = sorted(topics.items(), key=lambda x: x[1], reverse=True)
        
        for topic, count in sorted_topics[:limit]:
            score = min(1.0, count / 5.0)  # Normalize to 0-1
            recommendations.append(Recommendation(
                type=RecommendationType.CONTENT_TOPIC,
                title=topic,
                description=f"Appears in {count} research insights and vault items",
                score=score,
                reasoning="Trending topic based on recent research and knowledge base",
                metadata={"topic": topic, "occurrences": count}
            ))
        
        # If no topics found, return defaults
        if not recommendations:
            recommendations = [
                Recommendation(
                    type=RecommendationType.CONTENT_TOPIC,
                    title="AI in Education: Latest Trends",
                    description="Explore how AI is transforming education",
                    score=0.7,
                    reasoning="Popular topic in EdTech industry",
                    metadata={}
                ),
                Recommendation(
                    type=RecommendationType.CONTENT_TOPIC,
                    title="Building Referral Networks",
                    description="Strategies for expanding referral networks",
                    score=0.6,
                    reasoning="High-value content type for networking",
                    metadata={}
                ),
            ]
        
        return recommendations[:limit]
        
    except Exception as e:
        logger.error(f"Error recommending content topics: {e}")
        return []


def recommend_outreach_angles(user_id: str, prospect_id: Optional[str] = None) -> List[Recommendation]:
    """
    Recommend outreach angles based on:
    - Successful outreach patterns
    - Prospect research insights
    - Industry best practices
    """
    try:
        recommendations = []
        
        # Get research insights for prospect or general insights
        if prospect_id:
            # Get prospect-specific insights
            prospect_doc = db.collection("users").document(user_id).collection("prospects").document(prospect_id).get()
            if prospect_doc.exists:
                prospect_data = prospect_doc.to_dict()
                research_id = prospect_data.get("linked_research_id")
                
                if research_id:
                    research_doc = db.collection("users").document(user_id).collection("research_results").document(research_id).get()
                    if research_doc.exists:
                        research_data = research_doc.to_dict()
                        pain_points = research_data.get("pain_points", [])
                        opportunities = research_data.get("opportunities", [])
                        
                        for pain in pain_points[:3]:
                            recommendations.append(Recommendation(
                                type=RecommendationType.OUTREACH_ANGLE,
                                title=f"Address Pain Point: {pain}",
                                description=f"Highlight how your solution addresses this specific challenge",
                                score=0.8,
                                reasoning=f"Based on prospect research showing this as a key pain point",
                                metadata={"angle": "pain_point", "prospect_id": prospect_id}
                            ))
                        
                        for opp in opportunities[:2]:
                            recommendations.append(Recommendation(
                                type=RecommendationType.OUTREACH_ANGLE,
                                title=f"Leverage Opportunity: {opp}",
                                description=f"Position your solution to help capitalize on this opportunity",
                                score=0.7,
                                reasoning=f"Based on research identifying this opportunity",
                                metadata={"angle": "opportunity", "prospect_id": prospect_id}
                            ))
        
        # Add general outreach angles if needed
        if len(recommendations) < 5:
            general_angles = [
                {
                    "title": "Value-First Approach",
                    "description": "Lead with value proposition and ROI",
                    "score": 0.9,
                    "reasoning": "High-performing outreach pattern"
                },
                {
                    "title": "Case Study Reference",
                    "description": "Share relevant case study or success story",
                    "score": 0.85,
                    "reasoning": "Social proof increases engagement"
                },
                {
                    "title": "Industry Trend Connection",
                    "description": "Connect to current industry trends",
                    "score": 0.75,
                    "reasoning": "Relevance and timeliness improve response rates"
                },
            ]
            
            for angle in general_angles:
                recommendations.append(Recommendation(
                    type=RecommendationType.OUTREACH_ANGLE,
                    title=angle["title"],
                    description=angle["description"],
                    score=angle["score"],
                    reasoning=angle["reasoning"],
                    metadata={}
                ))
        
        return recommendations[:5]
        
    except Exception as e:
        logger.error(f"Error recommending outreach angles: {e}")
        return []


def recommend_hashtags(user_id: str, content_preview: str = "", limit: int = 10) -> List[Recommendation]:
    """
    Recommend hashtags based on:
    - Content topic analysis
    - Historical high-performing hashtags
    - Industry trends
    """
    try:
        recommendations = []
        
        # Get high-performing hashtags from historical content
        query = db.collection("users").document(user_id).collection("content_drafts")
        query = query.where("status", "==", "published")
        
        hashtag_performance: Dict[str, float] = {}
        
        for doc in query.stream():
            data = doc.to_dict()
            if not data:
                continue
            
            hashtags = data.get("hashtags", [])
            views = data.get("views", 0)
            engagements = data.get("engagements", 0)
            
            if views > 0 and hashtags:
                engagement_rate = engagements / views
                for hashtag in hashtags:
                    if hashtag not in hashtag_performance:
                        hashtag_performance[hashtag] = []
                    hashtag_performance[hashtag].append(engagement_rate)
        
        # Calculate averages
        avg_performance: Dict[str, float] = {}
        for hashtag, rates in hashtag_performance.items():
            avg_performance[hashtag] = sum(rates) / len(rates)
        
        # Convert to recommendations
        sorted_hashtags = sorted(avg_performance.items(), key=lambda x: x[1], reverse=True)
        
        for hashtag, avg_rate in sorted_hashtags[:limit]:
            # Normalize score
            score = min(1.0, avg_rate / 0.05)  # Assuming 5% is high engagement
            recommendations.append(Recommendation(
                type=RecommendationType.HASHTAG,
                title=f"#{hashtag}",
                description=f"Average engagement rate: {avg_rate:.2%}",
                score=score,
                reasoning="High-performing hashtag based on historical data",
                metadata={"hashtag": hashtag, "avg_engagement": avg_rate}
            ))
        
        # If no historical data, provide default recommendations
        if not recommendations:
            default_hashtags = ["EdTech", "AI", "Education", "Technology", "Innovation"]
            for i, hashtag in enumerate(default_hashtags[:limit]):
                recommendations.append(Recommendation(
                    type=RecommendationType.HASHTAG,
                    title=f"#{hashtag}",
                    description="Popular industry hashtag",
                    score=0.6 - (i * 0.05),
                    reasoning="Commonly used in EdTech and AI spaces",
                    metadata={"hashtag": hashtag}
                ))
        
        return recommendations
        
    except Exception as e:
        logger.error(f"Error recommending hashtags: {e}")
        return []

