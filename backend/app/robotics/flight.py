"""Flight telemetry store and health summariser for robotics inspections.

Earth-revenue MVP (AURORA-2): drones / ground robots doing field surveys
publish MQTT-style telemetry frames, and the platform ingests them through
``POST /robotics/flights/{flight_id}/telemetry``.

Two store implementations share one interface:

* ``FlightStore`` -- thread-safe, per-process, in-memory. Used by demo mode,
  where the whole platform is one process and data is ephemeral.
* ``RedisFlightStore`` -- the deployment path. Frames live in a bounded Redis
  list per flight, so with several API workers or replicas a telemetry POST
  handled by one process is visible to a fleet read served by any other.
  Keys expire after ``ROBOTICS_FLIGHT_TTL_SECONDS`` so the flight index stays
  bounded on a long-running deployment.

``flight_store`` is selected from settings at import time, so routes keep
using one object without knowing which backend is active.
"""

import json
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.config import get_settings
from app.robotics.telemetry import TelemetryEntry, TelemetryLogger


def _frame_timestamp(raw_ts: Any) -> float | None:
    """Arrival epoch for a frame-supplied timestamp, or None if unparsable."""
    if isinstance(raw_ts, datetime):
        return raw_ts.timestamp()
    if raw_ts:
        try:
            return datetime.fromisoformat(str(raw_ts)).timestamp()
        except ValueError:
            return None
    return None


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
        timestamp = _frame_timestamp(frame.get("timestamp"))
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

    def list_flights(self) -> list[dict[str, Any]]:
        with self._lock:
            ids = list(self._flights.keys())
        # summary() returns None only for unknown ids; these are the ids we
        # just snapshotted, so drop Nones to keep the type honest.
        return [s for s in (self.summary(fid) for fid in ids) if s is not None]

    def get_telemetry(self, flight_id: str, limit: int = 50) -> list[dict[str, Any]]:
        flight = self.get(flight_id)
        if flight is None:
            return []
        entries = flight.logger.recent("flight", n=limit)
        # timestamp is the numeric arrival epoch; a frame-supplied ISO string
        # in the payload must not shadow it, so it is applied last.
        return [{**e.data, "level": e.level, "timestamp": e.timestamp} for e in entries]

    def clear(self) -> None:
        with self._lock:
            self._flights.clear()


@dataclass
class FlightView:
    """Read-only snapshot of one flight from the shared store."""

    flight_id: str
    started_at: datetime
    entries: list[TelemetryEntry]


FLIGHT_INDEX_KEY = "flights:index"
FRAME_CATEGORY = "flight"


def _frames_key(flight_id: str) -> str:
    return f"flight:{flight_id}:frames"


class RedisFlightStore:
    """Flight store shared through Redis across every API process.

    The index is a sorted set scored by start time (so listing stays cheap and
    old flights can be trimmed by score); frames are a Redis list per flight
    with an atomic push + trim, which keeps concurrent ingests from different
    workers from losing each other's frames.
    """

    def __init__(self, redis=None) -> None:
        self._redis = redis

    @property
    def redis(self):
        if self._redis is None:
            from app.queue import get_redis

            self._redis = get_redis()
        return self._redis

    def _retention(self) -> int:
        return max(1, get_settings().ROBOTICS_FLIGHT_RETENTION_FRAMES)

    def _ttl(self) -> int:
        return max(60, get_settings().ROBOTICS_FLIGHT_TTL_SECONDS)

    def _claim(self, flight_id: str) -> None:
        now = time.time()
        # nx keeps the original start time when a second worker ingests into
        # a flight another process already started.
        self.redis.zadd(FLIGHT_INDEX_KEY, {flight_id: now}, nx=True)
        self.redis.zremrangebyscore(FLIGHT_INDEX_KEY, 0, now - self._ttl())

    def _started_at(self, flight_id: str) -> datetime | None:
        score = self.redis.zscore(FLIGHT_INDEX_KEY, flight_id)
        if score is None:
            return None
        started = float(score)
        if started < time.time() - self._ttl():
            return None
        return datetime.fromtimestamp(started, UTC)

    def _entries(self, flight_id: str, limit: int | None = None) -> list[TelemetryEntry]:
        key = _frames_key(flight_id)
        raw = (
            self.redis.lrange(key, -limit, -1)
            if limit
            else self.redis.lrange(key, 0, -1)
        )
        entries: list[TelemetryEntry] = []
        for item in raw:
            try:
                payload = json.loads(item.decode() if isinstance(item, bytes) else item)
            except (TypeError, ValueError):
                continue
            if not isinstance(payload, dict):
                continue
            data = payload.get("data")
            entries.append(
                TelemetryEntry(
                    timestamp=float(payload.get("timestamp") or 0.0),
                    category=FRAME_CATEGORY,
                    source=f"flight:{flight_id}",
                    data=data if isinstance(data, dict) else {},
                    level=str(payload.get("level") or "info"),
                )
            )
        return entries

    def start(self, flight_id: str) -> FlightView | None:
        self._claim(flight_id)
        return self.get(flight_id)

    def ingest(
        self,
        flight_id: str,
        frame: dict[str, Any],
        *,
        source: str = "mqtt",
    ) -> TelemetryEntry:
        """Append one frame; safe to call concurrently from multiple workers."""
        self._claim(flight_id)
        level = "error" if frame.get("faults") else "info"
        timestamp = _frame_timestamp(frame.get("timestamp")) or time.time()
        payload = json.dumps(
            {"level": level, "timestamp": timestamp, "data": frame},
            default=str,
        )
        key = _frames_key(flight_id)
        self.redis.rpush(key, payload)
        self.redis.ltrim(key, -self._retention(), -1)
        self.redis.expire(key, self._ttl())
        return TelemetryEntry(
            timestamp=timestamp,
            category=FRAME_CATEGORY,
            source=f"flight:{flight_id}",
            data=frame,
            level=level,
        )

    def get(self, flight_id: str) -> FlightView | None:
        started_at = self._started_at(flight_id)
        if started_at is None:
            return None
        return FlightView(flight_id, started_at, self._entries(flight_id))

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

    def list_flights(self) -> list[dict[str, Any]]:
        self.redis.zremrangebyscore(
            FLIGHT_INDEX_KEY, 0, time.time() - self._ttl()
        )
        result = []
        for member in self.redis.zrange(FLIGHT_INDEX_KEY, 0, -1):
            flight_id = member.decode() if isinstance(member, bytes) else str(member)
            summary = self.summary(flight_id)
            if summary is not None:
                result.append(summary)
        return result

    def get_telemetry(self, flight_id: str, limit: int = 50) -> list[dict[str, Any]]:
        if self._started_at(flight_id) is None:
            return []
        return [
            {**entry.data, "level": entry.level, "timestamp": entry.timestamp}
            for entry in self._entries(flight_id, limit)
        ]

    def clear(self) -> None:
        keys = self.redis.keys("flight:*:frames")
        if keys:
            self.redis.delete(*keys)
        self.redis.delete(FLIGHT_INDEX_KEY)


def get_flight_store() -> FlightStore | RedisFlightStore:
    """In-memory for the single-process demo, shared Redis everywhere else."""
    if get_settings().ENABLE_DEMO_MODE:
        return FlightStore()
    return RedisFlightStore()


flight_store = get_flight_store()
