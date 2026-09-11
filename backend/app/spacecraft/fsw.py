"""Flight software (FSW) for CubeSat.

Provides: task scheduling, fault detection/isolation/recovery (FDIR),
command execution, and telemetry collection.  The FSW is the central
orchestrator that ties all subsystems together.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any


class FSWMode(Enum):
    BOOT = "boot"
    NOMINAL = "nominal"
    SAFE = "safe"
    ECLIPSE = "eclipse"
    MAINTENANCE = "maintenance"
    EMERGENCY = "emergency"


class FaultSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class FaultEvent:
    timestamp: float
    subsystem: str
    severity: FaultSeverity
    message: str
    auto_recovered: bool = False


@dataclass
class TelemetryPacket:
    timestamp: float
    subsystem: str
    data: dict[str, Any]


class TaskScheduler:
    """Simple priority-based task scheduler.

    Tasks are callables with a priority and interval.  Higher priority
    tasks execute first.  Tasks can be one-shot or periodic.
    """

    @dataclass
    class Task:
        name: str
        callback: Callable
        priority: int = 0
        interval_s: float = 0.0
        one_shot: bool = False
        enabled: bool = True
        last_run: float = 0.0

    def __init__(self):
        self._tasks: list[TaskScheduler.Task] = []

    def schedule(
        self, name: str, callback: Callable, priority: int = 0,
        interval_s: float = 1.0, one_shot: bool = False,
    ) -> None:
        self._tasks.append(self.Task(
            name=name, callback=callback, priority=priority,
            interval_s=interval_s, one_shot=one_shot,
        ))

    def unschedule(self, name: str) -> None:
        self._tasks = [t for t in self._tasks if t.name != name]

    def tick(self, current_time: float) -> list[str]:
        executed: list[str] = []
        for task in sorted(self._tasks, key=lambda t: -t.priority):
            if not task.enabled:
                continue
            if task.one_shot and task.last_run > 0:
                continue
            if current_time - task.last_run >= task.interval_s:
                task.callback()
                task.last_run = current_time
                executed.append(task.name)
                if task.one_shot:
                    task.enabled = False
        return executed

    @property
    def task_count(self) -> int:
        return len([t for t in self._tasks if t.enabled])


class FaultManager:
    """Fault Detection, Isolation, and Recovery (FDIR).

    Monitors subsystem health and triggers safe mode on critical faults.
    """

    def __init__(self, max_history: int = 200):
        self._history: list[FaultEvent] = []
        self._max_history = max_history
        self._fault_counts: dict[str, int] = {}
        self._recovery_callbacks: dict[str, Callable] = {}

    def register_recovery(self, subsystem: str, callback: Callable) -> None:
        self._recovery_callbacks[subsystem] = callback

    def report_fault(
        self, timestamp: float, subsystem: str, severity: FaultSeverity,
        message: str, auto_recover: bool = True,
    ) -> FaultEvent:
        event = FaultEvent(
            timestamp=timestamp,
            subsystem=subsystem,
            severity=severity,
            message=message,
        )
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
        self._fault_counts[subsystem] = self._fault_counts.get(subsystem, 0) + 1
        if auto_recover and subsystem in self._recovery_callbacks:
            self._recovery_callbacks[subsystem]()
            event.auto_recovered = True
        return event

    @property
    def critical_count(self) -> int:
        return sum(1 for e in self._history if e.severity == FaultSeverity.CRITICAL)

    def recent(self, n: int = 10) -> list[FaultEvent]:
        return self._history[-n:]

    def reset(self) -> None:
        self._history.clear()
        self._fault_counts.clear()


class FlightSoftware:
    """Central FSW orchestrator for the CubeSat.

    Ties together the task scheduler, fault manager, and telemetry
    collection.  Subclasses or users attach subsystem tick functions
    via the scheduler.
    """

    def __init__(self):
        self.mode = FSWMode.BOOT
        self.scheduler = TaskScheduler()
        self.fault_manager = FaultManager()
        self._telemetry_buffer: list[TelemetryPacket] = []
        self._boot_time: float | None = None

    def boot(self, timestamp: float) -> None:
        self._boot_time = timestamp
        self.mode = FSWMode.NOMINAL

    def tick(self, current_time: float) -> dict[str, Any]:
        executed = self.scheduler.tick(current_time)
        critical = self.fault_manager.critical_count
        if critical > 0 and self.mode != FSWMode.EMERGENCY:
            self.mode = FSWMode.EMERGENCY
        elif self.mode == FSWMode.BOOT and self._boot_time:
            if current_time - self._boot_time > 10.0:
                self.mode = FSWMode.NOMINAL
        return {
            "mode": self.mode.value,
            "tasks_executed": executed,
            "task_count": self.scheduler.task_count,
            "faults": self.fault_manager.critical_count,
        }

    def collect_telemetry(self, subsystem: str, data: dict[str, Any], timestamp: float) -> None:
        pkt = TelemetryPacket(timestamp=timestamp, subsystem=subsystem, data=data)
        self._telemetry_buffer.append(pkt)
        if len(self._telemetry_buffer) > 500:
            self._telemetry_buffer = self._telemetry_buffer[-500:]

    def drain_telemetry(self) -> list[TelemetryPacket]:
        out = list(self._telemetry_buffer)
        self._telemetry_buffer.clear()
        return out

    def enter_safe_mode(self) -> None:
        self.mode = FSWMode.SAFE
        for task in self.scheduler._tasks:
            task.enabled = False
