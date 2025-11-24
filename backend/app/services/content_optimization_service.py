"""
Content Optimization Service
A/B testing, content scoring, sentiment analysis for content optimization
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.services.firestore_client import db
from app.services.nlp_service import analyze_sentiment

logger = logging.getLogger(__name__)


class ContentScore:
    """Content quality score components"""
    def __init__(self):
        self.scores = {}
        self.total_score = 0.0
        self.max_score = 100.0
    
    def add_score(self, component: str, score: float, weight: float = 1.0):
        """Add a score component"""
        self.scores[component] = {"score": score, "weight": weight}
        self.total_score += score * weight
        self.max_score += weight * 100
    
    def get_total(self) -> float:
        """Get total weighted score"""
        return (self.total_score / self.max_score * 100) if self.max_score > 0 else 0


def score_content_quality(content: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Score content quality based on multiple factors:
    - Length (optimal: 500-1500 chars)
    - Readability
    - Hashtags (optimal: 3-5)
    - Engagement potential
    - Brand voice consistency
    """
    metadata = metadata or {}
    content_length = len(content)
    
    score = ContentScore()
    improvements = []
    
    # Length score
    if 500 <= content_length <= 1500:
        length_score = 100
    elif 300 <= content_length < 500:
        length_score = 70
        improvements.append("Consider adding more detail (optimal: 500-1500 characters)")
    elif 1500 < content_length <= 2500:
        length_score = 80
        improvements.append("Content is slightly long - consider condensing")
    elif content_length > 2500:
        length_score = 50
        improvements.append("Content is too long - consider breaking into multiple posts")
    else:
        length_score = 40
        improvements.append("Content is too short - add more value")
    
    score.add_score("length", length_score, weight=0.2)
    
    # Hashtag score
    hashtags = metadata.get("hashtags", [])
    hashtag_count = len(hashtags)
    if 3 <= hashtag_count <= 5:
        hashtag_score = 100
    elif 1 <= hashtag_count < 3:
        hashtag_score = 60
        improvements.append(f"Add {3 - hashtag_count} more hashtags for better reach")
    elif hashtag_count > 5:
        hashtag_score = 70
        improvements.append("Consider using 3-5 most relevant hashtags")
    else:
        hashtag_score = 30
        improvements.append("Add 3-5 relevant hashtags")
    
    score.add_score("hashtags", hashtag_score, weight=0.15)
    
    # Readability score (simple: sentence length, paragraph breaks)
    sentences = content.split('.')
    avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences) if sentences else 0
    
    if 10 <= avg_sentence_length <= 20:
        readability_score = 100
    elif 5 <= avg_sentence_length < 10:
        readability_score = 70
        improvements.append("Consider longer, more detailed sentences")
    elif 20 < avg_sentence_length <= 30:
        readability_score = 75
        improvements.append("Consider shorter sentences for better readability")
    else:
        readability_score = 50
        improvements.append("Adjust sentence length for optimal readability")
    
    score.add_score("readability", readability_score, weight=0.15)
    
    # Engagement hooks score (questions, call-to-action)
    has_question = '?' in content
    has_cta = any(cta in content.lower() for cta in ['share', 'comment', 'thoughts', 'like', 'subscribe'])
    
    engagement_score = 50
    if has_question:
        engagement_score += 25
    if has_cta:
        engagement_score += 25
    if not has_question and not has_cta:
        improvements.append("Consider adding a question or call-to-action to increase engagement")
    
    score.add_score("engagement_hooks", engagement_score, weight=0.2)
    
    # Structure score (has intro, body, conclusion)
    paragraphs = content.split('\n\n')
    if len(paragraphs) >= 2:
        structure_score = 90
    elif len(paragraphs) == 1:
        structure_score = 60
        improvements.append("Consider adding paragraph breaks for better structure")
    else:
        structure_score = 40
    
    score.add_score("structure", structure_score, weight=0.1)
    
    # Sentiment analysis
    sentiment_result = analyze_sentiment(content)
    sentiment_score = 70  # Neutral default
    if sentiment_result["sentiment"] == "positive":
        sentiment_score = 90
    elif sentiment_result["sentiment"] == "negative":
        sentiment_score = 40
        improvements.append("Consider a more positive tone")
    
    score.add_score("sentiment", sentiment_score, weight=0.2)
    
    total_score = score.get_total()
    
    # Overall grade
    if total_score >= 85:
        grade = "A"
    elif total_score >= 75:
        grade = "B"
    elif total_score >= 65:
        grade = "C"
    else:
        grade = "D"
    
    return {
        "total_score": round(total_score, 1),
        "grade": grade,
        "component_scores": {k: round(v["score"], 1) for k, v in score.scores.items()},
        "improvements": improvements,
        "sentiment": sentiment_result
    }


