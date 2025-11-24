"""
NLP Routes - Intent detection, entity extraction, summarization
"""
import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Query, Body
from app.services.nlp_service import detect_intent, extract_entities, summarize_text, analyze_sentiment

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/detect-intent", response_model=Dict[str, Any])
async def detect_text_intent(text: str = Body(..., description="Text to analyze")) -> Dict[str, Any]:
    """Detect intent from text"""
    try:
        result = detect_intent(text)
        return {"success": True, **result}
    except Exception as e:
        logger.exception(f"Error detecting intent: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to detect intent: {str(e)}")


@router.post("/extract-entities", response_model=Dict[str, Any])
async def extract_text_entities(text: str = Body(..., description="Text to analyze")) -> Dict[str, Any]:
    """Extract entities from text"""
    try:
        entities = extract_entities(text)
        return {"success": True, "entities": entities}
    except Exception as e:
        logger.exception(f"Error extracting entities: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to extract entities: {str(e)}")


@router.post("/summarize", response_model=Dict[str, Any])
async def summarize_text_endpoint(
    text: str = Body(..., description="Text to summarize"),
    max_sentences: int = Query(3, ge=1, le=10, description="Maximum sentences in summary")
) -> Dict[str, Any]:
    """Summarize text"""
    try:
        summary = summarize_text(text, max_sentences)
        return {
            "success": True,
            "summary": summary,
            "original_length": len(text),
            "summary_length": len(summary)
        }
    except Exception as e:
        logger.exception(f"Error summarizing text: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to summarize: {str(e)}")


@router.post("/analyze-sentiment", response_model=Dict[str, Any])
async def analyze_text_sentiment(text: str = Body(..., description="Text to analyze")) -> Dict[str, Any]:
    """Analyze sentiment of text"""
    try:
        result = analyze_sentiment(text)
        return {"success": True, **result}
    except Exception as e:
        logger.exception(f"Error analyzing sentiment: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze sentiment: {str(e)}")

