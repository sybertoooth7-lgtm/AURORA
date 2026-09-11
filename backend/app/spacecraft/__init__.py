"""AURORA Spacecraft: CubeSat-class technology demonstrator.

Software architecture for a 3U CubeSat mission.  Every subsystem is
a Python class with a deterministic simulation backend.  The same
interfaces scale to lunar, Mars, and deep-space missions.

Design principles
-----------------
* Simulation-first: every subsystem has a ``tick(dt)`` method that
  advances its state.  Hardware backends (CAN bus, I2C) implement the
  same interface.
* Fault tolerance: every subsystem exposes health status and can be
  put into safe mode.
* Store-and-forward: deep-space comms require local storage before
  relay -- modelled explicitly so it can be tested.
"""

from app.spacecraft.adcs import (
    ADCS,
    AttitudeState,
    Magnetometer,
    Magnetorquer,
    ReactionWheel,
    SunSensor,
)
from app.spacecraft.comms import GroundStation, Packet, RadioTransceiver
from app.spacecraft.fsw import FaultManager, FlightSoftware, TaskScheduler
from app.spacecraft.mission import GroundSegment, MissionTimeline, TelemetryDownlink
from app.spacecraft.payload import ImagingPayload, PayloadManager
from app.spacecraft.power import BatteryModel, PowerSystem, SolarPanelModel
from app.spacecraft.simulation import EclipseModel, OrbitalState, SpacecraftSimulator
from app.spacecraft.thermal import ThermalModel

__all__ = [
    "ADCS", "AttitudeState", "SunSensor", "Magnetometer", "ReactionWheel", "Magnetorquer",
    "PowerSystem", "BatteryModel", "SolarPanelModel",
    "ThermalModel", "HeaterController",
    "RadioTransceiver", "Packet", "GroundStation",
    "PayloadManager", "ImagingPayload",
    "FlightSoftware", "TaskScheduler", "FaultManager",
    "MissionTimeline", "GroundSegment", "TelemetryDownlink",
    "SpacecraftSimulator", "OrbitalState", "EclipseModel",
]