def create_ab_test_variants(base_content: str, num_variants: int = 3) -> List[Dict[str, Any]]:
    """
    Create A/B test variants of content.
    Variants differ in:
    - Headline/hook
    - Tone (formal vs casual)
    - Length
    - CTA placement
    """
    variants = []
    
    # Parse base content
    sentences = base_content.split('. ')
    first_sentence = sentences[0] if sentences else ""
    rest_content = '. '.join(sentences[1:]) if len(sentences) > 1 else ""
    
    # Variant 1: Question hook
    if not first_sentence.endswith('?'):
        variant1_hook = f"Have you ever wondered about {first_sentence.lower()}? {first_sentence}"
    else:
        variant1_hook = first_sentence
    
    variant1 = {
        "id": "variant_1",
        "hook_type": "question",
        "content": f"{variant1_hook}. {rest_content}",
        "description": "Question hook variant - encourages engagement"
    }
    variants.append(variant1)
    
    # Variant 2: Direct/statistical hook
    variant2_hook = first_sentence
    if "statistic" not in first_sentence.lower() and "data" not in first_sentence.lower():
        # Try to add a statistic feel
        variant2_hook = f"Here's what most people don't know: {first_sentence.lower()}"
    
    variant2 = {
        "id": "variant_2",
        "hook_type": "statistical",
        "content": f"{variant2_hook}. {rest_content}",
        "description": "Direct/statistical hook variant - builds credibility"
    }
    variants.append(variant2)
    
    # Variant 3: Story hook
    variant3_hook = f"Let me tell you a story about {first_sentence.lower()}"
    variant3 = {
        "id": "variant_3",
        "hook_type": "story",
        "content": f"{variant3_hook}. {rest_content}",
        "description": "Story hook variant - creates emotional connection"
    }
    variants.append(variant3)
    
    return variants[:num_variants]


def track_ab_test_results(test_id: str, variant_id: str, metrics: Dict[str, Any]) -> bool:
    """Track A/B test results for analysis"""
    try:
        test_data = {
            "test_id": test_id,
            "variant_id": variant_id,
            "metrics": metrics,
            "timestamp": datetime.now().isoformat()
        }
        
        db.collection("ab_tests").document().set(test_data)
        logger.info(f"Tracked A/B test result: {test_id}/{variant_id}")
        return True
    except Exception as e:
        logger.error(f"Error tracking A/B test: {e}")
        return False


def get_ab_test_winner(test_id: str) -> Optional[Dict[str, Any]]:
    """Determine winner of A/B test based on performance"""
    try:
        query = db.collection("ab_tests").where("test_id", "==", test_id)
        docs = query.stream()
        
        variant_metrics = {}
        
        for doc in docs:
            data = doc.to_dict()
            if not data:
                continue
            
            variant_id = data.get("variant_id")
            metrics = data.get("metrics", {})
            
            if variant_id not in variant_metrics:
                variant_metrics[variant_id] = {
                    "views": 0,
                    "engagements": 0,
                    "clicks": 0,
                    "count": 0
                }
            
            variant_metrics[variant_id]["views"] += metrics.get("views", 0)
            variant_metrics[variant_id]["engagements"] += metrics.get("engagements", 0)
            variant_metrics[variant_id]["clicks"] += metrics.get("clicks", 0)
            variant_metrics[variant_id]["count"] += 1
        
        # Calculate engagement rates
        winner = None
        highest_rate = 0
        
        for variant_id, metrics in variant_metrics.items():
            views = metrics["views"]
            if views > 0:
                engagement_rate = metrics["engagements"] / views
                
                if engagement_rate > highest_rate:
                    highest_rate = engagement_rate
                    winner = {
                        "variant_id": variant_id,
                        "engagement_rate": engagement_rate,
                        "views": views,
                        "engagements": metrics["engagements"],
                        "statistical_significance": "pending"  # Could add statistical test
                    }
        
        return winner
        
    except Exception as e:
        logger.error(f"Error determining A/B test winner: {e}")
        return None

