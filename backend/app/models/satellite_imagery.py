"""Satellite imagery model"""

from geoalchemy2 import Geometry
from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy.sql import func

from app.database import Base


class SatelliteImage(Base):
    """Satellite imagery metadata"""
    __tablename__ = "satellite_images"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False)  # Sentinel, Landsat, etc.
    image_id = Column(String, unique=True, index=True, nullable=False)
    date_acquired = Column(DateTime(timezone=True), nullable=False)
    geometry = Column(Geometry('POLYGON', srid=4326), nullable=False)
    cloud_coverage = Column(Float, nullable=True)
    resolution_m = Column(Float, nullable=True)
    url = Column(String, nullable=True)
    metadata_json = Column("metadata", Text, nullable=True)  # JSON string
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<SatelliteImage(id={self.id}, source={self.source})>"
