"""Schemas for the Space Resource Program (ISRU) endpoints."""

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.simulation import SimulationResponse

ProcessName = Literal["water_ice", "oxygen_regolith", "metals", "construction_material", "generic"]
SignificanceName = Literal["primary", "secondary", "trace"]
PriorityName = Literal["low", "medium", "high"]


class TechnologyOut(BaseModel):
    id: str
    name: str
    resource_type: str
    trl: int
    readiness: str
    mass_kg: float
    power_w: float
    production_kg_per_day: float
    production_efficiency: float
    risk_overall: float
    total_timeline_years: float
    target_body: str
    terrestrial_heritage: str


class TechnologyListResponse(SimulationResponse):
    count: int
    technologies: list[TechnologyOut]


class TechnologyDetailResponse(TechnologyOut, SimulationResponse):
    description: str
    hardware: list[str]
    dependency_ids: list[str]
    dependency_chain: list[str]
    risk: dict[str, float]
    timeline_years: dict[str, float]


class EconomicsResponse(SimulationResponse):
    resource_type: str
    mass_kg: float
    destination: str
    earth_launch_cost: float
    in_situ_cost: float
    savings: float
    savings_percent: float
    profile: dict[str, float]


class ExtractionRequest(BaseModel):
    """Run one extraction process for a window of operating time."""

    process: ProcessName = "water_ice"
    hours: float = Field(default=24.0, gt=0.0, le=8760.0)
    feedstock_kg: float = Field(default=1000.0, ge=0.0, le=1e7)
    power_w: float | None = Field(
        default=None, gt=0.0, le=1e6, description="Overrides the process default draw."
    )
    efficiency: float | None = Field(
        default=None, gt=0.0, le=1.0, description="Overrides the process default yield."
    )


class ExtractionResponse(SimulationResponse):
    process: ProcessName
    resource_type: str
    hours: float
    feedstock_kg: float
    mass_produced_kg: float
    mass_waste_kg: float
    energy_used_wh: float
    yield_fraction: float
    specific_energy_kwh_per_kg: float | None = Field(
        default=None,
        description="Energy per kilogram produced; null when the run produced nothing.",
    )
    status: str


class SiteOccurrenceIn(BaseModel):
    resource_type: str = Field(min_length=1, max_length=40)
    significance: SignificanceName = "secondary"
    estimated_mass_kg: float = Field(gt=0.0, le=1e12)
    concentration_fraction: float = Field(default=0.01, ge=0.0, le=1.0)
    depth_m: float = Field(default=0.5, ge=0.0, le=100.0)
    extraction_method: str = Field(default="", max_length=60)


class SiteIn(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    name: str = Field(default="", max_length=80)
    body: str = Field(min_length=1, max_length=30)
    coordinates: dict[str, float] = Field(default_factory=dict)
    resources: list[SiteOccurrenceIn] = Field(default_factory=list, max_length=20)
    terrain_difficulty: float = Field(default=0.5, ge=0.0, le=1.0)
    solar_power_availability: float = Field(default=0.7, ge=0.0, le=1.0)
    access_window_hours: float = Field(default=0.0, ge=0.0, le=8760.0)
    priority: PriorityName = "medium"


class ProspectingRequest(BaseModel):
    """Candidate sites to rank. Nothing is stored."""

    sites: list[SiteIn] = Field(min_length=1, max_length=100)
    body: str | None = Field(default=None, max_length=30, description="Restrict the ranking to one body.")


class OccurrenceViability(BaseModel):
    resource_type: str
    significance: str
    estimated_mass_kg: float
    viability: float


class ProspectPlan(BaseModel):
    id: str
    name: str
    body: str
    value_score: float
    total_mass_kg: float
    primary_resources: list[str]
    viability: list[OccurrenceViability]


class ProspectingResponse(SimulationResponse):
    ranked: list[ProspectPlan]
    summary: dict


class RoadmapPhase(BaseModel):
    phase: str
    phase_number: int
    milestone_count: int
    critical_milestones: int
    total_cost_usd: float
    duration_years: float
    start_year: float
    end_year: float


class RoadmapResponse(SimulationResponse):
    total_milestones: int
    total_cost_usd: float
    total_duration_years: float
    critical_path_milestones: int
    phases: list[RoadmapPhase]
    milestones: list[dict]
