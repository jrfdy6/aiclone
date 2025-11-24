"""
Recommendation Engine Routes
"""
import logging
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Query
from app.models.predictive import Recommendation, RecommendationType
from app.services.recommendation_service import (
    recommend_prospects, recommend_content_topics,
    recommend_outreach_angles, recommend_hashtags
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/prospects", response_model=Dict[str, Any])
async def get_prospect_recommendations(
    user_id: str = Query(..., description="User identifier"),
    limit: int = Query(10, ge=1, le=50, description="Number of recommendations")
) -> Dict[str, Any]:
    """Get prospect recommendations"""
    try:
        recommendations = recommend_prospects(user_id, limit)
        return {
            "success": True,
            "recommendations": [r.model_dump() for r in recommendations],
            "total": len(recommendations)
        }
    except Exception as e:
        logger.exception(f"Error getting prospect recommendations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get recommendations: {str(e)}")


@router.get("/content-topics", response_model=Dict[str, Any])
async def get_content_topic_recommendations(
    user_id: str = Query(..., description="User identifier"),
    limit: int = Query(10, ge=1, le=50)
) -> Dict[str, Any]:
    """Get content topic recommendations"""
    try:
        recommendations = recommend_content_topics(user_id, limit)
        return {
            "success": True,
            "recommendations": [r.model_dump() for r in recommendations],
            "total": len(recommendations)
        }
    except Exception as e:
        logger.exception(f"Error getting content topic recommendations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get recommendations: {str(e)}")


@router.get("/outreach-angles", response_model=Dict[str, Any])
async def get_outreach_angle_recommendations(
    user_id: str = Query(..., description="User identifier"),
    prospect_id: str = Query(None, description="Optional prospect ID for personalized angles")
) -> Dict[str, Any]:
    """Get outreach angle recommendations"""
    try:
        recommendations = recommend_outreach_angles(user_id, prospect_id)
        return {
            "success": True,
            "recommendations": [r.model_dump() for r in recommendations],
            "total": len(recommendations)
        }
    except Exception as e:
        logger.exception(f"Error getting outreach angle recommendations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get recommendations: {str(e)}")


@router.get("/hashtags", response_model=Dict[str, Any])
async def get_hashtag_recommendations(
    user_id: str = Query(..., description="User identifier"),
    content_preview: str = Query("", description="Optional content preview for contextual recommendations"),
    limit: int = Query(10, ge=1, le=20)
) -> Dict[str, Any]:
    """Get hashtag recommendations"""
    try:
        recommendations = recommend_hashtags(user_id, content_preview, limit)
        return {
            "success": True,
            "recommendations": [r.model_dump() for r in recommendations],
            "total": len(recommendations)
        }
    except Exception as e:
        logger.exception(f"Error getting hashtag recommendations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get recommendations: {str(e)}")

