"""Mission operations: timeline, ground segment, telemetry downlink.

Models the mission lifecycle (launch, LEOP, commissioning, operations,
deorbit), ground station scheduling, and telemetry relay.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MissionPhase(Enum):
    PRE_LAUNCH = "pre_launch"
    LAUNCH = "launch"
    LEOP = "leop"
    COMMISSIONING = "commissioning"
    NOMINAL_OPS = "nominal_ops"
    EXTENDED_OPS = "extended_ops"
    DEORBIT = "deorbit"
    END_OF_LIFE = "end_of_life"


@dataclass
class MissionEvent:
    timestamp_s: float
    phase: MissionPhase
    description: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContactWindow:
    ground_station: str
    start_s: float
    end_s: float
    max_elevation_deg: float = 0.0
    slant_range_km: float = 0.0

    @property
    def duration_s(self) -> float:
        return max(0.0, self.end_s - self.start_s)


class MissionTimeline:
    """Mission event timeline and phase tracker."""

    def __init__(self, mission_duration_days: float = 365.0):
        self.mission_duration_days = mission_duration_days
        self.mission_duration_s = mission_duration_days * 86400.0
        self._events: list[MissionEvent] = []
        self._current_phase = MissionPhase.PRE_LAUNCH
        self._current_time_s = 0.0

    def add_event(self, timestamp_s: float, phase: MissionPhase, description: str) -> None:
        self._events.append(MissionEvent(timestamp_s=timestamp_s, phase=phase, description=description))

    def tick(self, time_s: float) -> MissionPhase:
        self._current_time_s = time_s
        for event in sorted(self._events, key=lambda e: e.timestamp_s):
            if time_s >= event.timestamp_s:
                self._current_phase = event.phase
        return self._current_phase

    @property
    def current_phase(self) -> MissionPhase:
        return self._current_phase

    @property
    def elapsed_days(self) -> float:
        return self._current_time_s / 86400.0

    @property
    def remaining_days(self) -> float:
        return max(0.0, self.mission_duration_days - self.elapsed_days)

    @property
    def completion_fraction(self) -> float:
        return min(1.0, self._current_time_s / self.mission_duration_s)

    def default_timeline(self) -> None:
        self.add_event(0.0, MissionPhase.LAUNCH, "Launch")
        self.add_event(3600.0, MissionPhase.LEOP, "Initial orbit acquisition")
        self.add_event(7 * 86400.0, MissionPhase.COMMISSIONING, "Commissioning start")
        self.add_event(30 * 86400.0, MissionPhase.NOMINAL_OPS, "Nominal operations")
        self.add_event(335 * 86400.0, MissionPhase.EXTENDED_OPS, "Extended operations")
        self.add_event(360 * 86400.0, MissionPhase.DEORBIT, "Deorbit maneuver")
        self.add_event(self.mission_duration_s, MissionPhase.END_OF_LIFE, "End of life")


class GroundSegment:
    """Ground station network and contact scheduling."""

    def __init__(self):
        self._stations: dict[str, Any] = {}
        self._contact_windows: list[ContactWindow] = []

    def add_station(self, name: str, station: Any) -> None:
        self._stations[name] = station

    def get_station(self, name: str) -> Any:
        return self._stations.get(name)

    def add_contact_window(self, window: ContactWindow) -> None:
        self._contact_windows.append(window)

    def next_contact(self, current_time_s: float) -> ContactWindow | None:
        future = [w for w in self._contact_windows if w.start_s > current_time_s]
        if not future:
            return None
        return min(future, key=lambda w: w.start_s)

    def total_contact_s(self) -> float:
        return sum(w.duration_s for w in self._contact_windows)

    def contacts_for_station(self, station_name: str) -> list[ContactWindow]:
        return [w for w in self._contact_windows if w.ground_station == station_name]


class TelemetryDownlink:
    """Telemetry queue and downlink scheduler."""

    def __init__(self, queue_capacity_packets: int = 1000):
        self._queue_capacity = queue_capacity_packets
        self._queue: list[dict[str, Any]] = []
        self._downlinked: list[dict[str, Any]] = []
        self._total_bytes = 0

    def enqueue(self, telemetry: dict[str, Any]) -> bool:
        if len(self._queue) >= self._queue_capacity:
            return False
        self._queue.append(telemetry)
        self._total_bytes += len(str(telemetry))
        return True

    def downlink_batch(self, max_bytes: int, contact_s: float, data_rate_bps: int = 9600) -> list[dict[str, Any]]:
        available_bytes = min(max_bytes, int(contact_s * data_rate_bps / 8))
        sent: list[dict[str, Any]] = []
        remaining = available_bytes
        while self._queue and remaining > 0:
            pkt = self._queue.pop(0)
            pkt_size = len(str(pkt))
            if pkt_size <= remaining:
                sent.append(pkt)
                remaining -= pkt_size
                self._downlinked.append(pkt)
        return sent

    @property
    def queue_depth(self) -> int:
        return len(self._queue)

    @property
    def total_downlinked(self) -> int:
        return len(self._downlinked)
