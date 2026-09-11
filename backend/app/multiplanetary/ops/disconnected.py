"""Disconnected operations manager.

When the spacecraft is out of ground contact (Mars blackout, orbital
occultation, deep-space isolation), this manager governs what autonomous
actions are permitted based on the autonomy level and preloaded
mission playbooks.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class MissionPlaybook:
    name: str
    triggers: dict[str, float]
    actions: list[dict[str, Any]]
    priority: int = 0


@dataclass
class DisconnectedState:
    elapsed_s: float = 0.0
    max_autonomous_s: float = 3600.0
    playbook_active: str | None = None
    actions_executed: int = 0
    fallback_safe: bool = False


class DisconnectedOpsManager:
    def __init__(self, autonomy_level: int = 3, max_autonomous_s: float = 3600.0):
        self._autonomy_level = autonomy_level
        self._max_autonomous_s = max_autonomous_s
        self._playbooks: list[MissionPlaybook] = []
        self._current_state = DisconnectedState(max_autonomous_s=max_autonomous_s)
        self._actions_log: list[dict[str, Any]] = []

    def register_playbook(self, playbook: MissionPlaybook) -> None:
        self._playbooks.append(playbook)
        self._playbooks.sort(key=lambda p: -p.priority)

    def enter_disconnected(self, elapsed_s: float = 0.0) -> None:
        self._current_state = DisconnectedState(
            elapsed_s=elapsed_s,
            max_autonomous_s=self._max_autonomous_s,
            fallback_safe=False,
        )

    def tick(self, elapsed_s: float, battery_percent: float = 100.0) -> DisconnectedState:
        self._current_state.elapsed_s = elapsed_s
        if elapsed_s > self._max_autonomous_s or battery_percent < 10.0:
            self._current_state.fallback_safe = True
            self._current_state.playbook_active = "safe_mode"
            return self._current_state
        for pb in self._playbooks:
            if all(battery_percent > v for k, v in pb.triggers.items() if k == "min_battery"):
                self._current_state.playbook_active = pb.name
                break
        return self._current_state

    def execute_playbook_action(self) -> dict[str, Any] | None:
        if not self._current_state.playbook_active:
            return None
        if self._current_state.fallback_safe:
            return {"action": "enter_safe_mode", "reason": "disconnected_ops_timeout"}
        action = {
            "playbook": self._current_state.playbook_active,
            "step": self._current_state.actions_executed,
        }
        self._current_state.actions_executed += 1
        self._actions_log.append(action)
        return action

    @property
    def state(self) -> DisconnectedState:
        return self._current_state

    @property
    def actions_log(self) -> list[dict[str, Any]]:
        return list(self._actions_log)
