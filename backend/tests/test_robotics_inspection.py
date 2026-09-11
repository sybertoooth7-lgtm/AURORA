"""Tests for robotics field inspection (AURORA-2).

Covers the NDVI damage pipeline (pure) and the flight telemetry store /
health summariser -- both DB-free so they run anywhere.
"""

from datetime import UTC, datetime

from app.ai.base import Provenance
from app.ai.registry import get_pipeline
from app.ai.robotics_inspection import RoboticsInspectionPipeline
from app.models.analysis import AnalysisType
from app.robotics.flight import FlightStore, compute_flight_health
from app.robotics.telemetry import TelemetryEntry
from app.satellite.providers import SatelliteObservation


def make_observation(ndvi=0.5, source="demo", image_id="demo-rob"):
    return SatelliteObservation(
        source=source,
        image_id=image_id,
        acquired_at=datetime.now(UTC),
        cloud_coverage=0.05,
        resolution_m=10.0,
        ndvi=ndvi,
        change_score=0.1,
    )


class TestRoboticsInspectionPipeline:
    def test_damage_proxy_mapping(self):
        assert 0.0 <= RoboticsInspectionPipeline.damage_proxy_from_ndvi(5.0) <= 1.0
        assert (
            RoboticsInspectionPipeline.damage_proxy_from_ndvi(0.1)
            > RoboticsInspectionPipeline.damage_proxy_from_ndvi(0.8)
        )

    def test_healthy_field_low_severity(self):
        result = RoboticsInspectionPipeline().run(make_observation(ndvi=0.8))
        assert result.severity < 0.4
        assert result.labels[0].class_ == "crop_normal"

    def test_damaged_field_high_severity(self):
        result = RoboticsInspectionPipeline().run(make_observation(ndvi=0.12))
        assert result.severity >= 0.4
        assert result.labels[0].class_ == "field_damage"

    def test_simulated_provenance_honesty(self):
        result = RoboticsInspectionPipeline().run(make_observation(ndvi=0.5, source="demo"))
        assert result.provenance == Provenance.SIMULATED
        assert result.to_dict()["simulated"] is True

    def test_registry_resolves_robotics_inspection(self):
        pipeline = get_pipeline(AnalysisType.ROBOTICS_INSPECTION)
        assert isinstance(pipeline, RoboticsInspectionPipeline)


class TestFlightHealth:
    def test_empty_log_is_no_telemetry(self):
        health = compute_flight_health([])
        assert health["status"] == "no_telemetry"
        assert health["samples"] == 0

    def test_healthy_frames_score_high(self):
        entries = [
            TelemetryEntry(timestamp=1.0, category="flight", source="flight:1", data={"battery_percent": 90.0}),
            TelemetryEntry(timestamp=2.0, category="flight", source="flight:1", data={"battery_percent": 85.0}),
        ]
        health = compute_flight_health(entries)
        assert health["status"] == "healthy"
        assert health["battery_min"] == 85.0

    def test_low_battery_pulls_score_down(self):
        entries = [
            TelemetryEntry(timestamp=1.0, category="flight", source="flight:1", data={"battery_percent": 10.0}),
        ]
        health = compute_flight_health(entries)
        # (25 - 10)/50 drops the score to 0.7 -> caution, not healthy.
        assert health["health_score"] == 0.7
        assert health["status"] == "caution"

    def test_faults_increment_count_and_lower_score(self):
        entries = [
            TelemetryEntry(timestamp=1.0, category="flight", source="flight:1", data={"battery_percent": 90.0}),
            TelemetryEntry(timestamp=2.0, category="flight", source="flight:1", data={"faults": ["motor_temp"]}, level="error"),
        ]
        health = compute_flight_health(entries)
        assert health["fault_count"] == 1
        assert health["health_score"] < 1.0


class TestFlightStore:
    def test_ingest_and_summary(self):
        store = FlightStore()
        store.ingest("flight-1", {"battery_percent": 90.0})
        store.ingest("flight-1", {"battery_percent": 20.0, "faults": ["gps"]})
        summary = store.summary("flight-1")
        assert summary is not None
        assert summary["flight_id"] == "flight-1"
        assert summary["telemetry_count"] == 2
        assert summary["flight_health"]["fault_count"] == 1

    def test_unknown_flight_returns_none(self):
        assert FlightStore().health("nope") is None
        assert FlightStore().summary("nope") is None
