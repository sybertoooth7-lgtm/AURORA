"""Schemas for the Mission Planning endpoints."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.simulation import SimulationResponse

TaskPriorityName = Literal["low", "normal", "high", "critical"]
SourceStatusName = Literal["healthy", "degraded", "down", "unknown"]


class TaskIn(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    name: str = Field(default="", max_length=80)
    priority: TaskPriorityName = "normal"
    earliest_start_s: float = Field(default=0.0, ge=0.0)
    latest_finish_s: float = Field(gt=0.0)
    duration_s: float = Field(gt=0.0)
    resource_requirements: dict[str, float] = Field(default_factory=dict)
    requires_contact: bool = False

    @model_validator(mode="after")
    def _fits_its_window(self) -> "TaskIn":
        if self.earliest_start_s + self.duration_s > self.latest_finish_s:
            raise ValueError(
                f"task '{self.id}': duration {self.duration_s}s cannot fit between "
                f"earliest_start_s and latest_finish_s"
            )
        return self


class ResourceBudgetIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    capacity: float = Field(ge=0.0)
    unit: str = Field(default="", max_length=20)


class ContactWindowIn(BaseModel):
    ground_station: str = Field(default="gs-0", min_length=1, max_length=60)
    start_s: float = Field(ge=0.0)
    end_s: float = Field(gt=0.0)
    max_elevation_deg: float = Field(default=0.0, ge=0.0, le=90.0)
    slant_range_km: float = Field(default=0.0, ge=0.0)

    @model_validator(mode="after")
    def _check_window(self) -> "ContactWindowIn":
        if self.end_s <= self.start_s:
            raise ValueError("contact window ends before it starts")
        return self


class ScheduleRequest(BaseModel):
    """Tasks, resource budgets and optional contact windows to place."""

    tasks: list[TaskIn] = Field(min_length=1, max_length=200)
    budgets: list[ResourceBudgetIn] = Field(default_factory=list, max_length=20)
    contact_windows: list[ContactWindowIn] = Field(default_factory=list, max_length=100)


class ScheduledTaskOut(BaseModel):
    id: str
    name: str
    priority: TaskPriorityName
    start_s: float
    end_s: float
    requires_contact: bool


class RejectedTask(BaseModel):
    id: str
    name: str
    priority: TaskPriorityName
    reason: str


class ScheduleResponse(SimulationResponse):
    scheduled: list[ScheduledTaskOut]
    conflicts: list[RejectedTask]
    window_start_s: float
    window_end_s: float


class DataSourceReadiness(BaseModel):
    name: str
    provider: str
    status: SourceStatusName
    quota_used: float
    quota_limit: float | None
    quota_fraction_used: float | None
    schedulable: bool


class DataReadinessResponse(SimulationResponse):
    overall: str
    basis: str = Field(
        description=(
            "How each status was derived, so a reader knows this is inferred from "
            "the platform's own job outcomes and not a provider health probe."
        )
    )
    sources: list[DataSourceReadiness]
    observations: dict[str, int]
