"""Analysis schemas"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from app.models.analysis import AnalysisType


class AnalysisCreate(BaseModel):
    """Analysis creation schema"""
    analysis_type: AnalysisType
    latitude: float
    longitude: float
    radius_km: float  # Search radius
    description: Optional[str] = None


class AnalysisResponse(BaseModel):
    """Analysis response schema"""
    id: int
    user_id: int
    analysis_type: AnalysisType
    status: str
    description: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class AnalysisResultResponse(BaseModel):
    """Analysis result response schema"""
    id: int
    severity_score: Optional[float]
    confidence: Optional[float]
    finding: str
    created_at: datetime

    class Config:
        from_attributes = True
