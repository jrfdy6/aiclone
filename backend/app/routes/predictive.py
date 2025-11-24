"""
Predictive Analytics Routes
"""
import logging
from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Query
from app.models.predictive import PredictionRequest, PredictionResponse, PredictionType
from app.services.predictive_service import (
    predict_prospect_conversion, predict_content_engagement,
    predict_optimal_posting_time
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/predict", response_model=PredictionResponse)
async def make_prediction(request: PredictionRequest) -> Dict[str, Any]:
    """Make a prediction based on type and input data"""
    try:
        result = {}
        
        if request.prediction_type == PredictionType.PROSPECT_CONVERSION:
            prediction = predict_prospect_conversion(request.input_data)
            result = prediction.model_dump()
            confidence = prediction.confidence
            
        elif request.prediction_type == PredictionType.CONTENT_ENGAGEMENT:
            prediction = predict_content_engagement(
                request.input_data,
                request.user_id
            )
            result = prediction.model_dump()
            confidence = prediction.confidence
            
        elif request.prediction_type == PredictionType.OPTIMAL_POSTING_TIME:
            predictions = predict_optimal_posting_time(request.user_id)
            result = {"optimal_times": [p.model_dump() for p in predictions]}
            confidence = 0.8
            
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported prediction type: {request.prediction_type}")
        
        return PredictionResponse(
            success=True,
            prediction_type=request.prediction_type,
            result=result,
            confidence=confidence,
            generated_at=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.exception(f"Error making prediction: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to make prediction: {str(e)}")


@router.post("/prospect/{prospect_id}/predict-conversion")
async def predict_prospect_conversion_endpoint(
    prospect_id: str,
    user_id: str = Query(..., description="User identifier")
) -> Dict[str, Any]:
    """Predict conversion probability for a specific prospect"""
    try:
        from app.services.firestore_client import db
        
        # Get prospect data
        prospect_doc = db.collection("users").document(user_id).collection("prospects").document(prospect_id).get()
        if not prospect_doc.exists:
            raise HTTPException(status_code=404, detail="Prospect not found")
        
        prospect_data = prospect_doc.to_dict()
        prospect_data["id"] = prospect_id
        
        prediction = predict_prospect_conversion(prospect_data)
        
        return {
            "success": True,
            "prediction": prediction.model_dump()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error predicting prospect conversion: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to predict: {str(e)}")


@router.get("/optimal-posting-time", response_model=Dict[str, Any])
async def get_optimal_posting_time(
    user_id: str = Query(..., description="User identifier")
) -> Dict[str, Any]:
    """Get optimal posting times based on historical data"""
    try:
        predictions = predict_optimal_posting_time(user_id)
        return {
            "success": True,
            "optimal_times": [p.model_dump() for p in predictions]
        }
    except Exception as e:
        logger.exception(f"Error getting optimal posting time: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get optimal posting time: {str(e)}")

