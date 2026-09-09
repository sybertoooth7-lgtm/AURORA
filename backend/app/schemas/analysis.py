"""Analysis schemas"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from app.models.analysis import AnalysisType


class AnalysisCreate(BaseModel):
    """Analysis creation schema"""
    analysis_type: AnalysisType
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_km: float = Field(gt=0, le=500)
    description: Optional[str] = None


class AnalysisResponse(BaseModel):
    """Analysis response schema"""
    id: int
    user_id: int
    analysis_type: AnalysisType
    status: str
    description: Optional[str]
    latitude: float
    longitude: float
    radius_km: float
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class AnalysisResultListResponse(BaseModel):
    """Analysis results returned for a completed analysis."""
    results: List["AnalysisResultResponse"]


class AnalysisResultResponse(BaseModel):
    """Analysis result response schema"""
    id: int
    severity_score: Optional[float]
    confidence: Optional[float]
    finding: str
    metadata_json: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
