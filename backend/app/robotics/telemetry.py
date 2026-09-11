"""Structured telemetry and monitoring for robotics.

Logs every snapshot, sensor reading, and actuator command in a
searchable format.  Works identically in simulation and on real
hardware (same JSON lines, same fields).
"""

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TelemetryEntry:
    timestamp: float
    category: str
    source: str
    data: Dict[str, Any]
    level: str = "info"

    def to_json(self) -> str:
        return json.dumps({
            "ts": self.timestamp,
            "cat": self.category,
            "src": self.source,
            "lvl": self.level,
            **self.data,
        })


class TelemetryLogger:
    """Append-only telemetry log.

    Stores entries in memory (simulation) or can be extended to
    write to ROS 2 topics, MQTT, or a file.
    """

    def __init__(self, buffer_size: int = 10000):
        self._buffer: List[TelemetryEntry] = []
        self._buffer_size = buffer_size
        self._counters: Dict[str, int] = {}

    def log(self, category: str, source: str, data: Dict[str, Any],
            level: str = "info", timestamp: Optional[float] = None) -> TelemetryEntry:
        entry = TelemetryEntry(
            timestamp=timestamp or time.time(),
            category=category,
            source=source,
            data=data,
            level=level,
        )
        self._buffer.append(entry)
        if len(self._buffer) > self._buffer_size:
            self._buffer = self._buffer[-self._buffer_size:]
        key = f"{category}:{source}"
        self._counters[key] = self._counters.get(key, 0) + 1
        return entry

    def log_sensor(self, sensor_name: str, reading: Dict[str, Any]) -> TelemetryEntry:
        return self.log("sensor", sensor_name, reading)

    def log_actuator(self, actuator_name: str, command: Dict[str, Any]) -> TelemetryEntry:
        return self.log("actuator", actuator_name, command)

    def log_navigation(self, event: str, data: Dict[str, Any]) -> TelemetryEntry:
        return self.log("navigation", event, data)

    def log_fault(self, component: str, message: str) -> TelemetryEntry:
        return self.log("fault", component, {"message": message}, level="error")

    def recent(self, category: Optional[str] = None, n: int = 50) -> List[TelemetryEntry]:
        if category is None:
            return list(self._buffer[-n:])
        return [e for e in self._buffer if e.category == category][-n:]

    def counters(self) -> Dict[str, int]:
        return dict(self._counters)

    def clear(self) -> None:
        self._buffer.clear()
        self._counters.clear()