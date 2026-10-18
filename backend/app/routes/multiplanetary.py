"""Multi-planetary autonomy endpoints (Stage 0).

One decision stack for Earth, orbital, lunar and asteroid operations: seven
layers propose actions, mission control filters them by autonomy budget, and a
fail-safe trips on critical state. ``POST /multiplanetary/decide`` runs exactly
one cycle of that and returns what it produced -- the actions are proposals,
nothing here commands hardware, and the response says so.

Command signing (``app.multiplanetary.ops.security``) is deliberately not
exposed: it HMACs payloads with a built-in default key, which is a
placeholder for a deployment that has not chosen one yet.
"""

from fastapi import APIRouter, Depends

from app.ai.base import Provenance
from app.exceptions import NotFoundError
from app.models.user import User
from app.multiplanetary.layers.core import MissionContext
from app.multiplanetary.layers.stack import AuroraStack
from app.multiplanetary.ops.comms_delay import CommsDelayModel, TargetBody
from app.multiplanetary.simulation import PlanetaryEnvironment, get_environment
from app.schemas.multiplanetary import (
    ActionOut,
    CommsDelayResponse,
    EnvironmentDetailResponse,
    EnvironmentListResponse,
    EnvironmentOut,
    MissionContextIn,
    StackDecisionResponse,
)
from app.security import get_current_user

router = APIRouter(prefix="/multiplanetary", tags=["Multi-Planetary Autonomy"])

_ENVIRONMENTS = ("earth", "lunar", "mars", "asteroid")

_DECISION_LIMITATIONS = [
    "proposed actions are never executed: no hardware, no command uplink",
    "layer rules are hand-written heuristics, not learned policies",
    "safe mode is per-stack, and each request builds a fresh stack, so it cannot "
    "stay tripped across calls",
    "vision and terrain-relative navigation are not consulted: context is "
    "whatever the caller asserts",
]

_ENVIRONMENT_LIMITATIONS = [
    "constants are order-of-magnitude planning values, not mission-specific data",
    "terrain and hazard generators are seeded pseudo-random, not real surfaces",
    "one-way delay is a fixed per-body constant; real geometry changes daily",
]


def _action_rows(payload: list[dict]) -> list[ActionOut]:
    return [ActionOut.model_validate(row) for row in payload]


def _environment_out(env: PlanetaryEnvironment) -> EnvironmentOut:
    return EnvironmentOut(
        name=env.name,
        gravity_ms2=env.gravity_ms2,
        atmosphere_pressure_pa=env.atmosphere_pressure_pa,
        has_atmosphere=env.has_atmosphere,
        solar_flux_wm2=env.solar_flux_wm2,
        mean_temperature_c=env.mean_temperature_c,
        temperature_range_c=env.temperature_range_c,
        day_length_s=env.day_length_s,
        radiation_multiplier=env.radiation_multiplier,
        terrain_roughness=env.terrain_roughness,
        slope_range_deg=env.slope_range_deg,
        regolith_depth_m=env.regolith_depth_m,
    )


@router.post("/decide", response_model=StackDecisionResponse)
def run_decision_cycle(
    request: MissionContextIn,
    current_user: User = Depends(get_current_user),
):
    """Run one cycle of the seven-layer autonomy stack over a mission context."""
    stack = AuroraStack()
    decision = stack.step(MissionContext(**request.model_dump()))
    payload = decision.to_dict()

    return StackDecisionResponse(
        provenance=Provenance.SIMULATED,
        layers_evaluated=[
            stack.human_assistance.name,
            stack.resources.name,
            stack.infrastructure.name,
            stack.navigation.name,
            stack.robotics.name,
            stack.scientific.name,
            stack.mission_control.name,
        ],
        approved=_action_rows(payload["approved"]),
        pending_authorization=_action_rows(payload["pending_authorization"]),
        rejected=_action_rows(payload["rejected"]),
        safe_mode_active=payload["safe_mode_active"],
        warnings=list(payload["warnings"]),
        model_limitations=_DECISION_LIMITATIONS,
    )


@router.get("/environments", response_model=EnvironmentListResponse)
def list_environments(current_user: User = Depends(get_current_user)):
    """The planetary environments the autonomy stack can be pointed at."""
    return EnvironmentListResponse(
        provenance=Provenance.SIMULATED,
        environments=[_environment_out(get_environment(name)) for name in _ENVIRONMENTS],
        model_limitations=_ENVIRONMENT_LIMITATIONS,
    )


@router.get("/environments/{name}", response_model=EnvironmentDetailResponse)
def get_environment_profile(
    name: str,
    current_user: User = Depends(get_current_user),
):
    """One environment's constants.

    ``app.multiplanetary.simulation.get_environment`` quietly falls back to
    Earth for a name it does not know, which would turn a typo into a wrong
    answer, so the name is checked before it reaches that function.
    """
    if name not in _ENVIRONMENTS:
        raise NotFoundError(
            f"Unknown environment '{name}'",
            details={"known": list(_ENVIRONMENTS)},
        )
    return EnvironmentDetailResponse(
        provenance=Provenance.SIMULATED,
        environment=_environment_out(get_environment(name)),
        model_limitations=_ENVIRONMENT_LIMITATIONS,
    )


@router.get("/comms-delay/{target}", response_model=CommsDelayResponse)
def comms_delay(
    target: TargetBody,
    current_user: User = Depends(get_current_user),
):
    """One-way light time to a body and the autonomy it forces on operators."""
    model = CommsDelayModel.for_target(target)
    return CommsDelayResponse(
        provenance=Provenance.SIMULATED,
        target_body=model.target_body.value,
        owlt_s=model.owlt_seconds,
        rtt_s=round(model.round_trip_delay_s, 1),
        autonomy_level=model.autonomy_level,
        real_time=model.is_real_time_controllable(),
        recommended_contact_interval_s=round(model.recommended_contact_interval_s, 1),
        max_autonomous_operations_s=round(model.max_autonomous_operations_s, 1),
        model_limitations=[
            "mean distances: real one-way light time varies with orbital geometry",
            "autonomy level and contact interval are planning heuristics, not "
            "flight-rule values",
        ],
    )
