"""Analysis endpoints"""

import math
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import area_geometry, get_db
from app.models.analysis import Analysis, AnalysisResult
from app.models.user import User
from app.queue import get_analysis_queue
from app.quota import check_and_increment_daily_quota
from app.schemas.analysis import (
    AnalysisCreate,
    AnalysisMonitorUpdate,
    AnalysisResponse,
    AnalysisResultListResponse,
)
from app.security import get_current_user
from app.services.analysis_runner import run_analysis

router = APIRouter(prefix="/analysis", tags=["Analysis"])


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
    check_and_increment_daily_quota(
        current_user.id, "analyses", get_settings().MAX_ANALYSES_PER_USER_PER_DAY
    )

    area = build_area_polygon_wkt(analysis.latitude, analysis.longitude, analysis.radius_km)

    db_analysis = Analysis(
        user_id=current_user.id,
        analysis_type=analysis.analysis_type,
        geometry=area_geometry(area["polygon_wkt"]),
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
    analysis = _owned_analysis(db, current_user.id, analysis_id)
    return analysis


@router.get("/", response_model=list[AnalysisResponse])
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
    _owned_analysis(db, current_user.id, analysis_id)

    results = db.query(AnalysisResult).filter(
        AnalysisResult.analysis_id == analysis_id
    ).all()
    return {"results": results}


@router.patch("/{analysis_id}/monitor", response_model=AnalysisResponse)
async def set_monitoring(
    analysis_id: int,
    update: AnalysisMonitorUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Enable/disable continuous monitoring for an area.

    ``monitor_interval_minutes`` non-null re-checks the area every that many
    minutes; null turns monitoring off. Setting a cadence schedules the first
    follow-up pass a full interval from now.
    """
    analysis = _owned_analysis(db, current_user.id, analysis_id)
    analysis.monitor_interval_minutes = update.monitor_interval_minutes
    if update.monitor_interval_minutes is None:
        analysis.next_check_at = None
    else:
        analysis.next_check_at = datetime.now(UTC) + timedelta(
            minutes=update.monitor_interval_minutes
        )
    db.commit()
    db.refresh(analysis)
    return analysis


@router.post("/{analysis_id}/re-run", response_model=AnalysisResponse)
async def rerun_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-run an area now, bypassing any monitoring cadence.

    Manual re-runs share the per-user daily quota with new analyses, because
    each pass costs a real Sentinel processing-unit request. Refuses to start
    a run while one is already pending/processing.
    """
    analysis = _owned_analysis(db, current_user.id, analysis_id)
    if analysis.status in ("pending", "processing"):
        raise HTTPException(
            status_code=409,
            detail="This area already has a run in progress",
        )
    check_and_increment_daily_quota(
        current_user.id, "analyses", get_settings().MAX_ANALYSES_PER_USER_PER_DAY
    )
    analysis.status = "pending"
    # An immediate re-run still keeps the cadence honest: the next scheduled
    # pass is counted from this run, not from whenever the last try fired.
    if analysis.monitor_interval_minutes is not None:
        analysis.next_check_at = datetime.now(UTC) + timedelta(
            minutes=analysis.monitor_interval_minutes
        )
    db.commit()
    get_analysis_queue().enqueue(
        run_analysis,
        analysis.id,
        job_timeout=get_settings().ANALYSIS_JOB_TIMEOUT_SECONDS,
    )
    # Refresh after enqueue so the inline (demo) queue's synchronous run is
    # reflected in the response, not a stale "pending" from before it ran.
    db.refresh(analysis)
    return analysis


def _owned_analysis(db: Session, user_id: int, analysis_id: int) -> Analysis:
    """Return the analysis if it belongs to ``user_id``, else 404.

    The 404 (rather than a 403) mirrors the existing read endpoints so the
    existence of another user's area is not disclosed.
    """
    analysis = db.query(Analysis).filter(
        Analysis.id == analysis_id, Analysis.user_id == user_id
    ).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis
