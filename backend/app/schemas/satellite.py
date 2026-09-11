"""Satellite imagery schemas"""

from datetime import datetime

from pydantic import BaseModel


class SatelliteImageResponse(BaseModel):
    """Satellite image response schema"""
    id: int
    source: str
    image_id: str
    date_acquired: datetime
    cloud_coverage: float | None
    resolution_m: float | None
    url: str | None
    created_at: datetime

    class Config:
        from_attributes = True
