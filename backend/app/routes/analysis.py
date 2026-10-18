"""Analysis endpoints"""

import json
import math
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import area_geometry, get_db
from app.models.alert import Alert
from app.models.analysis import Analysis, AnalysisResult, AnalysisType
from app.models.user import User
from app.queue import get_analysis_queue
from app.quota import check_and_increment_daily_quota, current_daily_quota_usage
from app.schemas.analysis import (
    AnalysisCreate,
    AnalysisHistoryResponse,
    AnalysisListResponse,
    AnalysisMonitorUpdate,
    AnalysisResponse,
    AnalysisResultListResponse,
    AnalysisSummaryResponse,
)
from app.security import get_current_user, require_verified
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
    current_user: User = Depends(require_verified),
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


@router.get("/summary", response_model=AnalysisSummaryResponse)
async def summarize_analyses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Account roll-up for the dashboard: counts, averages and quota headroom.

    Every figure is a single grouped query rather than a per-area loop, so the
    cost does not grow with how many areas a customer has. ``provenance`` is
    the honesty invariant made visible: it separates how many findings came
    from real satellite data versus the simulated demo provider.
    """
    by_status = dict(
        db.query(Analysis.status, func.count())
        .filter(Analysis.user_id == current_user.id)
        .group_by(Analysis.status)
        .all()
    )
    by_type = {
        key.value if hasattr(key, "value") else str(key): count
        for key, count in db.query(Analysis.analysis_type, func.count())
        .filter(Analysis.user_id == current_user.id)
        .group_by(Analysis.analysis_type)
        .all()
    }
    total = sum(by_status.values())
    monitored = db.query(Analysis).filter(
        Analysis.user_id == current_user.id,
        Analysis.monitor_interval_minutes.is_not(None),
    ).count()

    averages = db.query(
        func.count(AnalysisResult.id),
        func.avg(AnalysisResult.severity_score),
        func.avg(AnalysisResult.confidence),
    ).join(Analysis, AnalysisResult.analysis_id == Analysis.id).filter(
        Analysis.user_id == current_user.id
    ).one()
    findings, mean_severity, mean_confidence = averages

    unread = db.query(Alert).filter(
        Alert.user_id == current_user.id, Alert.is_read.is_(False)
    ).count()

    latest = (
        db.query(Analysis)
        .filter(Analysis.user_id == current_user.id)
        .order_by(Analysis.created_at.desc())
        .first()
    )
    last_activity = latest.created_at if latest else None

    provenance_counts: dict[str, int] = {}
    for (payload,) in db.query(AnalysisResult.metadata_json).join(
        Analysis, AnalysisResult.analysis_id == Analysis.id
    ).filter(Analysis.user_id == current_user.id).all():
        key = _provenance_of(payload)
        provenance_counts[key] = provenance_counts.get(key, 0) + 1

    limit = get_settings().MAX_ANALYSES_PER_USER_PER_DAY
    used = current_daily_quota_usage(current_user.id, "analyses")
    return {
        "total_analyses": total,
        "by_status": by_status,
        "by_analysis_type": by_type,
        "monitored_areas": monitored,
        "completed_with_findings": int(findings or 0),
        "mean_severity": round(float(mean_severity), 4) if mean_severity is not None else None,
        "mean_confidence": round(float(mean_confidence), 4) if mean_confidence is not None else None,
        "unread_alerts": int(unread),
        "quota_limit_per_day": limit,
        "quota_used_today": used,
        "quota_remaining_today": max(limit - used, 0),
        "last_activity_at": last_activity,
        "provenance": provenance_counts,
    }


def _provenance_of(metadata_json: str | None) -> str:
    """Bucket a persisted result by where its data actually came from.

    Results written before provenance was tracked report ``unknown`` rather
    than being silently counted as real.
    """
    if not metadata_json:
        return "unknown"
    try:
        payload = json.loads(metadata_json)
    except (TypeError, ValueError):
        return "unknown"
    if not isinstance(payload, dict):
        return "unknown"
    if payload.get("provenance"):
        return str(payload["provenance"])
    if payload.get("simulated") is True:
        return "simulated"
    if payload.get("simulated") is False:
        return "real"
    return "unknown"


@router.get("/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get analysis by ID"""
    analysis = _owned_analysis(db, current_user.id, analysis_id)
    return analysis


