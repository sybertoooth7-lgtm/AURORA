"""Analysis schemas"""

from datetime import datetime

from pydantic import BaseModel, Field

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

    class Config:
        from_attributes = True


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
