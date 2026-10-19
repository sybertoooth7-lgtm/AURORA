"""Schemas for the multi-planetary autonomy endpoints."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.simulation import SimulationResponse

EnvironmentName = Literal["earth", "lunar", "mars", "asteroid"]
DelayTargetName = Literal[
    "earth_leo", "moon", "mars", "jupiter", "saturn", "asteroid", "deep_space"
]


class MissionContextIn(BaseModel):
    """The state the decision stack is shown before it proposes anything."""

    timestamp: float = Field(default=0.0, ge=0.0)
    environment: str = Field(default="earth", max_length=30)
    target_body: str = Field(default="earth", max_length=30)
    autonomy_level: int = Field(default=3, ge=1, le=5)
    one_way_delay_s: float = Field(default=0.0, ge=0.0)
    in_contact: bool = True
    battery_percent: float = Field(default=100.0, ge=0.0, le=100.0)
    power_available_w: float = Field(default=100.0, ge=0.0)
    power_demand_w: float = Field(default=50.0, ge=0.0)
    temperature_c: float = Field(default=25.0, ge=-273.0, le=200.0)
    navigation: dict[str, Any] = Field(default_factory=dict)
    inventory: dict[str, float] = Field(default_factory=dict)
    infrastructure: dict[str, Any] = Field(default_factory=dict)
    fleet: dict[str, Any] = Field(default_factory=dict)
    environment_sensor: dict[str, Any] = Field(default_factory=dict)
    science_hypotheses: list[dict[str, Any]] = Field(default_factory=list)
    current_plan: str = Field(default="", max_length=500)
    warnings: list[str] = Field(default_factory=list, max_length=50)


class ActionOut(BaseModel):
    layer: str
    action_type: str
    target: str
    description: str
    requires_authorization: bool
    reversible: bool
    severity: str


class StackDecisionResponse(SimulationResponse):
    layers_evaluated: list[str]
    approved: list[ActionOut]
    pending_authorization: list[ActionOut]
    rejected: list[ActionOut]
    safe_mode_active: bool
    warnings: list[str]


class EnvironmentOut(BaseModel):
    name: str
    gravity_ms2: float
    atmosphere_pressure_pa: float
    has_atmosphere: bool
    solar_flux_wm2: float
    mean_temperature_c: float
    temperature_range_c: tuple[float, float]
    day_length_s: float
    radiation_multiplier: float
    terrain_roughness: float
    slope_range_deg: tuple[float, float]
    regolith_depth_m: float


class EnvironmentListResponse(SimulationResponse):
    environments: list[EnvironmentOut]


class EnvironmentDetailResponse(SimulationResponse):
    """One environment on its own, so the constants cannot travel unlabelled."""

    environment: EnvironmentOut


class CommsDelayResponse(SimulationResponse):
    target_body: str
    owlt_s: float
    rtt_s: float
    autonomy_level: int
    real_time: bool
    recommended_contact_interval_s: float
    max_autonomous_operations_s: float
