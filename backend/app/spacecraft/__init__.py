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

from app.spacecraft.adcs import ADCS, AttitudeState, SunSensor, Magnetometer, ReactionWheel, Magnetorquer
from app.spacecraft.power import PowerSystem, BatteryModel, SolarPanelModel
from app.spacecraft.thermal import ThermalModel
from app.spacecraft.comms import RadioTransceiver, Packet, GroundStation
from app.spacecraft.payload import PayloadManager, ImagingPayload
from app.spacecraft.fsw import FlightSoftware, TaskScheduler, FaultManager
from app.spacecraft.mission import MissionTimeline, GroundSegment, TelemetryDownlink
from app.spacecraft.simulation import SpacecraftSimulator, OrbitalState, EclipseModel

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