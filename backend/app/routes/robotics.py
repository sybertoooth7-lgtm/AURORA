"""Robotics field-inspection endpoints (AURORA-2 Earth revenue).

Two concerns:

* Telemetry bridge -- ``POST /robotics/flights/{flight_id}/telemetry``
  ingests MQTT-style frames published by drones / ground robots and returns
  the running flight-health summary.
* Post-flight report -- ``POST /robotics/inspect`` runs the robotics
  inspection pipeline over a flight's area and fuses the satellite-derived
  damage proxy with the robot's own health into a combined report.
"""


from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai.registry import UnknownPipelineError
from app.database import get_db
from app.exceptions import PipelineUnavailableError, SatelliteDataUnavailableError
from app.logging_conf import get_logger
from app.models.analysis import AnalysisType
from app.models.user import User
from app.robotics.flight import flight_store
from app.routes.ai import _fetch_observation, _persist_analysis_result
from app.routes.analysis import build_area_polygon_wkt
from app.schemas.ai import PipelineResultResponse
from app.schemas.robotics import (
    FlightHealth,
    FlightSummaryResponse,
    FlightTelemetryFrame,
    RoboticsInspectRequest,
    RoboticsInspectResponse,
    TelemetryAckResponse,
)
from app.security import get_current_user

logger = get_logger(__name__)

router = APIRouter(prefix="/robotics", tags=["Robotics Field Services"])


@router.post("/flights/{flight_id}/telemetry", response_model=TelemetryAckResponse)
def ingest_telemetry(
    flight_id: str,
    frame: FlightTelemetryFrame,
    current_user: User = Depends(get_current_user),
):
    """Ingest one telemetry frame from a drone / ground robot and return the
    updated flight-health summary. Idempotent per flight -- frames append."""
    flight_store.ingest(flight_id, frame.model_dump(exclude_none=False))
    health = flight_store.health(flight_id)
    flight = flight_store.get(flight_id)
    assert health is not None and flight is not None  # just ingested
    logger.info(
        "Flight telemetry ingested",
        extra_keys={"flight_id": flight_id, "user_id": current_user.id, "frames": len(flight.entries)},
    )
    return TelemetryAckResponse(
        received=True,
        flight_id=flight_id,
        telemetry_count=len(flight.entries),
        flight_health=FlightHealth(**health),
    )


@router.get("/flights/{flight_id}", response_model=FlightSummaryResponse)
def get_flight(
    flight_id: str,
    current_user: User = Depends(get_current_user),
):
    summary = flight_store.summary(flight_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="Flight not found")
    return summary


def _build_combined_report(damage_proxy: float, flight_health: dict) -> list:
    report = [f"Satellite field-damage proxy {damage_proxy:.2f}."]
    health = flight_health.get("health_score")
    status = flight_health.get("status")
    if health is not None:
        report.append(
            f"Robot telemetry health {health:.2f} ({status}) across "
            f"{flight_health.get('samples', 0)} frames."
        )
        if health >= 0.8 and damage_proxy >= 0.5:
            report.append(
                "Robot reports nominal operations but the satellite signal shows "
                "damage -- expected for vegetation changes invisible to airframe "
                "sensors; schedule a ground survey."
            )
    if damage_proxy >= 0.35:
        report.append("Follow-up ground survey recommended before loss quantification.")
    else:
        report.append("No significant vegetation damage indicated by the satellite signal.")
    return report


@router.post("/inspect", response_model=RoboticsInspectResponse)
def inspect_flight_area(
    request: RoboticsInspectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Post-flight inspection report for a flight's field area.

    Runs the robotics-inspection (NDVI) pipeline, fuses it with the flight's
    telemetry health when ``flight_id`` is supplied, and persists the run as
    an analysis for the dashboard / alerts.
    """
    area = build_area_polygon_wkt(
        latitude=request.latitude,
        longitude=request.longitude,
        radius_km=request.radius_km,
    )
    try:
        result, observation = _fetch_observation(
            AnalysisType.ROBOTICS_INSPECTION,
            request.latitude,
            request.longitude,
            request.radius_km,
            request.use_history,
        )
    except UnknownPipelineError as exc:
        raise PipelineUnavailableError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - provider failures map to 502
        raise SatelliteDataUnavailableError(
            f"Satellite observation unavailable for this area: {exc}"
        ) from exc

    analysis_id = _persist_analysis_result(
        db,
        current_user.id,
        AnalysisType.ROBOTICS_INSPECTION,
        {
            "polygon_wkt": area["polygon_wkt"],
            "latitude": request.latitude,
            "longitude": request.longitude,
            "radius_km": request.radius_km,
            "description": request.description,
        },
        result,
    )

    damage_proxy = result.severity
    flight_health = flight_store.health(request.flight_id) if request.flight_id else None
    combined_report: list = []
    if flight_health is not None:
        combined_report = _build_combined_report(damage_proxy, flight_health)
    else:
        combined_report.append(
            "No flight telemetry linked; robot-health fusion skipped."
            + (
                " Follow-up ground survey recommended."
                if damage_proxy >= 0.35
                else ""
            )
        )

    logger.info(
        "Robotics inspection completed",
        extra_keys={
            "flight_id": request.flight_id,
            "analysis_id": analysis_id,
            "damage_proxy": damage_proxy,
            "provenance": result.provenance.value,
        },
    )

    return RoboticsInspectResponse(
        result=PipelineResultResponse.model_validate(
            result.to_dict() | {"analysis_id": analysis_id}
        ),
        analysis_id=analysis_id,
        flight_id=request.flight_id,
        flight_health=FlightHealth(**flight_health) if flight_health else None,
        vsatellite_damage_proxy=round(damage_proxy, 4),
        combined_report=combined_report,
    )
