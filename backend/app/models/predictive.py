"""
Predictive Analytics Models
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class PredictionType(str, Enum):
    PROSPECT_CONVERSION = "prospect_conversion"
    CONTENT_ENGAGEMENT = "content_engagement"
    OPTIMAL_POSTING_TIME = "optimal_posting_time"
    HASHTAG_PERFORMANCE = "hashtag_performance"


class ConversionPrediction(BaseModel):
    prospect_id: str
    conversion_probability: float = Field(..., ge=0.0, le=1.0, description="Probability of conversion (0-1)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence in prediction")
    key_factors: List[str] = Field(default_factory=list, description="Key factors influencing prediction")
    recommended_actions: List[str] = Field(default_factory=list, description="Recommended actions to improve conversion")
    predicted_conversion_date: Optional[str] = None


class ContentEngagementPrediction(BaseModel):
    content_id: Optional[str] = None
    content_preview: str
    predicted_engagement_rate: float = Field(..., ge=0.0, description="Predicted engagement rate")
    predicted_views: Optional[int] = None
    predicted_clicks: Optional[int] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    recommended_improvements: List[str] = Field(default_factory=list)
    optimal_hashtags: List[str] = Field(default_factory=list)


class OptimalPostingTime(BaseModel):
    day_of_week: str
    hour: int = Field(..., ge=0, le=23)
    predicted_engagement_multiplier: float = Field(..., description="Multiplier vs average (1.0 = average)")


class RecommendationType(str, Enum):
    PROSPECT = "prospect"
    CONTENT_TOPIC = "content_topic"
    OUTREACH_ANGLE = "outreach_angle"
    HASHTAG = "hashtag"
    TIMING = "timing"


class Recommendation(BaseModel):
    type: RecommendationType
    title: str
    description: str
    score: float = Field(..., ge=0.0, le=1.0, description="Recommendation score")
    reasoning: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PredictionRequest(BaseModel):
    user_id: str
    prediction_type: PredictionType
    input_data: Dict[str, Any]


class PredictionResponse(BaseModel):
    success: bool
    prediction_type: PredictionType
    result: Dict[str, Any]
    confidence: float
    generated_at: str

