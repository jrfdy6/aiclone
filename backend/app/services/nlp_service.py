"""
Advanced NLP Service
Intent detection, entity extraction, summarization
"""
import logging
from typing import List, Dict, Any, Optional
import re

logger = logging.getLogger(__name__)


def detect_intent(text: str) -> Dict[str, Any]:
    """
    Detect intent from text (prospect inquiry, support request, etc.)
    Returns intent type and confidence
    """
    text_lower = text.lower()
    
    # Intent keywords
    intents = {
        "interested": ["interested", "want to", "looking for", "need", "help with"],
        "not_interested": ["not interested", "not looking", "don't need", "not right"],
        "request_info": ["more information", "tell me more", "details", "learn more"],
        "scheduling": ["schedule", "meeting", "call", "demo", "availability"],
        "pricing": ["price", "cost", "pricing", "how much", "budget"],
        "support": ["help", "issue", "problem", "error", "doesn't work"],
    }
    
    detected_intents = {}
    for intent_type, keywords in intents.items():
        matches = sum(1 for keyword in keywords if keyword in text_lower)
        if matches > 0:
            confidence = min(0.9, matches * 0.3 + 0.3)
            detected_intents[intent_type] = confidence
    
    if not detected_intents:
        return {
            "intent": "unknown",
            "confidence": 0.3,
            "suggestions": ["Could not determine specific intent"]
        }
    
    # Get highest confidence intent
    primary_intent = max(detected_intents.items(), key=lambda x: x[1])
    
    return {
        "intent": primary_intent[0],
        "confidence": primary_intent[1],
        "all_intents": detected_intents,
        "suggestions": _get_intent_suggestions(primary_intent[0])
    }


def extract_entities(text: str) -> Dict[str, List[str]]:
    """
    Extract entities from text:
    - Company names
    - Person names
    - Products/services
    - Industries
    """
    entities = {
        "companies": [],
        "people": [],
        "products": [],
        "industries": [],
        "keywords": []
    }
    
    # Simple pattern-based extraction (can be enhanced with NER models)
    
    # Company patterns
    company_patterns = [
        r'\b([A-Z][a-z]+ (?:Inc|LLC|Corp|Ltd|Company|Co))\b',
        r'\b([A-Z][a-z]+ (?:Solutions|Systems|Technologies|Group))\b',
    ]
    for pattern in company_patterns:
        matches = re.findall(pattern, text)
        entities["companies"].extend(matches)
    
    # Person names (simple - capital words, 2-3 words)
    name_pattern = r'\b([A-Z][a-z]+ [A-Z][a-z]+)\b'
    name_matches = re.findall(name_pattern, text)
    # Filter out common false positives
    false_positives = ["United States", "New York", "San Francisco"]
    entities["people"] = [m for m in name_matches if m not in false_positives]
    
    # Industry keywords
    industries = [
        "education", "edtech", "healthcare", "technology", "finance",
        "retail", "manufacturing", "consulting", "marketing", "sales"
    ]
    text_lower = text.lower()
    entities["industries"] = [ind for ind in industries if ind in text_lower]
    
    # Extract important keywords (capitalized words, quoted phrases)
    keyword_patterns = [
        r'"([^"]+)"',  # Quoted phrases
        r'\b([A-Z][a-z]{3,})\b',  # Capitalized words
    ]
    for pattern in keyword_patterns:
        matches = re.findall(pattern, text)
        entities["keywords"].extend(matches[:10])  # Limit to 10
    
    # Remove duplicates
    for key in entities:
        entities[key] = list(set(entities[key]))[:5]  # Limit each category
    
    return entities


