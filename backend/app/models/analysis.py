"""Analysis models"""

from sqlalchemy import Column, String, Integer, Float, DateTime, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from app.database import Base
import enum


class AnalysisType(str, enum.Enum):
    """Types of analysis"""
    VEGETATION_STRESS = "vegetation_stress"
    LAND_CHANGE = "land_change"
    CLIMATE_IMPACT = "climate_impact"
    INFRASTRUCTURE_CHANGE = "infrastructure_change"
    WATER_MONITORING = "water_monitoring"
    INFRASTRUCTURE_MONITORING = "infrastructure_monitoring"
    ENVIRONMENTAL_MONITORING = "environmental_monitoring"
    ANOMALY_DETECTION = "anomaly_detection"
    WILDFIRE_RISK = "wildfire_risk"
    FLOOD_MONITORING = "flood_monitoring"


class Analysis(Base):
    """Analysis job/request"""
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    analysis_type = Column(SQLEnum(AnalysisType), nullable=False)
    geometry = Column(Geometry('POLYGON', srid=4326), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    radius_km = Column(Float, nullable=False)
    status = Column(String, default="pending")  # pending, processing, completed, failed
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    results = relationship("AnalysisResult", back_populates="analysis", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Analysis(id={self.id}, type={self.analysis_type}, status={self.status})>"


class AnalysisResult(Base):
    """Analysis results"""
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("analyses.id"), nullable=False)
    result_geometry = Column(Geometry('POLYGON', srid=4326), nullable=True)
    severity_score = Column(Float, nullable=True)  # 0-1
    confidence = Column(Float, nullable=True)  # 0-1
    finding = Column(Text, nullable=False)
    metadata_json = Column("metadata", Text, nullable=True)  # JSON string
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    analysis = relationship("Analysis", back_populates="results")

    def __repr__(self):
        return f"<AnalysisResult(id={self.id}, analysis_id={self.analysis_id})>"
