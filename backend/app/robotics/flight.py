"""Flight telemetry store and health summariser for robotics inspections.

Earth-revenue MVP (AURORA-2): drones / ground robots doing field surveys
publish MQTT-style telemetry frames, and the platform ingests them through
``POST /robotics/flights/{flight_id}/telemetry``. This module keeps a small,
per-process, thread-safe store (bounded per flight) and a pure health
summariser so a consumer can see "is this robot healthy and did the flight
produce a usable inspection?" before the satellite-derived report.

The MVP store is intentionally in-memory and single-process -- the same
honest trade-off as the security events list in app.multiplanetary.ops.
Real deployments back this with Redis Streams / a telemetry database; the
route boundary and the frame schema stay identical.
"""

import threading
from datetime import UTC, datetime
from typing import Any

from app.config import get_settings
from app.robotics.telemetry import TelemetryEntry, TelemetryLogger


def compute_flight_health(entries: list[TelemetryEntry]) -> dict[str, Any]:
    """Devise one health score (0..1) + status from flight telemetry.

    Pure and deterministic: battery below ~25% and fault frames each pull
    the score down; an empty log returns ``no_telemetry`` rather than a
    false 'healthy'.
    """
    if not entries:
        return {
            "health_score": 1.0,
            "status": "no_telemetry",
            "samples": 0,
            "fault_count": 0,
            "battery_min": None,
        }

    batteries = [
        float(entry.data["battery_percent"])
        for entry in entries
        if entry.data.get("battery_percent") is not None
    ]
    battery_min = min(batteries) if batteries else None
    fault_count = sum(
        1
        for entry in entries
        if entry.level == "error" or entry.data.get("faults")
    )

    score = 1.0
    if battery_min is not None and battery_min < 25.0:
        score -= (25.0 - battery_min) / 50.0
    score -= min(0.3, fault_count * 0.1)
    score = round(min(1.0, max(0.0, score)), 4)

    status = "healthy" if score >= 0.8 else ("caution" if score >= 0.5 else "critical")
    return {
        "health_score": score,
        "status": status,
        "samples": len(entries),
        "fault_count": fault_count,
        "battery_min": round(battery_min, 2) if battery_min is not None else None,
    }


class Flight:
    """One inspection flight: its telemetry stream and metadata."""

    def __init__(self, flight_id: str, started_at: datetime | None = None):
        self.flight_id = flight_id
        self.started_at = started_at or datetime.now(UTC)
        self.logger = TelemetryLogger(buffer_size=get_settings().ROBOTICS_FLIGHT_RETENTION_FRAMES)

    @property
    def entries(self) -> list[TelemetryEntry]:
        return self.logger.recent(n=get_settings().ROBOTICS_FLIGHT_RETENTION_FRAMES)


class FlightStore:
    """Thread-safe, bounded, in-memory store of active Flights."""

    def __init__(self) -> None:
        self._flights: dict[str, Flight] = {}
        self._lock = threading.Lock()

    def start(self, flight_id: str) -> Flight:
        with self._lock:
            flight = self._flights.get(flight_id)
            if flight is None:
                flight = Flight(flight_id)
                self._flights[flight_id] = flight
            return flight

    def ingest(
        self,
        flight_id: str,
        frame: dict[str, Any],
        *,
        source: str = "mqtt",
    ) -> TelemetryEntry:
        """Record one telemetry frame against a flight (lazily starting it)."""
        flight = self.start(flight_id)
        level = "error" if frame.get("faults") else "info"
        timestamp = None
        raw_ts = frame.get("timestamp")
        if isinstance(raw_ts, datetime):
            timestamp = raw_ts.timestamp()
        elif raw_ts:
            try:
                timestamp = datetime.fromisoformat(str(raw_ts)).timestamp()
            except ValueError:
                timestamp = None
        return flight.logger.log(
            "flight",
            f"flight:{flight_id}",
            frame,
            level=level,
            timestamp=timestamp,
        )

    def get(self, flight_id: str) -> Flight | None:
        with self._lock:
            return self._flights.get(flight_id)

    def health(self, flight_id: str) -> dict[str, Any] | None:
        flight = self.get(flight_id)
        if flight is None:
            return None
        return compute_flight_health(flight.entries)

    def summary(self, flight_id: str) -> dict[str, Any] | None:
        flight = self.get(flight_id)
        if flight is None:
            return None
        health = compute_flight_health(flight.entries)
        return {
            "flight_id": flight_id,
            "started_at": flight.started_at.isoformat(),
            "telemetry_count": health["samples"],
            "flight_health": health,
        }

    def clear(self) -> None:
        with self._lock:
            self._flights.clear()


flight_store = FlightStore()