def summarize_text(text: str, max_sentences: int = 3) -> str:
    """
    Summarize text using extractive summarization.
    Returns key sentences.
    """
    if not text or len(text) < 100:
        return text
    
    # Simple extractive summarization
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
    
    if len(sentences) <= max_sentences:
        return ". ".join(sentences) + "."
    
    # Score sentences (simple heuristic: length, position, keywords)
    sentence_scores = []
    keywords = _extract_keywords(text)
    
    for i, sentence in enumerate(sentences):
        score = 0
        
        # Position score (first and last sentences are important)
        if i < 2 or i >= len(sentences) - 2:
            score += 0.3
        
        # Length score (moderate length is good)
        length = len(sentence)
        if 50 <= length <= 150:
            score += 0.3
        elif 30 <= length <= 200:
            score += 0.2
        
        # Keyword score
        sentence_lower = sentence.lower()
        keyword_matches = sum(1 for kw in keywords if kw.lower() in sentence_lower)
        score += keyword_matches * 0.2
        
        sentence_scores.append((score, sentence))
    
    # Sort by score and take top sentences
    sentence_scores.sort(reverse=True, key=lambda x: x[0])
    top_sentences = [s for _, s in sentence_scores[:max_sentences]]
    
    # Maintain original order
    summary_sentences = []
    for sentence in sentences:
        if sentence in top_sentences:
            summary_sentences.append(sentence)
            if len(summary_sentences) >= max_sentences:
                break
    
    return ". ".join(summary_sentences) + "."


def _extract_keywords(text: str, limit: int = 10) -> List[str]:
    """Extract important keywords from text"""
    # Simple keyword extraction (can be enhanced with TF-IDF)
    words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
    
    # Common stopwords
    stopwords = {"that", "this", "with", "from", "have", "been", "will", "would", "their", "there"}
    
    # Count word frequency
    word_freq = {}
    for word in words:
        if word not in stopwords:
            word_freq[word] = word_freq.get(word, 0) + 1
    
    # Get top words
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    return [word for word, _ in sorted_words[:limit]]


def _get_intent_suggestions(intent: str) -> List[str]:
    """Get suggested actions based on detected intent"""
    suggestions_map = {
        "interested": [
            "Schedule a demo or discovery call",
            "Send detailed information about solution",
            "Share relevant case studies"
        ],
        "request_info": [
            "Provide detailed product information",
            "Share relevant resources or documentation",
            "Offer to answer specific questions"
        ],
        "scheduling": [
            "Share calendar availability",
            "Propose specific meeting times",
            "Send meeting link"
        ],
        "pricing": [
            "Provide pricing information",
            "Schedule pricing discussion call",
            "Share pricing guide or calculator"
        ],
        "support": [
            "Acknowledge the issue",
            "Gather more details about the problem",
            "Route to support team"
        ],
        "not_interested": [
            "Ask for feedback on why not interested",
            "Offer to stay in touch for future",
            "Respectfully acknowledge decision"
        ]
    }
    
    return suggestions_map.get(intent, ["Follow up with general information"])


def analyze_sentiment(text: str) -> Dict[str, Any]:
    """
    Analyze sentiment of text (positive, negative, neutral).
    Returns sentiment and score.
    """
    # Simple sentiment analysis (can be enhanced with ML model)
    positive_words = ["great", "excellent", "good", "love", "amazing", "perfect", "wonderful", "happy", "pleased"]
    negative_words = ["bad", "terrible", "awful", "hate", "horrible", "disappointed", "frustrated", "poor"]
    
    text_lower = text.lower()
    
    positive_count = sum(1 for word in positive_words if word in text_lower)
    negative_count = sum(1 for word in negative_words if word in text_lower)
    
    if positive_count > negative_count:
        sentiment = "positive"
        score = min(1.0, 0.5 + positive_count * 0.15)
    elif negative_count > positive_count:
        sentiment = "negative"
        score = min(1.0, 0.5 + negative_count * 0.15)
    else:
        sentiment = "neutral"
        score = 0.5
    
    return {
        "sentiment": sentiment,
        "score": score,
        "positive_indicators": positive_count,
        "negative_indicators": negative_count
    }

