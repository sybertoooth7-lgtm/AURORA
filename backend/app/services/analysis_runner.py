"""Analysis execution service used by the API background task."""

import json
from datetime import datetime, timezone
import math

from geoalchemy2.elements import WKTElement

from app.database import SessionLocal
from app.models.alert import Alert
from app.models.analysis import Analysis, AnalysisResult, AnalysisType
from app.satellite.providers import get_satellite_provider


def _polygon_wkt(latitude: float, longitude: float, radius_km: float) -> str:
    latitude_delta = radius_km / 111.32
    longitude_delta = radius_km / (111.32 * max(math.cos(math.radians(latitude)), 0.01))
    points = [
        (longitude - longitude_delta, latitude - latitude_delta),
        (longitude + longitude_delta, latitude - latitude_delta),
        (longitude + longitude_delta, latitude + latitude_delta),
        (longitude - longitude_delta, latitude + latitude_delta),
        (longitude - longitude_delta, latitude - latitude_delta),
    ]
    return "POLYGON((" + ", ".join(f"{lon} {lat}" for lon, lat in points) + "))"


def run_analysis(analysis_id: int) -> None:
    """Fetch an observation, compute a finding, and persist alerts/results."""
    db = SessionLocal()
    analysis = None
    try:
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not analysis:
            return
        analysis.status = "processing"
        db.commit()

        observation = get_satellite_provider().fetch_latest(
            analysis.latitude, analysis.longitude, analysis.radius_km
        )
        if analysis.analysis_type == AnalysisType.VEGETATION_STRESS:
            severity = max(0.0, min(1.0, (0.65 - observation.ndvi) / 0.65))
            finding = "Vegetation stress detected" if severity >= 0.35 else "No significant vegetation stress detected"
        elif analysis.analysis_type == AnalysisType.LAND_CHANGE:
            severity = observation.change_score
            finding = "Land change detected" if severity >= 0.35 else "No significant land change detected"
        else:
            severity = observation.change_score
            finding = f"{analysis.analysis_type.value.replace('_', ' ').title()} screening completed"

        result = AnalysisResult(
            analysis_id=analysis.id,
            result_geometry=WKTElement(
                _polygon_wkt(analysis.latitude, analysis.longitude, analysis.radius_km),
                srid=4326,
            ),
            severity_score=round(severity, 4),
            confidence=0.7 if observation.source == "demo" else 0.85,
            finding=finding,
            metadata_json=json.dumps({
                "source": observation.source,
                "image_id": observation.image_id,
                "acquired_at": observation.acquired_at.isoformat(),
                "cloud_coverage": observation.cloud_coverage,
                "resolution_m": observation.resolution_m,
                "ndvi": observation.ndvi,
                "change_score": observation.change_score,
            }),
        )
        db.add(result)
        db.flush()
        if severity >= 0.35:
            db.add(Alert(
                user_id=analysis.user_id,
                analysis_result_id=result.id,
                alert_type="warning" if severity < 0.7 else "critical",
                title=f"{analysis.analysis_type.value.replace('_', ' ').title()} detected",
                description=finding,
            ))
        analysis.status = "completed"
        analysis.completed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        db.rollback()
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if analysis:
            analysis.status = "failed"
            db.commit()
        raise
    finally:
        db.close()