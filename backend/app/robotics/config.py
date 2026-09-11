"""Configuration schemas for robotics, spacecraft, and multi-planetary systems.

Defines dataclasses that validate and document every tunable parameter.
All configs default to realistic Earth-based values; spacecraft and
planetary configs override specific fields.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Environment(Enum):
    EARTH = "earth"
    LUNAR = "lunar"
    MARS = "mars"
    ASTEROID = "asteroid"
    ORBITAL = "orbital"


class RobotPlatform(Enum):
    GROUND_ROVER = "ground_rover"
    UGV = "ugv"
    UAV = "uav"
    CUBESAT = "cubesat"
    LANDER = "lander"
    ROVER_PLANETARY = "rover_planetary"


@dataclass
class SensorConfig:
    name: str
    sensor_type: str
    sampling_hz: float = 10.0
    noise_std: float = 0.02
    range_m: float = 100.0
    fov_deg: float = 60.0
    resolution: tuple | None = None
    is_simulated: bool = True


@dataclass
class ActuatorConfig:
    name: str
    actuator_type: str
    max_velocity: float = 1.0
    max_torque: float = 10.0
    efficiency: float = 0.85
    is_simulated: bool = True


@dataclass
class NavigationConfig:
    planner: str = "astar"
    grid_resolution: float = 0.5
    grid_width: int = 200
    grid_height: int = 200
    replan_interval_s: float = 5.0
    obstacle_inflation_cells: int = 2
    reach_threshold_m: float = 0.5


@dataclass
class PerceptionConfig:
    backend: str = "synthetic"
    model_name: str = "none"
    confidence_threshold: float = 0.5
    nms_iou_threshold: float = 0.5
    max_detections: int = 50


@dataclass
class PowerConfig:
    capacity_wh: float = 100.0
    nominal_voltage: float = 12.0
    solar_area_m2: float = 0.0
    solar_efficiency: float = 0.22
    base_draw_w: float = 5.0
    battery_chemistry: str = "LiFePO4"
    min_voltage: float = 10.0


@dataclass
class ThermalConfig:
    min_operating_c: float = -20.0
    max_operating_c: float = 60.0
    heater_power_w: float = 5.0
    radiator_area_m2: float = 0.01
    thermal_mass_j_per_k: float = 100.0
    environment_c: float = 25.0


@dataclass
class CommsConfig:
    band: str = "UHF"
    frequency_mhz: float = 435.0
    data_rate_bps: int = 9600
    max_packet_bytes: int = 256
    protocol: str = "AX.25"
    store_and_forward: bool = False


@dataclass
class ADCSConfig:
    controller: str = "pid"
    reaction_wheel_max_rpm: float = 6000.0
    reaction_wheel_max_torque_nm: float = 0.001
    magnetorquer_max_dipole_aim: float = 0.5
    sun_sensor_fov_deg: float = 120.0
    magnetometer_noise_ut: float = 0.5
    pointing_accuracy_deg: float = 1.0


@dataclass
class MissionConfig:
    environment: Environment = Environment.EARTH
    platform: RobotPlatform = RobotPlatform.GROUND_ROVER
    mission_name: str = "aurora-mission"
    duration_days: float = 30.0
    target_area_km2: float = 1.0
    auto_telemetry_interval_s: float = 10.0


@dataclass
class RoboticsConfig:
    mission: MissionConfig = field(default_factory=MissionConfig)
    sensors: list[SensorConfig] = field(default_factory=list)
    actuators: list[ActuatorConfig] = field(default_factory=list)
    navigation: NavigationConfig = field(default_factory=NavigationConfig)
    perception: PerceptionConfig = field(default_factory=PerceptionConfig)
    power: PowerConfig = field(default_factory=PowerConfig)
    thermal: ThermalConfig = field(default_factory=ThermalConfig)
    comms: CommsConfig = field(default_factory=CommsConfig)
    adcs: ADCSConfig = field(default_factory=ADCSConfig)

    def to_dict(self) -> dict[str, Any]:
        from dataclasses import asdict
        return asdict(self)
