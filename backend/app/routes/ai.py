"""AI pipeline, inference, and model-management endpoints.

Conventions
-----------
* Provenance is never faked: a result produced from the demo provider is
  returned with provenance="simulated" and simulated=True, and results from
  real sensors are provenance="real".
* Every response includes the model identity + kind (prototype/production)
  so consumers can tell "working prototype" from "validated production".
"""

import json
from datetime import datetime, timezone
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai import get_pipeline, list_pipeline_descriptions
from app.ai.base import PipelineResult
from app.ai.registry import UnknownPipelineError
from app.ai.repository import (
    ModelValidationError,
    create_model,
    get_model,
    list_models,
    serialize_model,
    set_status,
)
from app.config import get_settings
from app.database import get_db
from app.exceptions import (
    PipelineUnavailableError,
    SatelliteDataUnavailableError,
)
from app.logging_conf import get_logger
from app.models.alert import Alert
from app.models.analysis import Analysis, AnalysisResult
from app.models.user import User
from app.routes.analysis import build_area_polygon_wkt
from app.satellite.providers import get_satellite_provider
from app.schemas.ai import (
    InferRequest,
    InferResponse,
    ModelCreate,
    ModelResponse,
    ModelStatusUpdate,
    PipelineDescription,
    PipelineResultResponse,
)
from app.security import get_current_user, require_admin
from geoalchemy2.elements import WKTElement

logger = get_logger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/pipelines", response_model=list[PipelineDescription])
def list_ai_pipelines():
    """Describe every registered pipeline (public -- no auth needed).

    Handles = the analysis types each pipeline covers; model.kind tells
    consumers whether the underlying approach is a validated production
    model or a prototype under evaluation.
    """
    return list_pipeline_descriptions()


def _fetch_observation(
    analysis_type,
    latitude: float,
    longitude: float,
    radius_km: float,
    use_history: bool,
):
    """Fetch observation(+history) and run the pipeline synchronously."""
    pipeline = get_pipeline(analysis_type)
    started = time.monotonic()
    provider = get_satellite_provider()
    pipeline_timeout = get_settings().AI_INFER_SYNC_TIMEOUT_SECONDS

    observation = provider.fetch_latest(latitude, longitude, radius_km)
    if use_history and pipeline.supports_history():
        history = provider.fetch_history(
            latitude, longitude, radius_km, limit=get_settings().AI_HISTORY_LIMIT
        )
    else:
        history = None

    elapsed = time.monotonic() - started
    if elapsed > pipeline_timeout:
        logger.warning(
            "Sync inference exceeded timeout budget",
            extra_keys={"analysis_type": analysis_type.value, "seconds": round(elapsed, 2)},
        )

    result = pipeline.run(observation, history=history)
    logger.info(
        "Pipeline executed",
        extra_keys={
            "pipeline": pipeline.name,
            "analysis_type": analysis_type.value,
            "source": observation.source,
            "provenance": result.provenance.value,
            "severity": result.severity,
        },
    )
    return result, observation


def _persist_analysis_result(db: Session, user_id: int, analysis_type, area: dict, result: PipelineResult) -> int:
    """Store the run exactly like the queued runner would, so the dashboard
    and the /analysis/ endpoints see the same data."""
    db_analysis = Analysis(
        user_id=user_id,
        analysis_type=analysis_type,
        geometry=WKTElement(area["polygon_wkt"], srid=4326),
        latitude=area["latitude"],
        longitude=area["longitude"],
        radius_km=area["radius_km"],
        status="completed",
        description=area["description"],
        completed_at=datetime.now(timezone.utc),
    )
    db.add(db_analysis)
    db.flush()

    metadata = result.to_metadata()
    metadata["analysis_id"] = db_analysis.id
    for legacy_key in ("ndvi", "change_score", "cloud_coverage", "resolution_m"):
        if legacy_key in result.metrics:
            metadata[legacy_key] = result.metrics[legacy_key]

    db_result = AnalysisResult(
        analysis_id=db_analysis.id,
        result_geometry=WKTElement(area["polygon_wkt"], srid=4326),
        severity_score=result.severity,
        confidence=result.confidence,
        finding=result.findings[0] if result.findings else "",
        metadata_json=json.dumps(metadata, sort_keys=True),
    )
    db.add(db_result)
    db.flush()

    if result.severity >= 0.35:
        db.add(
            Alert(
                user_id=user_id,
                analysis_result_id=db_result.id,
                alert_type="warning" if result.severity < 0.7 else "critical",
                title=f"{analysis_type.value.replace('_', ' ').title()} detected",
                description=db_result.finding,
            )
        )
    db.commit()
    return db_analysis.id


@router.post("/infer", response_model=InferResponse)
def run_inference(
    request: InferRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run a pipeline synchronously over an area and persist the result.

    Picks the pipeline registered for ``analysis_type``, fetches the latest
    observation (and its history when ``use_history`` is set and the
    pipeline supports it), and stores the run as a completed analysis so the
    same result shows up in the dashboard, alerts, and report exports.

    Simulated observations are disclosed in the response (simulated=True).
    """
    area = build_area_polygon_wkt(
        latitude=request.latitude,
        longitude=request.longitude,
        radius_km=request.radius_km,
    )
    try:
        result, observation = _fetch_observation(
            request.analysis_type,
            request.latitude,
            request.longitude,
            request.radius_km,
            request.use_history,
        )
    except UnknownPipelineError as exc:
        raise PipelineUnavailableError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - provider failures map to 502
        raise SatelliteDataUnavailableError(
            f"Satellite observation unavailable for this area: {exc}"
        ) from exc

    analysis_id = _persist_analysis_result(
        db,
        current_user.id,
        request.analysis_type,
        {
            "polygon_wkt": area["polygon_wkt"],
            "latitude": request.latitude,
            "longitude": request.longitude,
            "radius_km": request.radius_km,
            "description": request.description,
        },
        result,
    )
    return InferResponse(
        result=PipelineResultResponse.model_validate(result.to_dict() | {"analysis_id": analysis_id}),
        created_analysis_id=analysis_id,
    )


@router.get("/models", response_model=list[ModelResponse])
def list_ai_models(
    name: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List registered model versions (optionally filtered by name)."""
    return list_models(db, name=name)


@router.post("/models", response_model=ModelResponse, status_code=201)
def register_model(
    payload: ModelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Register a new model version. Always starts as prototype; an admin
    must explicitly promote it to production (governance gate so simulated or
    unvalidated prototypes can never self-declare as production)."""
    try:
        model = create_model(
            db,
            name=payload.name,
            version=payload.version,
            framework=payload.framework,
            description=payload.description,
            parameters=payload.parameters,
            metrics=payload.metrics,
            artifact_uri=payload.artifact_uri,
            status="prototype",
        )
    except ModelValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    logger.info("Registered AI model", extra_keys={"name": payload.name, "version": payload.version})
    return model


@router.patch("/models/{model_id}/status", response_model=ModelResponse)
def update_model_status(
    model_id: int,
    payload: ModelStatusUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Promote/archive a model (admin only -- production status changes are a
    governance action, not an everyday one)."""
    try:
        updated = set_status(db, model_id, payload.status)
    except ModelValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="Model not found")
    logger.info(
        "Model status updated",
        extra_keys={"model_id": model_id, "status": payload.status, "actor": admin.username},
    )
    return updated


@router.get("/models/{model_id}", response_model=ModelResponse)
def get_model_details(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = get_model(db, model_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return serialize_model(row)