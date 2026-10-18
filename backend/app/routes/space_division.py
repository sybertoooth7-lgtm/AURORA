"""Space Division endpoints: constellation fleet sizing and ground-segment
contention (Stage 0).

Both endpoints are stateless planning tools -- a fleet or a set of contact
requests goes in, an assessment comes out. The revisit figure is the
back-of-envelope fleet-sizing estimate the engine implements, not a coverage
analysis, and the response says so rather than letting a planner forward it as
one.
"""

from fastapi import APIRouter, Depends

from app.ai.base import Provenance
from app.models.user import User
from app.schemas.space_division import (
    ConstellationEvaluateRequest,
    ConstellationEvaluateResponse,
    ContactConflict,
    GrantedContact,
    GroundContactScheduleRequest,
    GroundContactScheduleResponse,
    PlaneSummary,
)
from app.security import get_current_user
from app.space_division.constellation import (
    Constellation,
    GroundContactScheduler,
    OrbitalPlane,
    Satellite,
    SatelliteStatus,
)
from app.spacecraft.mission import ContactWindow

router = APIRouter(prefix="/space-division", tags=["Space Division"])

_REVISIT_LIMITATIONS = [
    "first-order fleet-sizing estimate, not a coverage analysis",
    "assumes evenly phased satellites and ignores swath width and field of view",
    "no latitude-dependent pass geometry or real ground-track spacing",
    "uses the first operational satellite's plane period for the whole fleet",
]

_GROUND_SEGMENT_LIMITATIONS = [
    "one antenna per station: no queue, recording or data relay",
    "priority order only: no fairness and no re-plan across the rest of the day",
    "contact windows are taken as given; nothing here propagates them",
]

# Contention is resolved purely from a satellite's id and priority, so a
# request without a fleet definition still schedules; this plane stands in for
# the orbital details the scheduler never reads.
_DEFAULT_PLANE = OrbitalPlane(inclination_deg=97.4, altitude_km=500.0)


@router.post("/constellation", response_model=ConstellationEvaluateResponse)
def evaluate_constellation(
    request: ConstellationEvaluateRequest,
    current_user: User = Depends(get_current_user),
):
    """Size a fleet: the planes it occupies and the revisit estimate between passes."""
    fleet = Constellation(request.name)
    for entry in request.satellites:
        plane = OrbitalPlane(
            inclination_deg=entry.plane.inclination_deg,
            altitude_km=entry.plane.altitude_km,
            raan_deg=entry.plane.raan_deg,
        )
        fleet.add_satellite(
            Satellite(
                id=entry.id,
                name=entry.name or entry.id,
                plane=plane,
                phase_deg=entry.phase_deg,
                status=SatelliteStatus(entry.status),
                priority=entry.priority,
            )
        )

    counts: dict[tuple[float, float, float], int] = {}
    for satellite in fleet.satellites():
        key = (
            satellite.plane.inclination_deg,
            satellite.plane.altitude_km,
            satellite.plane.raan_deg,
        )
        counts[key] = counts.get(key, 0) + 1

    planes = [
        PlaneSummary(
            inclination_deg=inclination,
            altitude_km=altitude,
            raan_deg=raan,
            period_min=round(
                OrbitalPlane(
                    inclination_deg=inclination, altitude_km=altitude, raan_deg=raan
                ).period_minutes(),
                3,
            ),
            satellites=count,
        )
        for (inclination, altitude, raan), count in sorted(counts.items())
    ]

    revisit = fleet.estimated_revisit_interval_hours()
    return ConstellationEvaluateResponse(
        provenance=Provenance.SIMULATED,
        name=fleet.name,
        satellites=len(fleet.satellites()),
        operational=len(fleet.operational_satellites()),
        planes=planes,
        revisit_interval_hours=round(revisit, 3) if revisit is not None else None,
        model_limitations=_REVISIT_LIMITATIONS,
    )


@router.post("/ground-contacts", response_model=GroundContactScheduleResponse)
def schedule_ground_contacts(
    request: GroundContactScheduleRequest,
    current_user: User = Depends(get_current_user),
):
    """Grant or refuse overlapping downlink requests for the same station."""
    pairs = []
    for entry in request.requests:
        satellite = Satellite(
            id=entry.satellite_id,
            name=entry.satellite_id,
            plane=_DEFAULT_PLANE,
            priority=entry.priority,
        )
        window = ContactWindow(
            ground_station=entry.ground_station,
            start_s=entry.start_s,
            end_s=entry.end_s,
            max_elevation_deg=entry.max_elevation_deg,
            slant_range_km=entry.slant_range_km,
        )
        pairs.append((satellite, window))

    granted, conflicts = GroundContactScheduler().schedule(pairs)

    return GroundContactScheduleResponse(
        provenance=Provenance.SIMULATED,
        requested=len(pairs),
        granted=[
            GrantedContact(
                satellite_id=satellite.id,
                ground_station=window.ground_station,
                start_s=window.start_s,
                end_s=window.end_s,
                duration_s=round(window.duration_s, 3),
                max_elevation_deg=window.max_elevation_deg,
                slant_range_km=window.slant_range_km,
            )
            for satellite, window in granted
        ],
        conflicts=[
            ContactConflict(
                satellite_id=conflict.satellite_id,
                ground_station=conflict.request.ground_station,
                start_s=conflict.request.start_s,
                end_s=conflict.request.end_s,
                reason=conflict.reason,
            )
            for conflict in conflicts
        ],
        model_limitations=_GROUND_SEGMENT_LIMITATIONS,
    )
