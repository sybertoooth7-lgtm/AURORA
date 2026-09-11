"""Onboarding flow endpoints (AURORA-2 conversion milestone).

Guides a new account through the shortest path to an operational setup:
account created, live satellite source connected (or the honest demo-provider
fallback explained), and the first analysis run. ``POST /onboarding/complete``
records completion on the user row; ``GET /onboarding/status`` recomputes the
checklist dynamically so re-visiting the dashboard updates progress.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai.registry import UnknownPipelineError
from app.config import get_settings
from app.database import get_db
from app.exceptions import PipelineUnavailableError, SatelliteDataUnavailableError
from app.logging_conf import get_logger
from app.models.analysis import Analysis
from app.models.user import User
from app.routes.ai import _fetch_observation, _persist_analysis_result
from app.routes.analysis import build_area_polygon_wkt
from app.schemas.ai import PipelineResultResponse
from app.schemas.onboarding import (
    FirstAnalysisRequest,
    FirstAnalysisResponse,
    OnboardingChecklistItem,
    OnboardingStatus,
)
from app.security import get_current_user

logger = get_logger(__name__)

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])


def has_live_satellite() -> bool:
    settings = get_settings()
    return bool(settings.SENTINEL_CLIENT_ID and settings.SENTINEL_CLIENT_SECRET)


def build_onboarding_status(
    user: User,
    *,
    analysis_count: int,
    live_satellite: bool,
    pipeline_count: int,
    onboarding_complete: bool,
) -> OnboardingStatus:
    """Pure builder so the flow is unit-testable without a DB session."""
    settings = get_settings()
    checklist: list = []
    if onboarding_complete:
        checklist.append(
            OnboardingChecklistItem(
                id="account", label="Create an account", done=True
            )
        )
        checklist.append(
            OnboardingChecklistItem(
                id="satellite_source", label="Connect live satellite data", done=live_satellite
            )
        )
        checklist.append(
            OnboardingChecklistItem(
                id="first_analysis", label="Run your first analysis", done=analysis_count > 0
            )
        )
        checklist.append(
            OnboardingChecklistItem(
                id="pipeline_review", label="Review available AI pipelines", done=True
            )
        )
    else:
        sentinel_instructions = None
        if not live_satellite:
            sentinel_instructions = (
                f"Create a free OAuth client at {settings.ONBOARDING_SENTINEL_SETUP_URL} "
                "(User Settings -> OAuth clients), set SENTINEL_CLIENT_ID and "
                "SENTINEL_CLIENT_SECRET in backend/.env, then restart the API. Until "
                "then AURORA uses a deterministic demo provider and every output is "
                "marked simulated."
            )
        checklist = [
            OnboardingChecklistItem(id="account", label="Create an account", done=True),
            OnboardingChecklistItem(
                id="satellite_source",
                label="Connect live satellite data (Sentinel Hub)",
                done=live_satellite,
                instructions=sentinel_instructions,
            ),
            OnboardingChecklistItem(
                id="first_analysis",
                label="Run your first analysis",
                done=analysis_count > 0,
                instructions=(
                    None
                    if analysis_count > 0
                    else "POST /onboarding/first-analysis with an area of interest to "
                    "run your first vegetation-stress check end-to-end."
                ),
            ),
            OnboardingChecklistItem(
                id="pipeline_review",
                label="Review available AI pipelines",
                done=pipeline_count > 0,
                instructions=(
                    None if pipeline_count > 0 else "GET /ai/pipelines lists every pipeline."
                ),
            ),
        ]

    done_items = sum(1 for item in checklist if item.done)
    progress = round(done_items / len(checklist) * 100) if checklist else 100
    next_action = next(
        (item.id for item in checklist if not item.done),
        "onboarding_complete" if not onboarding_complete else "all_done",
    )

    return OnboardingStatus(
        user_id=user.id,
        username=user.username,
        completed=onboarding_complete or progress == 100,
        progress=progress,
        checklist=checklist,
        next_action=next_action,
    )


@router.get("/status", response_model=OnboardingStatus)
def get_onboarding_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    analysis_count = (
        db.query(Analysis).filter(Analysis.user_id == current_user.id).count()
    )
    pipeline_count = 0
    try:
        from app.ai.registry import get_registry

        pipeline_count = len(get_registry().list_active())
    except Exception:  # pragma: no cover - registry is import-time deterministic
        pass
    return build_onboarding_status(
        current_user,
        analysis_count=analysis_count,
        live_satellite=has_live_satellite(),
        pipeline_count=pipeline_count,
        onboarding_complete=current_user.onboarding_completed_at is not None,
    )


@router.post("/complete", response_model=OnboardingStatus)
def complete_onboarding(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark onboarding complete (idempotent)."""
    if current_user.onboarding_completed_at is None:
        current_user.onboarding_completed_at = datetime.now(UTC)
        db.commit()
        db.refresh(current_user)
    logger.info(
        "Onboarding completed",
        extra_keys={"user_id": current_user.id, "username": current_user.username},
    )
    return get_onboarding_status(db, current_user)


@router.post("/first-analysis", response_model=FirstAnalysisResponse)
def run_first_analysis(
    request: FirstAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Guided first analysis -- one call from zero to a completed run.

    Runs the requested pipeline synchronously, persists it like /ai/infer,
    and returns the result plus honest next steps (e.g. 'connect live data')
    appropriate for a brand-new account.
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

    next_steps: list = [
        "View the persisted run under /analysis/ or in the dashboard.",
        "Review all pipelines at /ai/pipelines.",
    ]
    if result.provenance.value == "simulated":
        next_steps.append(
            "Connect live Sentinel Hub credentials (see /onboarding/status) to "
            "replace simulated results with real observation data."
        )

    logger.info(
        "First analysis executed",
        extra_keys={"user_id": current_user.id, "analysis_type": request.analysis_type.value},
    )
    return FirstAnalysisResponse(
        result=PipelineResultResponse.model_validate(
            result.to_dict() | {"analysis_id": analysis_id}
        ),
        created_analysis_id=analysis_id,
        next_steps=next_steps,
    )
