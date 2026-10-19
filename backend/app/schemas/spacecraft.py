"""Schemas for the CubeSat subsystem endpoints."""

from pydantic import BaseModel, Field

from app.schemas.simulation import SimulationResponse

MAX_SAMPLE_POINTS = 200


class SpacecraftSimulateRequest(BaseModel):
    """Run the coupled 3U CubeSat simulator for a window of mission time."""

    altitude_km: float = Field(default=400.0, ge=200.0, le=2000.0)
    inclination_deg: float = Field(default=97.4, ge=0.0, le=180.0)
    duration_s: float = Field(default=5550.0, ge=60.0, le=86400.0)
    dt_s: float = Field(default=10.0, ge=1.0, le=600.0)
    sample_points: int = Field(default=40, ge=2, le=MAX_SAMPLE_POINTS)


class SpacecraftSimulateResponse(SimulationResponse):
    """Summary of one simulated mission window, plus a sampled trajectory."""

    steps: int
    duration_s: float
    orbital_period_s: float
    velocity_kms: float
    eclipse_fraction: float = Field(
        description="Share of the window the simulator placed the spacecraft in shadow."
    )
    battery_soc_min: float
    battery_soc_max: float
    battery_soc_end: float
    temperature_min_c: float
    temperature_max_c: float
    fsw_modes: list[str]
    images_captured: int
    trajectory: list[dict] = Field(
        default_factory=list,
        description="Evenly-spaced state snapshots, capped by sample_points.",
    )


class LinkBudgetResponse(SimulationResponse):
    """Free-space link budget between the spacecraft and a ground station."""

    frequency_mhz: float
    tx_power_dbm: float
    distance_km: float
    path_loss_db: float
    received_power_dbm: float
    snr_db: float
    max_range_km_at_10db: float


class OrbitResponse(SimulationResponse):
    """First-order circular-orbit properties for one altitude."""

    altitude_km: float
    inclination_deg: float
    period_min: float
    velocity_kms: float
    eclipse_fraction_assumed: float
