"""Analysis execution service used by the RQ worker.

Fetches an observation through the satellite provider, runs the pipeline
registered for the analysis type (app.ai), and persists findings + alerts.
All provenance/simulated flags come from the pipeline result, and failures
leave the analysis in a clear "failed" state with the error logged.
"""

import json
from datetime import UTC, datetime

from geoalchemy2.elements import WKTElement

from app.ai import get_pipeline
from app.ai.registry import UnknownPipelineError
from app.database import SessionLocal
from app.logging_conf import get_logger
from app.models.alert import Alert
from app.models.analysis import Analysis, AnalysisResult
from app.satellite.providers import get_satellite_provider

logger = get_logger(__name__)


def _polygon_wkt(latitude: float, longitude: float, radius_km: float) -> str:
    from app.routes.analysis import build_area_polygon_wkt

    return build_area_polygon_wkt(latitude, longitude, radius_km)["polygon_wkt"]


def _history_limit() -> int:
    from app.config import get_settings

    return get_settings().AI_HISTORY_LIMIT


def _execute_pipeline(analysis: Analysis):
    """Resolve + run the pipeline for an analysis, returning (result, observation, history)."""
    pipeline = get_pipeline(analysis.analysis_type)
    provider = get_satellite_provider()
    observation = provider.fetch_latest(
        analysis.latitude, analysis.longitude, analysis.radius_km
    )
    history = None
    if pipeline.supports_history():
        history = provider.fetch_history(
            analysis.latitude,
            analysis.longitude,
            analysis.radius_km,
            limit=_history_limit(),
        )
    result = pipeline.run(observation, history=history)
    return result, observation


def run_analysis(analysis_id: int) -> None:
    """Fetch an observation, run the registered AI pipeline, and persist."""
    db = SessionLocal()
    analysis = None
    try:
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not analysis:
            return
        analysis.status = "processing"
        db.commit()

        result, observation = _execute_pipeline(analysis)

        history_length = getattr(result, "history_length", 0)
        metadata = result.to_metadata()
        metadata["analysis_id"] = analysis.id
        # Keep the legacy top-level observation fields the existing dashboard
        # reads (ndvi, change_score, cloud_coverage, resolution_m) alongside
        # the new structured pipeline output -- removing them would break
        # already-shipped frontend code for no benefit.
        obs = observation.to_dict()
        metadata["obs"] = obs
        for legacy_key in ("ndvi", "change_score", "cloud_coverage", "resolution_m"):
            metadata[legacy_key] = obs.get(legacy_key)

        db_result = AnalysisResult(
            analysis_id=analysis.id,
            result_geometry=WKTElement(
                _polygon_wkt(analysis.latitude, analysis.longitude, analysis.radius_km),
                srid=4326,
            ),
            severity_score=result.severity,
            confidence=result.confidence,
            finding=result.findings[0] if result.findings else "",
            metadata_json=json.dumps(metadata, sort_keys=True),
        )
        db.add(db_result)
        db.flush()

        if result.severity >= 0.35:
            db.add(Alert(
                user_id=analysis.user_id,
                analysis_result_id=db_result.id,
                alert_type="warning" if result.severity < 0.7 else "critical",
                title=f"{analysis.analysis_type.value.replace('_', ' ').title()} detected",
                description=db_result.finding,
            ))
        analysis.status = "completed"
        analysis.completed_at = datetime.now(UTC)
        db.commit()

        logger.info(
            "Analysis completed",
            extra_keys={
                "analysis_id": analysis.id,
                "pipeline": result.model.name,
                "type": analysis.analysis_type.value,
                "source": observation.source,
                "provenance": result.provenance.value,
                "severity": result.severity,
                "history_length": history_length,
            },
        )
    except Exception as exc:  # noqa: BLE001 - worker boundary: surface everything
        db.rollback()
        error_type = "pipeline" if isinstance(exc, (UnknownPipelineError,)) else "provider"
        logger.error(
            "Analysis failed",
            exc_info=exc,
            extra_keys={
                "analysis_id": analysis_id,
                "error_type": error_type,
                "error": str(exc),
            },
        )
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if analysis:
            analysis.status = "failed"
            db.commit()
        raise
    finally:
        db.close()
