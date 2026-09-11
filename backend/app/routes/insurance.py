"""Parametric agriculture-insurance endpoint (AURORA-2 Earth revenue).

``POST /insurance/trigger-check`` runs the insurance-index pipeline over an
area and applies the policy trigger. Payout figures are honest *estimates*
for underwriting review -- provenance is disclosed, simulated runs are
flagged in the response, and nothing here auto-settles a claim.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai.registry import UnknownPipelineError
from app.config import get_settings
from app.database import get_db
from app.exceptions import PipelineUnavailableError, SatelliteDataUnavailableError
from app.logging_conf import get_logger
from app.models.analysis import AnalysisType
from app.models.user import User
from app.routes.ai import _fetch_observation, _persist_analysis_result
from app.routes.analysis import build_area_polygon_wkt
from app.schemas.ai import PipelineResultResponse
from app.schemas.insurance import TriggerCheckRequest, TriggerCheckResponse
from app.security import get_current_user
from app.services.insurance import evaluate_trigger

logger = get_logger(__name__)

router = APIRouter(prefix="/insurance", tags=["Insurance (Parametric)"])


@router.post("/trigger-check", response_model=TriggerCheckResponse)
def trigger_check(
    request: TriggerCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check whether a parametric policy trigger has been breached.

    Runs the ``insurance_index`` pipeline synchronously, persists the run
    (audit trail on the dashboard), and returns whether the policy's trigger
    threshold is crossed along with an estimated payout for planning. The
    estimate is explicitly not a settlement.
    """
    area = build_area_polygon_wkt(
        latitude=request.latitude,
        longitude=request.longitude,
        radius_km=request.radius_km,
    )
    try:
        result, observation = _fetch_observation(
            AnalysisType.INSURANCE_INDEX,
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
        AnalysisType.INSURANCE_INDEX,
        {
            "polygon_wkt": area["polygon_wkt"],
            "latitude": request.latitude,
            "longitude": request.longitude,
            "radius_km": request.radius_km,
            "description": request.description,
        },
        result,
    )

    severity = result.severity
    trigger = evaluate_trigger(
        severity=severity,
        sum_insured_usd=request.sum_insured_usd,
        trigger_threshold=request.trigger_threshold,
        coverage_ratio=request.coverage_ratio,
    )
    breached = trigger.trigger_breached

    warning = None
    if result.provenance.value == "simulated":
        warning = (
            "Simulated observation (demo provider): no live Sentinel data is "
            "configured for this deployment. This is an estimate for pipeline "
            "evaluation only -- never a basis for settlement."
        )

    data_quality = "simulated" if result.provenance.value == "simulated" else "real"

    logger.info(
        "Trigger check evaluated",
        extra_keys={
            "user_id": current_user.id,
            "policy_id": request.policy_id,
            "breached": breached,
            "severity": severity,
            "estimated_liability_usd": trigger.estimated_liability_usd,
            "provenance": result.provenance.value,
        },
    )

    return TriggerCheckResponse(
        result=PipelineResultResponse.model_validate(
            result.to_dict() | {"analysis_id": analysis_id}
        ),
        analysis_id=analysis_id,
        policy_id=request.policy_id,
        crop_type=request.crop_type,
        trigger_threshold=request.trigger_threshold,
        severity_at_check=round(severity, 4),
        trigger_breached=breached,
        estimated_liability_usd=trigger.estimated_liability_usd,
        payout_usd=trigger.payout_usd,
        coverage_ratio=request.coverage_ratio,
        data_quality=data_quality,
        warning=warning,
    )


@router.get("/defaults")
def insurance_defaults():
    """Public defaults+limits a policy UI can render before calling trigger-check."""
    settings = get_settings()
    return {
        "trigger_threshold": settings.INSURANCE_DEFAULT_TRIGGER_THRESHOLD,
        "max_sum_insured_usd": settings.INSURANCE_MAX_SUM_INSURED_USD,
        "analysis_type": AnalysisType.INSURANCE_INDEX.value,
    }
