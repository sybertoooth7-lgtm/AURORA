"""Schemas for the Space Division endpoints.

Requests carry the fleet, plan or programme inputs; responses inherit the
Stage 0 provenance envelope from ``app.schemas.simulation``.
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.simulation import SimulationResponse

SatelliteStatusName = Literal["commissioning", "operational", "degraded", "decommissioned"]


class PlaneIn(BaseModel):
    inclination_deg: float = Field(default=97.4, ge=0.0, le=180.0)
    altitude_km: float = Field(default=500.0, ge=200.0, le=2000.0)
    raan_deg: float = Field(default=0.0, ge=0.0, lt=360.0)


class SatelliteIn(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    name: str = Field(default="", max_length=80)
    plane: PlaneIn
    phase_deg: float = Field(default=0.0, ge=0.0, lt=360.0)
    status: SatelliteStatusName = "operational"
    priority: int = Field(default=0, ge=0, le=100)


class ConstellationEvaluateRequest(BaseModel):
    """A fleet to size and revisit-characterise. Nothing is stored."""

    name: str = Field(default="aurora-earth", min_length=1, max_length=60)
    satellites: list[SatelliteIn] = Field(min_length=1, max_length=200)


class PlaneSummary(BaseModel):
    inclination_deg: float
    altitude_km: float
    raan_deg: float
    period_min: float
    satellites: int


class ConstellationEvaluateResponse(SimulationResponse):
    name: str
    satellites: int
    operational: int
    planes: list[PlaneSummary]
    revisit_interval_hours: float | None = Field(
        default=None,
        description="First-order fleet-sizing estimate; null with no operational satellite.",
    )


class ContactRequestIn(BaseModel):
    satellite_id: str = Field(min_length=1, max_length=40)
    priority: int = Field(default=0, ge=0, le=100)
    ground_station: str = Field(min_length=1, max_length=60)
    start_s: float = Field(ge=0.0)
    end_s: float = Field(gt=0.0)
    max_elevation_deg: float = Field(default=0.0, ge=0.0, le=90.0)
    slant_range_km: float = Field(default=0.0, ge=0.0)

    @model_validator(mode="after")
    def _check_window(self) -> "ContactRequestIn":
        if self.end_s <= self.start_s:
            raise ValueError("contact request ends before it starts")
        return self


class GroundContactScheduleRequest(BaseModel):
    """Contact requests competing for one station's antenna."""

    requests: list[ContactRequestIn] = Field(min_length=1, max_length=200)


class GrantedContact(BaseModel):
    satellite_id: str
    ground_station: str
    start_s: float
    end_s: float
    duration_s: float
    max_elevation_deg: float
    slant_range_km: float


class ContactConflict(BaseModel):
    satellite_id: str
    ground_station: str
    start_s: float
    end_s: float
    reason: str


class GroundContactScheduleResponse(SimulationResponse):
    requested: int
    granted: list[GrantedContact]
    conflicts: list[ContactConflict]
