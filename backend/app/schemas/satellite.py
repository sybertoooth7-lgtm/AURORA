"""Satellite imagery schemas"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class SatelliteImageResponse(BaseModel):
    """Satellite image response schema"""
    id: int
    source: str
    image_id: str
    date_acquired: datetime
    cloud_coverage: Optional[float]
    resolution_m: Optional[float]
    url: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
