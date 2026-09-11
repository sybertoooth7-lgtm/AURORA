"""Fail-safe controller and safe-mode management.

The fail-safe controller is the last-resort safety net.  It monitors
health signals (battery, thermal, watchdog, command loss, navigation
confidence, radiation) and can override any other layer to force the
system into a known-safe state.  The fail-safe invariant: safe mode
must always be reachable.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any


class SafeModeLevel(Enum):
    NORMAL = "normal"
    CAUTION = "caution"
    SAFE = "safe"
    EMERGENCY = "emergency"


_LEVEL_RANK = {
    SafeModeLevel.NORMAL: 0,
    SafeModeLevel.CAUTION: 1,
    SafeModeLevel.SAFE: 2,
    SafeModeLevel.EMERGENCY: 3,
}


@dataclass
class HealthSignal:
    name: str
    value: float
    threshold_safe: float
    threshold_caution: float
    is_lower_better: bool = False

    @property
    def level(self) -> SafeModeLevel:
        if self.is_lower_better:
            if self.value < self.threshold_safe:
                return SafeModeLevel.NORMAL
            elif self.value < self.threshold_caution:
                return SafeModeLevel.CAUTION
            else:
                return SafeModeLevel.SAFE
        else:
            if self.value > self.threshold_safe:
                return SafeModeLevel.NORMAL
            elif self.value > self.threshold_caution:
                return SafeModeLevel.CAUTION
            else:
                return SafeModeLevel.SAFE


class FailSafeController:
    def __init__(
        self,
        initial_level: SafeModeLevel = SafeModeLevel.NORMAL,
        max_watchdog_before_safe: int = 3,
        command_loss_timeout_s: float = 300.0,
    ):
        self._level = initial_level
        self._signals: dict[str, HealthSignal] = {}
        self._watchdog_count: int = 0
        self._max_watchdog_before_safe = max_watchdog_before_safe
        self._command_loss_timeout_s = command_loss_timeout_s
        self._last_command_time: float = 0.0
        self._on_safe_mode: Callable | None = None

    def register_signal(self, signal: HealthSignal) -> None:
        self._signals[signal.name] = signal

    def register_safe_mode_callback(self, callback: Callable) -> None:
        self._on_safe_mode = callback

    def update_signal(self, name: str, value: float) -> None:
        if name in self._signals:
            self._signals[name].value = value

    def watchdog_reset(self) -> bool:
        self._watchdog_count += 1
        if self._watchdog_count >= self._max_watchdog_before_safe:
            self._transition(SafeModeLevel.SAFE)
            return False
        return True

    def command_received(self, timestamp: float) -> None:
        self._last_command_time = timestamp

    def check(self, current_time: float = 0.0) -> SafeModeLevel:
        worst = SafeModeLevel.NORMAL
        for signal in self._signals.values():
            if _LEVEL_RANK[signal.level] > _LEVEL_RANK[worst]:
                worst = signal.level
        if current_time - self._last_command_time > self._command_loss_timeout_s:
            if _LEVEL_RANK[worst] < _LEVEL_RANK[SafeModeLevel.SAFE]:
                worst = SafeModeLevel.SAFE
        if self._watchdog_count >= self._max_watchdog_before_safe:
            worst = SafeModeLevel.SAFE
        if worst != self._level:
            self._transition(worst)
        return self._level

    def _transition(self, new_level: SafeModeLevel) -> None:
        old = self._level
        self._level = new_level
        if new_level in (SafeModeLevel.SAFE, SafeModeLevel.EMERGENCY) and self._on_safe_mode:
            self._on_safe_mode(old.value, new_level.value)

    @property
    def level(self) -> SafeModeLevel:
        return self._level

    @property
    def is_safe_mode(self) -> bool:
        return self._level in (SafeModeLevel.SAFE, SafeModeLevel.EMERGENCY)

    def reset(self) -> None:
        self._level = SafeModeLevel.NORMAL
        self._watchdog_count = 0

    def status(self) -> dict[str, Any]:
        return {
            "level": self._level.value,
            "is_safe_mode": self.is_safe_mode,
            "watchdog_count": self._watchdog_count,
            "signals": {name: {"value": s.value, "level": s.level.value}
                       for name, s in self._signals.items()},
        }
