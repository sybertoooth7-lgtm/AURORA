"""Schemas for the robotics field-inspection endpoints (AURORA-2)."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.ai import PipelineResultResponse


class FlightHealth(BaseModel):
    """Health derived from a flight's telemetry stream (0..1 score)."""

    health_score: float
    status: str
    samples: int
    fault_count: int
    battery_min: float | None = None


class FlightTelemetryFrame(BaseModel):
    """One MQTT-style telemetry frame published by a drone / ground robot."""

    battery_percent: float | None = Field(default=None, ge=0, le=100)
    gps_accuracy_m: float | None = Field(default=None, ge=0)
    motor_temp_c: float | None = None
    altitude_m: float | None = None
    heading_deg: float | None = Field(default=None, ge=0, le=360)
    faults: list[str] = Field(default_factory=list)
    sequence: int | None = Field(default=None, ge=0)
    timestamp: datetime | None = None


class TelemetryAckResponse(BaseModel):
    received: bool
    flight_id: str
    telemetry_count: int
    flight_health: FlightHealth


class FlightSummaryResponse(BaseModel):
    flight_id: str
    started_at: str
    telemetry_count: int
    flight_health: FlightHealth


class RoboticsInspectRequest(BaseModel):
    """Post-flight inspection: satellite NDVI report for a flight's area."""

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_km: float = Field(gt=0, le=500)
    use_history: bool = True
    flight_id: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=500)


class RoboticsInspectResponse(BaseModel):
    result: PipelineResultResponse
    analysis_id: int
    flight_id: str | None = None
    flight_health: FlightHealth | None = None
    vsatellite_damage_proxy: float | None = None
    combined_report: list[str] = Field(default_factory=list)
