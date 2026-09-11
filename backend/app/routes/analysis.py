"""Analysis endpoints"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.config import get_settings
from app.database import get_db
from app.queue import get_analysis_queue
from app.schemas.analysis import (
    AnalysisCreate,
    AnalysisResponse,
    AnalysisResultListResponse,
)
from app.models.analysis import Analysis, AnalysisResult
from app.models.user import User
from app.security import get_current_user
from app.services.analysis_runner import run_analysis
from geoalchemy2.elements import WKTElement
from typing import List
import math

router = APIRouter(prefix="/analysis", tags=["analysis"])


def build_area_polygon_wkt(latitude: float, longitude: float, radius_km: float) -> dict:
    """Approximate the requested search area as a geodesic polygon.

    Stores the concrete area of interest for downstream imagery providers.
    Returns dict {polygon_wkt, latitude, longitude, radius_km}.
    """
    latitude_delta = radius_km / 111.32
    longitude_delta = radius_km / (111.32 * max(math.cos(math.radians(latitude)), 0.01))
    points = [
        (longitude - longitude_delta, latitude - latitude_delta),
        (longitude + longitude_delta, latitude - latitude_delta),
        (longitude + longitude_delta, latitude + latitude_delta),
        (longitude - longitude_delta, latitude + latitude_delta),
        (longitude - longitude_delta, latitude - latitude_delta),
    ]
    polygon = ", ".join(f"{longitude} {latitude}" for longitude, latitude in points)
    return {
        "polygon_wkt": f"POLYGON(({polygon}))",
        "latitude": latitude,
        "longitude": longitude,
        "radius_km": radius_km,
    }


@router.post("/", response_model=AnalysisResponse)
async def create_analysis(
    analysis: AnalysisCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new analysis"""
    area = build_area_polygon_wkt(analysis.latitude, analysis.longitude, analysis.radius_km)

    db_analysis = Analysis(
        user_id=current_user.id,
        analysis_type=analysis.analysis_type,
        geometry=WKTElement(area["polygon_wkt"], srid=4326),
        latitude=analysis.latitude,
        longitude=analysis.longitude,
        radius_km=analysis.radius_km,
        status="pending",
        description=analysis.description
    )
    db.add(db_analysis)
    db.commit()
    db.refresh(db_analysis)
    get_analysis_queue().enqueue(
        run_analysis,
        db_analysis.id,
        job_timeout=get_settings().ANALYSIS_JOB_TIMEOUT_SECONDS,
    )
    return db_analysis


@router.get("/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get analysis by ID"""
    analysis = db.query(Analysis).filter(
        Analysis.id == analysis_id, Analysis.user_id == current_user.id
    ).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis


@router.get("/", response_model=List[AnalysisResponse])
async def list_analyses(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
):
    """List analyses"""
    analyses = db.query(Analysis).filter(Analysis.user_id == current_user.id).offset(skip).limit(limit).all()
    return analyses


@router.get("/{analysis_id}/results", response_model=AnalysisResultListResponse)
async def get_analysis_results(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return findings produced for an analysis."""
    analysis = db.query(Analysis).filter(
        Analysis.id == analysis_id, Analysis.user_id == current_user.id
    ).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    results = db.query(AnalysisResult).filter(
        AnalysisResult.analysis_id == analysis_id
    ).all()
    return {"results": results}