@router.get("/", response_model=AnalysisListResponse)
async def list_analyses(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: str | None = Query(None, description="pending | processing | completed | failed"),
    analysis_type: AnalysisType | None = None,
    monitored_only: bool = False,
    since: datetime | None = None,
    until: datetime | None = None,
    order: str = Query("newest", pattern="^(newest|oldest)$"),
    current_user: User = Depends(get_current_user),
):
    """List the caller's areas, newest first by default.

    Filtered and paged server-side: the previous shape returned a bare slice
    with no total, so a client could not tell a short account from a full
    page.
    """
    query = db.query(Analysis).filter(Analysis.user_id == current_user.id)
    if status is not None:
        query = query.filter(Analysis.status == status)
    if analysis_type is not None:
        query = query.filter(Analysis.analysis_type == analysis_type)
    if monitored_only:
        query = query.filter(Analysis.monitor_interval_minutes.is_not(None))
    if since is not None:
        query = query.filter(Analysis.created_at >= _naive_aware(since))
    if until is not None:
        query = query.filter(Analysis.created_at <= _naive_aware(until))

    total = query.count()
    # created_at is only second-precision, so rows created in the same tick tie
    # and the id tie-break has to follow the requested direction -- pinning it
    # to one direction would make ?order=oldest still return newest first.
    if order == "oldest":
        items = (
            query.order_by(Analysis.created_at.asc(), Analysis.id.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )
    else:
        items = (
            query.order_by(Analysis.created_at.desc(), Analysis.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
    return {"total": total, "skip": skip, "limit": limit, "items": items}


def _naive_aware(value: datetime) -> datetime:
    """Strip tzinfo for created_at comparisons.

    ``analyses.created_at`` is a naive column (server_default now()), and
    SQLite refuses to compare aware against naive datetimes. Comparing on the
    wall-clock value keeps the filter working in both demo mode and Postgres.
    """
    return value.replace(tzinfo=None) if value.tzinfo is not None else value


@router.get("/{analysis_id}/history", response_model=AnalysisHistoryResponse)
async def get_analysis_history(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Every monitored pass over an area, oldest first, with the trend between
    the first and latest pass.

    Continuous monitoring is only useful as a series: ``/results`` gives the
    rows, this gives the direction of travel across them.
    """
    _owned_analysis(db, current_user.id, analysis_id)

    rows = (
        db.query(AnalysisResult)
        .filter(AnalysisResult.analysis_id == analysis_id)
        .order_by(AnalysisResult.created_at.asc(), AnalysisResult.id.asc())
        .all()
    )

    points: list[dict] = []
    for row in rows:
        payload = _metadata_payload(row.metadata_json)
        points.append(
            {
                "result_id": row.id,
                "checked_at": row.created_at,
                "severity_score": row.severity_score,
                "confidence": row.confidence,
                "finding": row.finding,
                "provenance": payload.get("provenance"),
                "source": payload.get("source"),
                "simulated": payload.get("simulated"),
            }
        )

    # Trend is read off the ORM rows, not the serialized points, so the
    # severity comparison works on typed Float columns rather than dict lookups.
    first_row = rows[0] if rows else None
    latest_row = rows[-1] if rows else None
    change: float | None = None
    if len(rows) < 2:
        direction = "single_pass" if rows else "no_data"
    elif first_row.severity_score is None or latest_row.severity_score is None:  # type: ignore[union-attr]
        direction = "no_data"
    else:
        change = round(latest_row.severity_score - first_row.severity_score, 4)  # type: ignore[union-attr]
        if change > 0.05:
            direction = "worsening"
        elif change < -0.05:
            direction = "improving"
        else:
            direction = "stable"

    return {
        "analysis_id": analysis_id,
        "points": points,
        "passes": len(points),
        "first_checked_at": first_row.created_at if first_row else None,
        "latest_checked_at": latest_row.created_at if latest_row else None,
        "severity_change": change,
        "direction": direction,
    }


def _metadata_payload(metadata_json: str | None) -> dict:
    """Decode persisted result metadata, tolerating anything unparseable.

    Historical rows written before the current metadata shape exist; a broken
    blob must degrade to missing fields, not a 500 on a read endpoint.
    """
    if not metadata_json:
        return {}
    try:
        payload = json.loads(metadata_json)
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}



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
    current_user: User = Depends(require_verified),
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
    current_user: User = Depends(require_verified),
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
