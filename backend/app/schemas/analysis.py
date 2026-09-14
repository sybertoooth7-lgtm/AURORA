"""Analysis schemas"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.config import get_settings
from app.models.analysis import AnalysisType


class AnalysisCreate(BaseModel):
    """Analysis creation schema"""
    analysis_type: AnalysisType
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_km: float = Field(gt=0, le=500)
    description: str | None = None


class AnalysisResponse(BaseModel):
    """Analysis response schema"""
    id: int
    user_id: int
    analysis_type: AnalysisType
    status: str
    description: str | None
    latitude: float
    longitude: float
    radius_km: float
    created_at: datetime
    completed_at: datetime | None
    monitor_interval_minutes: int | None
    next_check_at: datetime | None

    class Config:
        from_attributes = True


class AnalysisMonitorUpdate(BaseModel):
    """Set (or clear) continuous monitoring for an area.

    A non-null value schedules a re-check every that many minutes, starting
    now; null disables monitoring. The floor is enforced here against the
    configured minimum so enabling can never create a cadence fast enough to
    burn through the whole Sentinel free tier on one area alone.
    """
    monitor_interval_minutes: int | None = None

    @field_validator("monitor_interval_minutes")
    @classmethod
    def _floor_min_interval(cls, value: int | None) -> int | None:
        if value is None:
            return value
        minimum = get_settings().MONITOR_MIN_INTERVAL_MINUTES
        if value < minimum:
            raise ValueError(
                f"monitor_interval_minutes must be at least {minimum} minutes"
            )
        return value


class AnalysisResultListResponse(BaseModel):
    """Analysis results returned for a completed analysis."""
    results: list["AnalysisResultResponse"]


class AnalysisResultResponse(BaseModel):
    """Analysis result response schema"""
    id: int
    severity_score: float | None
    confidence: float | None
    finding: str
    metadata_json: str | None
    created_at: datetime

    class Config:
        from_attributes = True
