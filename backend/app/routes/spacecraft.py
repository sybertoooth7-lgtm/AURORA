"""CubeSat subsystem endpoints (AURORA Space Division, Stage 0).

Exposes ``app.spacecraft`` over HTTP so the platform can be shown and tested
as a whole system, not just as Earth observation. Everything here is model
code: the orbit propagator, the eclipse model, the power/thermal balance and
the link budget all run locally and deterministically, and each response says
so. No hardware telemetry, no two-line element sets, no live space-track data.
"""

import math

from fastapi import APIRouter, Depends, Query

from app.ai.base import Provenance
from app.models.user import User
from app.schemas.spacecraft import (
    LinkBudgetResponse,
    OrbitResponse,
    SpacecraftSimulateRequest,
    SpacecraftSimulateResponse,
)
from app.security import get_current_user
from app.space_division.constellation import OrbitalPlane
from app.spacecraft.comms import LinkBudget
from app.spacecraft.simulation import SpacecraftSimulator

router = APIRouter(prefix="/spacecraft", tags=["Spacecraft Simulation"])

_EARTH_RADIUS_KM = 6371.0
_ECLIPSE_FRACTION = 0.35

# The coupled simulator propagates a circular orbit at a fixed period and
# treats eclipse as a constant shadow fraction, so these are the honest limits
# of anything it reports.
_ORBIT_LIMITATIONS = [
    "circular orbit only: no eccentricity, no J2 or drag perturbation",
    f"eclipse uses a fixed {_ECLIPSE_FRACTION:.0%} shadow fraction, not a computed terminator",
    "no ground track and no access geometry to a specific station",
]

_SIMULATOR_LIMITATIONS = [
    *_ORBIT_LIMITATIONS,
    "the coupled loop keeps a 5550 s orbital period whatever the altitude; "
    "GET /spacecraft/orbit reports the Kepler value instead",
    "pointing error and packet counters are held at zero in the coupled loop",
    "the payload is never triggered inside the coupled loop, so images_captured "
    "is always zero",
    "the coupled thermal node receives no solar input, so its temperature is an "
    "internal-heat and radiator balance only",
]


@router.post("/simulate", response_model=SpacecraftSimulateResponse)
def simulate_mission(
    request: SpacecraftSimulateRequest,
    current_user: User = Depends(get_current_user),
):
    """Run the coupled ADCS/power/thermal/FSW/payload simulation for a window.

    The trajectory is sampled to `sample_points` evenly-spaced states so the
    response stays reviewable; the aggregates describe the whole run.
    """
    simulator = SpacecraftSimulator(
        altitude_km=request.altitude_km,
        inclination_deg=request.inclination_deg,
        dt=request.dt_s,
    )
    states = simulator.run(request.duration_s)

    socs = [state.power_battery_soc for state in states]
    temps = [state.thermal_temp_c for state in states]
    modes: list[str] = []
    for state in states:
        if not modes or modes[-1] != state.fsw_mode:
            modes.append(state.fsw_mode)

    stride = max(1, len(states) // request.sample_points)
    trajectory = [state.to_dict() for state in states[::stride]][: request.sample_points]

    return SpacecraftSimulateResponse(
        provenance=Provenance.SIMULATED,
        steps=len(states),
        duration_s=request.duration_s,
        orbital_period_s=states[-1].orbital.orbital_period_s,
        velocity_kms=round(states[-1].orbital.velocity_kms(), 4),
        eclipse_fraction=round(
            sum(1 for state in states if state.eclipse) / len(states), 4
        ),
        battery_soc_min=round(min(socs), 2),
        battery_soc_max=round(max(socs), 2),
        battery_soc_end=round(socs[-1], 2),
        temperature_min_c=round(min(temps), 2),
        temperature_max_c=round(max(temps), 2),
        fsw_modes=modes,
        images_captured=states[-1].payload_image_count,
        trajectory=trajectory,
        model_limitations=_SIMULATOR_LIMITATIONS,
    )


@router.get("/link-budget", response_model=LinkBudgetResponse)
def link_budget(
    distance_km: float = Query(default=1200.0, ge=1.0, le=40000.0),
    frequency_mhz: float = Query(default=435.0, ge=100.0, le=8000.0),
    tx_power_dbm: float = Query(default=30.0, ge=-10.0, le=60.0),
    rx_gain_dbi: float = Query(default=0.0, ge=-10.0, le=60.0),
    current_user: User = Depends(get_current_user),
):
    """Received power and SNR for one slant range, from the free-space model.

    Answers "can the station hear the satellite at this range" for planning
    only: a real UHF link needs antenna patterns, polarisation, atmospheric and
    rain attenuation, and a pointed, tracked antenna.
    """
    budget = LinkBudget(
        frequency_mhz=frequency_mhz,
        tx_power_dbm=tx_power_dbm,
        rx_gain_dbi=rx_gain_dbi,
    )
    return LinkBudgetResponse(
        provenance=Provenance.SIMULATED,
        frequency_mhz=frequency_mhz,
        tx_power_dbm=tx_power_dbm,
        distance_km=distance_km,
        path_loss_db=round(budget.free_space_path_loss_db(distance_km), 2),
        received_power_dbm=round(budget.received_power_dbm(distance_km), 2),
        snr_db=round(budget.snr_db(distance_km), 2),
        max_range_km_at_10db=round(budget.max_range_km(min_snr_db=10.0), 1),
        model_limitations=[
            "free-space path loss only: no atmospheric, rain or polarisation loss",
            "no antenna pattern, pointing or tracking losses",
            "system noise figure is one fixed value",
            "max range ignores antenna aperture, regulatory EIRP and any link margin",
        ],
    )


@router.get("/orbit", response_model=OrbitResponse)
def orbit_properties(
    altitude_km: float = Query(default=400.0, ge=200.0, le=2000.0),
    inclination_deg: float = Query(default=97.4, ge=0.0, le=180.0),
    current_user: User = Depends(get_current_user),
):
    """Keplerian period and velocity for a circular orbit at one altitude.

    Uses the same third-law computation as constellation fleet sizing, so the
    two division surfaces cannot disagree about how long one orbit takes.
    """
    plane = OrbitalPlane(inclination_deg=inclination_deg, altitude_km=altitude_km)
    radius_km = _EARTH_RADIUS_KM + altitude_km
    period_s = plane.period_minutes() * 60.0
    return OrbitResponse(
        provenance=Provenance.SIMULATED,
        altitude_km=altitude_km,
        inclination_deg=inclination_deg,
        period_min=round(plane.period_minutes(), 3),
        velocity_kms=round(2 * math.pi * radius_km / period_s, 4),
        eclipse_fraction_assumed=_ECLIPSE_FRACTION,
        model_limitations=_ORBIT_LIMITATIONS,
    )
