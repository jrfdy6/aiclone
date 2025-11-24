"""
Predictive Insights Service
Forecasting models, anomaly detection
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from app.services.firestore_client import db

logger = logging.getLogger(__name__)


def forecast_revenue(user_id: str, days_ahead: int = 30) -> Dict[str, Any]:
    """
    Forecast revenue based on:
    - Pipeline data
    - Historical conversion rates
    - Deal velocity
    """
    try:
        # Simple forecasting model (can be enhanced with ML)
        # This would require CRM integration for actual pipeline data
        
        # For now, return structure
        return {
            "forecasted_revenue": 0,
            "confidence": 0.5,
            "method": "historical_average",
            "forecast_date": (datetime.now() + timedelta(days=days_ahead)).isoformat(),
            "factors": [],
            "note": "Requires pipeline data integration"
        }
    except Exception as e:
        logger.error(f"Error forecasting revenue: {e}")
        return {}


def forecast_pipeline(user_id: str, days_ahead: int = 30) -> Dict[str, Any]:
    """Forecast pipeline growth"""
    try:
        # Get historical pipeline data
        # For now, return structure
        return {
            "forecasted_pipeline": 0,
            "growth_rate": 0,
            "forecast_date": (datetime.now() + timedelta(days=days_ahead)).isoformat(),
            "confidence": 0.5
        }
    except Exception as e:
        logger.error(f"Error forecasting pipeline: {e}")
        return {}


def detect_anomalies(user_id: str, metric_type: str, days: int = 30) -> List[Dict[str, Any]]:
    """
    Detect anomalies in metrics:
    - Unusual activity spikes/drops
    - Performance anomalies
    - Data quality issues
    """
    try:
        anomalies = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        if metric_type == "engagement":
            # Check for engagement anomalies
            content_query = db.collection("users").document(user_id).collection("content_drafts")
            content_query = content_query.where("status", "==", "published")
            
            engagement_rates = []
            for doc in content_query.stream():
                data = doc.to_dict()
                if not data:
                    continue
                
                views = data.get("views", 0)
                engagements = data.get("engagements", 0)
                if views > 0:
                    engagement_rates.append(engagements / views)
            
            if engagement_rates:
                avg_rate = sum(engagement_rates) / len(engagement_rates)
                std_dev = _calculate_std_dev(engagement_rates)
                
                # Detect outliers
                threshold = avg_rate + (2 * std_dev)  # 2 standard deviations
                low_threshold = avg_rate - (2 * std_dev)
                
                for i, rate in enumerate(engagement_rates):
                    if rate > threshold:
                        anomalies.append({
                            "type": "high_engagement",
                            "metric": "engagement_rate",
                            "value": rate,
                            "expected": avg_rate,
                            "severity": "high",
                            "message": f"Unusually high engagement rate detected: {rate:.2%}"
                        })
                    elif rate < low_threshold and rate > 0:
                        anomalies.append({
                            "type": "low_engagement",
                            "metric": "engagement_rate",
                            "value": rate,
                            "expected": avg_rate,
                            "severity": "medium",
                            "message": f"Unusually low engagement rate detected: {rate:.2%}"
                        })
        
        return anomalies[:10]  # Limit to 10 anomalies
        
    except Exception as e:
        logger.error(f"Error detecting anomalies: {e}")
        return []


def _calculate_std_dev(values: List[float]) -> float:
    """Calculate standard deviation"""
    if not values:
        return 0.0
    
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return variance ** 0.5


def forecast_content_performance(user_id: str, content_preview: str, days_ahead: int = 7) -> Dict[str, Any]:
    """Forecast content performance"""
    try:
        # Use predictive service to estimate performance
        from app.services.predictive_service import predict_content_engagement
        
        content_data = {
            "content": content_preview,
            "id": None
        }
        
        prediction = predict_content_engagement(content_data, user_id)
        
        # Project over time period
        daily_views = prediction.predicted_views / days_ahead if prediction.predicted_views else 0
        
        return {
            "predicted_engagement_rate": prediction.predicted_engagement_rate,
            "predicted_total_views": prediction.predicted_views,
            "predicted_daily_views": int(daily_views),
            "forecast_period_days": days_ahead,
            "confidence": prediction.confidence,
            "recommendations": prediction.recommended_improvements
        }
    except Exception as e:
        logger.error(f"Error forecasting content performance: {e}")
        return {}

