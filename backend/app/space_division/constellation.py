"""Satellite constellation management -- the actual gap in AURORA's Space
Division (Earth Observation, CubeSat Technology, and Deep Space
Infrastructure already exist elsewhere; see the package README).

Stage 0 simulation, same house style as app.spacecraft and app.robotics:
deterministic, offline-testable, no hardware or live-route dependency yet.
Two concerns, deliberately separate from single-spacecraft mission ops
(app.spacecraft.mission) because they only exist once there's more than
one spacecraft:

1. Fleet composition -- which satellites exist, which orbital plane and
   phase slot each occupies, and a first-order revisit-time estimate for
   fleet-sizing planning (NOT a rigorous coverage analysis -- see
   `estimated_revisit_interval_hours` for exactly what it does and
   doesn't account for).
2. Ground-segment contention -- AURORA's plan is one primary ground
   station (see app/spacecraft/README.md); once there's more than one
   satellite, more than one can want that station's antenna at the same
   time. GroundContactScheduler resolves those conflicts by priority,
   reusing app.spacecraft.mission.ContactWindow rather than redefining it.
"""

import math
from dataclasses import dataclass
from enum import Enum

from app.spacecraft.mission import ContactWindow

_EARTH_RADIUS_KM = 6371.0
_MU_EARTH_KM3_S2 = 398600.4418  # standard gravitational parameter of Earth


class SatelliteStatus(Enum):
    COMMISSIONING = "commissioning"
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    DECOMMISSIONED = "decommissioned"


@dataclass(frozen=True)
class OrbitalPlane:
    """One orbital plane in a Walker-style constellation."""

    inclination_deg: float
    altitude_km: float
    raan_deg: float = 0.0  # right ascension of ascending node -- separates planes

    def period_minutes(self) -> float:
        """Circular-orbit period via Kepler's third law.

        Approximate -- ignores J2 and other perturbations, which is fine
        for fleet-sizing but not for precision orbit determination.
        """
        semi_major_axis_km = _EARTH_RADIUS_KM + self.altitude_km
        period_s = 2 * math.pi * math.sqrt(semi_major_axis_km**3 / _MU_EARTH_KM3_S2)
        return period_s / 60.0


@dataclass
class Satellite:
    id: str
    name: str
    plane: OrbitalPlane
    phase_deg: float = 0.0  # position within the plane, 0-360
    status: SatelliteStatus = SatelliteStatus.COMMISSIONING
    priority: int = 0  # higher wins ground-contact conflicts


class Constellation:
    """A fleet of satellites, grouped by orbital plane."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._satellites: dict[str, Satellite] = {}

    def add_satellite(self, satellite: Satellite) -> None:
        self._satellites[satellite.id] = satellite

    def get(self, satellite_id: str) -> Satellite | None:
        return self._satellites.get(satellite_id)

    def satellites(self) -> list[Satellite]:
        return list(self._satellites.values())

    def operational_satellites(self) -> list[Satellite]:
        return [s for s in self._satellites.values() if s.status == SatelliteStatus.OPERATIONAL]

    def satellites_in_plane(self, plane: OrbitalPlane) -> list[Satellite]:
        return [s for s in self._satellites.values() if s.plane == plane]

    def estimated_revisit_interval_hours(self) -> float | None:
        """First-order fleet-sizing estimate, NOT a rigorous coverage
        analysis: assumes satellites are evenly phased and estimates the
        average gap between passes over an arbitrary point as (orbital
        period) / (operational satellite count) -- the standard rough
        back-of-envelope formula used at the "how many satellites do we
        need" planning stage. It does NOT account for swath width, sensor
        field of view, latitude-dependent pass geometry, or real
        ground-track spacing; an actual coverage analysis needs a proper
        orbital propagator and is out of scope here.
        """
        operational = self.operational_satellites()
        if not operational:
            return None
        # Uses the first operational satellite's plane period -- fleet
        # sizing at this level normally assumes near-identical altitudes
        # across planes anyway (the standard Walker-constellation choice).
        period_minutes = operational[0].plane.period_minutes()
        return (period_minutes / 60.0) / len(operational)


@dataclass
class GroundContactConflict:
    request: ContactWindow
    satellite_id: str
    reason: str


class GroundContactScheduler:
    """Resolves ground-station contention across a fleet.

    A single-antenna ground station can serve one satellite at a time --
    this grants each requested ContactWindow in priority order (by the
    requesting satellite's `priority`, then by earliest start) and
    reports which requests lost the contention and to whom.
    """

    def schedule(
        self, requests: list[tuple[Satellite, ContactWindow]]
    ) -> tuple[list[tuple[Satellite, ContactWindow]], list[GroundContactConflict]]:
        ordered = sorted(requests, key=lambda pair: (-pair[0].priority, pair[1].start_s))
        granted: list[tuple[Satellite, ContactWindow]] = []
        conflicts: list[GroundContactConflict] = []
        busy: dict[str, list[tuple[float, float]]] = {}

        for satellite, window in ordered:
            station_busy = busy.setdefault(window.ground_station, [])
            overlap = any(
                window.start_s < end and start < window.end_s for start, end in station_busy
            )
            if overlap:
                conflicts.append(
                    GroundContactConflict(
                        request=window,
                        satellite_id=satellite.id,
                        reason=(
                            f"ground station '{window.ground_station}' already "
                            f"committed to {self._holder(granted, window)} during this window"
                        ),
                    )
                )
                continue
            station_busy.append((window.start_s, window.end_s))
            granted.append((satellite, window))

        return granted, conflicts

    @staticmethod
    def _holder(
        granted: list[tuple[Satellite, ContactWindow]], window: ContactWindow
    ) -> str:
        for sat, granted_window in granted:
            if (
                granted_window.ground_station == window.ground_station
                and window.start_s < granted_window.end_s
                and granted_window.start_s < window.end_s
            ):
                return sat.id
        return "another satellite"
