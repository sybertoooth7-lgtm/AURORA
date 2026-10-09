"""Field-boundary crop analysis.

Turns a GeoJSON field polygon into a completed vegetation analysis: the route
derives the satellite survey area (centroid + a covering radius) from the
boundary, fetches the latest real satellite observation over it (Sentinel-2
when live credentials are configured, the deterministic demo provider
otherwise), runs the NDVI vegetation pipeline synchronously, persists the run
exactly like the worker would, and returns a structured report. Provenance is
always surfaced (``real`` vs ``simulated``) and never inferred from context.
"""

import math

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai.registry import UnknownPipelineError
from app.database import get_db
from app.exceptions import PipelineUnavailableError, SatelliteDataUnavailableError
from app.logging_conf import get_logger
from app.models.analysis import AnalysisType
from app.models.user import User
from app.routes.ai import _fetch_observation, _persist_analysis_result
from app.schemas.crop import (
    CropAnalysisRequest,
    CropAnalysisResponse,
    CropObservationResponse,
)
from app.security import require_verified

router = APIRouter(prefix="/crop", tags=["Crop Analysis"])

logger = get_logger(__name__)

KM_PER_DEG_LAT = 111.32
SURVEY_MAX_RADIUS_KM = 500.0
AREA_PAD = 1.1
MIN_RADIUS_KM = 0.1


def _survey_area(coordinates: list[list[list[float]]]) -> tuple[float, float, float, str]:
    """Derive (centroid_lon, centroid_lat, covering_radius_km, boundary_wkt).

    The radius is the centroid's furthest vertex distance padded out so the
    satellite provider's survey box fully encloses the field polygon. The
    polygon is validated by the schema already; only degeneracy remains to
    reject here.
    """
    ring = coordinates[0]
    pts = ring[:-1]  # drop the closing duplicate for the area math
    n = len(pts)

    area2 = 0.0
    cx = 0.0
    cy = 0.0
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        cross = x1 * y2 - x2 * y1
        area2 += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    if abs(area2) < 1e-10:
        raise HTTPException(
            status_code=422,
            detail="field boundary has zero area (vertices are collinear or coincident)",
        )

    centroid_lon = cx / (3.0 * area2)
    centroid_lat = min(90.0, max(-90.0, cy / (3.0 * area2)))
    cos_lat = math.cos(math.radians(centroid_lat))

    radius_km = max(
        (math.hypot((x - centroid_lon) * KM_PER_DEG_LAT * cos_lat, (y - centroid_lat) * KM_PER_DEG_LAT))
        for x, y in pts
    ) * AREA_PAD
    radius_km = max(radius_km, MIN_RADIUS_KM)
    if radius_km > SURVEY_MAX_RADIUS_KM:
        raise HTTPException(
            status_code=422,
            detail=f"field boundary is too large (covering radius {radius_km:.0f} km exceeds the {SURVEY_MAX_RADIUS_KM} km limit)",
        )

    wkt = "POLYGON((" + ", ".join(f"{lon:.8f} {lat:.8f}" for lon, lat in pts) + ", " + f"{pts[0][0]:.8f} {pts[0][1]:.8f}))"
    return centroid_lon, centroid_lat, radius_km, wkt


def _condition(result) -> str:
    """Crop condition from the pipeline's label when present, else severity."""
    if result.labels:
        return result.labels[0].class_
    if result.severity < 0.35:
        return "healthy"
    if result.severity < 0.7:
        return "stressed"
    return "critical"


@router.post("/analyze", response_model=CropAnalysisResponse, status_code=201)
def analyze_field_boundary(
    request: CropAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified),
):
    """Run an end-to-end crop analysis over a field boundary.

    Accepts the field as a GeoJSON polygon, measures NDVI from satellite
    observations over the covering area, classifies crop condition through
    the vegetation pipeline, persists the run (dashboard/alerts see it too),
    and returns a report with the observation provenance made explicit.
    """
    centroid_lon, centroid_lat, radius_km, boundary_wkt = _survey_area(
        request.field_boundary.coordinates
    )

    try:
        result, observation = _fetch_observation(
            AnalysisType.VEGETATION_STRESS,
            centroid_lat,
            centroid_lon,
            radius_km,
            request.use_history,
        )
    except UnknownPipelineError as exc:
        raise PipelineUnavailableError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - provider failures map to 502
        raise SatelliteDataUnavailableError(
            f"Satellite observation unavailable for this field boundary: {exc}"
        ) from exc

    analysis_id = _persist_analysis_result(
        db,
        current_user.id,
        AnalysisType.VEGETATION_STRESS,
        {
            "polygon_wkt": boundary_wkt,
            "latitude": centroid_lat,
            "longitude": centroid_lon,
            "radius_km": radius_km,
            "description": request.description
            or "Crop analysis over field boundary polygon (NDVI)",
        },
        result,
    )
    logger.info(
        "Crop analysis completed",
        extra_keys={
            "analysis_id": analysis_id,
            "user_id": current_user.id,
            "source": observation.source,
            "provenance": result.provenance.value,
            "ndvi": result.metrics.get("ndvi"),
            "condition": _condition(result),
        },
    )

    metrics = {k: float(v) if v is not None else -1.0 for k, v in result.metrics.items()}
    condition = _condition(result)
    model_label = f"{result.model.name} {result.model.version} ({result.model.kind.value})"
    report = [
        f"Observation: {observation.source} image {observation.image_id} acquired "
        f"{observation.acquired_at:%Y-%m-%d} (cloud {observation.cloud_coverage * 100:.0f}%, "
        f"resolution {observation.resolution_m:.0f} m, simulated={observation.is_simulated}).",
        f"NDVI over the field's covering area: {metrics['ndvi']:.3f}.",
        f"Crop condition: {condition} (severity {result.severity:.3f}, confidence {result.confidence:.2f}).",
    ]
    report.extend(result.findings)
    report.append(f"Provenance: {result.provenance.value}. Model: {model_label}.")

    return CropAnalysisResponse(
        analysis_id=analysis_id,
        boundary=request.field_boundary,
        boundary_wkt=boundary_wkt,
        latitude=centroid_lat,
        longitude=centroid_lon,
        radius_km=round(radius_km, 4),
        observation=CropObservationResponse(
            source=observation.source,
            image_id=observation.image_id,
            acquired_at=observation.acquired_at,
            cloud_coverage=observation.cloud_coverage,
            resolution_m=observation.resolution_m,
            simulated=observation.is_simulated,
        ),
        ndvi=metrics["ndvi"],
        change_score=metrics.get("change_score") or observation.change_score,
        condition=condition,
        severity=result.severity,
        confidence=result.confidence,
        findings=result.findings,
        metrics=metrics,
        model=model_label,
        provenance=result.provenance.value,
        report=report,
    )
