"""
Analytics Models
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class MetricType(str, Enum):
    PROSPECTS_ANALYZED = "prospects_analyzed"
    OUTREACH_SENT = "outreach_sent"
    MEETINGS_BOOKED = "meetings_booked"
    CONTENT_PUBLISHED = "content_published"
    RESEARCH_TASKS_COMPLETED = "research_tasks_completed"
    ENGAGEMENT_RATE = "engagement_rate"
    CONVERSION_RATE = "conversion_rate"


class TimeRange(str, Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


class MetricDataPoint(BaseModel):
    date: str
    value: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AnalyticsMetric(BaseModel):
    metric_type: MetricType
    time_range: TimeRange
    data_points: List[MetricDataPoint]
    total: float
    average: float
    trend: str  # "up", "down", "stable"


class AnalyticsSummary(BaseModel):
    user_id: str
    period_start: str
    period_end: str
    metrics: List[AnalyticsMetric]
    top_performers: Dict[str, Any] = Field(default_factory=dict)


class AnalyticsResponse(BaseModel):
    success: bool
    summary: AnalyticsSummary


class ExportFormat(str, Enum):
    CSV = "csv"
    JSON = "json"
    EXCEL = "xlsx"


class ExportRequest(BaseModel):
    user_id: str
    data_type: str  # "prospects", "activities", "content", "all"
    format: ExportFormat = ExportFormat.CSV
    date_range: Optional[Dict[str, str]] = None  # {"start": "2024-01-01", "end": "2024-12-31"}

