"""CubeSat orbital simulation.

Deterministic LEO orbit propagator (simplified Keplerian), eclipse
calculator, and ground station visibility model.  No external orbit
propagator dependency -- everything runs offline for testing.

Orbit model (LEO)
-----------------
* Circular orbit (no eccentricity, no J2 for MVP).
* Constant altitude, constant orbital period.
* Eclipse: simple spherical-geometry shadow model.
* Ground station visibility: elevation angle from slant range.
"""

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from app.spacecraft.adcs import ADCS, AttitudeState
from app.spacecraft.comms import GroundStation, RadioTransceiver
from app.spacecraft.power import PowerSystem
from app.spacecraft.thermal import ThermalModel
from app.spacecraft.fsw import FlightSoftware, FSWMode
from app.spacecraft.payload import ImagingPayload, PayloadManager
from app.spacecraft.mission import MissionTimeline, GroundSegment, TelemetryDownlink


@dataclass
class OrbitalState:
    altitude_km: float = 400.0
    inclination_deg: float = 97.4
    raan_deg: float = 0.0
    true_anomaly_deg: float = 0.0
    orbital_period_s: float = 5550.0

    def update(self, dt: float) -> None:
        angular_vel_deg = 360.0 / self.orbital_period_s
        self.true_anomaly_deg = (self.true_anomaly_deg + angular_vel_deg * dt) % 360.0

    @property
    def position_eci(self) -> Tuple[float, float, float]:
        r = 6371.0 + self.altitude_km
        ta = math.radians(self.true_anomaly_deg)
        return (r * math.cos(ta), r * math.sin(ta), 0.0)

    def velocity_kms(self) -> float:
        r = (6371.0 + self.altitude_km) * 1000.0
        mu = 3.986e14
        return math.sqrt(mu / r) / 1000.0


class EclipseModel:
    def __init__(self, altitude_km: float = 400.0):
        self.altitude_km = altitude_km
        self._shadow_fraction = 0.35

    def is_in_eclipse(self, true_anomaly_deg: float) -> bool:
        ta = true_anomaly_deg % 360.0
        eclipse_center = 180.0
        half_shadow = 180.0 * self._shadow_fraction
        return abs(ta - eclipse_center) < half_shadow

    def sun_angle_cos(self, true_anomaly_deg: float) -> float:
        ta = math.radians(true_anomaly_deg)
        return math.cos(ta)


@dataclass
class SpacecraftState:
    timestamp: float
    orbital: OrbitalState
    eclipse: bool
    sun_angle_cos: float
    power_battery_soc: float
    thermal_temp_c: float
    adcs_pointing_error_deg: float
    fsw_mode: str
    payload_image_count: int
    comms_packets_tx: int
    comms_packets_rx: int

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "altitude_km": self.orbital.altitude_km,
            "true_anomaly_deg": round(self.orbital.true_anomaly_deg, 2),
            "eclipse": self.eclipse,
            "battery_soc": round(self.power_battery_soc, 2),
            "temp_c": round(self.thermal_temp_c, 2),
            "pointing_error_deg": round(self.adcs_pointing_error_deg, 3),
            "fsw_mode": self.fsw_mode,
            "images": self.payload_image_count,
            "tx": self.comms_packets_tx,
            "rx": self.comms_packets_rx,
        }


class SpacecraftSimulator:
    """Full CubeSat simulation tying all subsystems together.

    Advances the orbit, checks eclipse, drives power/thermal/ADCS/FSW,
    and produces a state snapshot each tick.
    """

    def __init__(
        self,
        altitude_km: float = 400.0,
        inclination_deg: float = 97.4,
        dt: float = 1.0,
    ):
        self.dt = dt
        self.time = 0.0
        self.orbital = OrbitalState(altitude_km=altitude_km, inclination_deg=inclination_deg)
        self.eclipse_model = EclipseModel(altitude_km)
        self.power = PowerSystem()
        self.thermal = ThermalModel()
        self.adcs = ADCS()
        self.fsw = FlightSoftware()
        self.fsw.boot(0.0)
        self.payload = ImagingPayload()
        self.payload_manager = PayloadManager()
        self.payload_manager.add_payload("camera", self.payload)
        self.ground_segment = GroundSegment()
        self.telemetry = TelemetryDownlink()
        self._history: List[SpacecraftState] = []
        self._ground_station = GroundStation("gs-0", 0.0, 0.0)
        self.ground_segment.add_station("gs-0", self._ground_station)

    def tick(self) -> SpacecraftState:
        self.orbital.update(self.dt)
        self.time += self.dt
        eclipse = self.eclipse_model.is_in_eclipse(self.orbital.true_anomaly_deg)
        sun_cos = self.eclipse_model.sun_angle_cos(self.orbital.true_anomaly_deg)
        power_bgt = self.power.tick(self.dt, sun_cos, eclipse)
        therm_st = self.thermal.tick(self.dt, eclipse=eclipse)
        self.adcs.tick(self.dt)
        fsw_out = self.fsw.tick(self.time)
        state = SpacecraftState(
            timestamp=self.time,
            orbital=OrbitalState(
                altitude_km=self.orbital.altitude_km,
                true_anomaly_deg=self.orbital.true_anomaly_deg,
                orbital_period_s=self.orbital.orbital_period_s,
            ),
            eclipse=eclipse,
            sun_angle_cos=sun_cos,
            power_battery_soc=power_bgt.battery_soc_percent,
            thermal_temp_c=therm_st.temperature_c,
            adcs_pointing_error_deg=0.0,
            fsw_mode=fsw_out["mode"],
            payload_image_count=self.payload.image_count,
            comms_packets_tx=0,
            comms_packets_rx=0,
        )
        self._history.append(state)
        return state

    def run(self, duration_s: float) -> List[SpacecraftState]:
        steps = int(duration_s / self.dt)
        for _ in range(steps):
            self.tick()
        return self._history

    @property
    def history(self) -> List[SpacecraftState]:
        return list(self._history)

    def reset(self) -> None:
        self.time = 0.0
        self.orbital.true_anomaly_deg = 0.0
        self.power.battery.reset_cycles()
        self._history.clear()