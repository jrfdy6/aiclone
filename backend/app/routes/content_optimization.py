"""
Content Optimization Routes - A/B testing, scoring, sentiment
"""
import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Query, Body
from app.services.content_optimization_service import (
    score_content_quality, create_ab_test_variants,
    track_ab_test_results, get_ab_test_winner
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/score", response_model=Dict[str, Any])
async def score_content(
    content: str = Body(..., description="Content to score"),
    metadata: Dict[str, Any] = Body(default_factory=dict, description="Content metadata")
) -> Dict[str, Any]:
    """Score content quality"""
    try:
        score_result = score_content_quality(content, metadata)
        return {"success": True, **score_result}
    except Exception as e:
        logger.exception(f"Error scoring content: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to score content: {str(e)}")


@router.post("/ab-test/variants", response_model=Dict[str, Any])
async def create_ab_variants(
    base_content: str = Body(..., description="Base content to create variants from"),
    num_variants: int = Query(3, ge=2, le=5, description="Number of variants to create")
) -> Dict[str, Any]:
    """Create A/B test variants"""
    try:
        variants = create_ab_test_variants(base_content, num_variants)
        return {
            "success": True,
            "variants": variants,
            "base_content": base_content
        }
    except Exception as e:
        logger.exception(f"Error creating A/B test variants: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create variants: {str(e)}")


@router.post("/ab-test/{test_id}/track", response_model=Dict[str, bool])
async def track_ab_test(
    test_id: str,
    variant_id: str = Query(..., description="Variant ID"),
    metrics: Dict[str, Any] = Body(..., description="Performance metrics")
) -> Dict[str, bool]:
    """Track A/B test results"""
    try:
        success = track_ab_test_results(test_id, variant_id, metrics)
        return {"success": success}
    except Exception as e:
        logger.exception(f"Error tracking A/B test: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to track test: {str(e)}")


@router.get("/ab-test/{test_id}/winner", response_model=Dict[str, Any])
async def get_ab_test_winner_endpoint(test_id: str) -> Dict[str, Any]:
    """Get A/B test winner"""
    try:
        winner = get_ab_test_winner(test_id)
        if not winner:
            return {"success": False, "message": "No winner determined yet or insufficient data"}
        return {"success": True, "winner": winner}
    except Exception as e:
        logger.exception(f"Error getting A/B test winner: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get winner: {str(e)}")

