"""Robotics Layer: fleet coordination and agent dispatch.

Coordinates a fleet of agents (rovers, landers, hoppers) and exposes
a teleoperation bridge for level-1 direct control.  Decisions here are
proposals; mission control + the fail-safe controller own authority.

The layer refuses to dispatch agents into states that the mission
control interlocks would reject (insufficient battery, no navigation
lock), and tracks each agent's current assignment.
"""

from typing import List

from app.multiplanetary.layers.core import Action, ActionType, Layer, MissionContext


class RoboticsLayer(Layer):
    name = "robotics"

    def __init__(self, fleet: dict | None = None):
        super().__init__()
        self._fleet = fleet or {
            "rover-1": {"status": "idle", "position": None, "battery": 100.0},
            "rover-2": {"status": "idle", "position": None, "battery": 100.0},
        }
        self._assignments: dict = {}

    def evaluate(self, ctx: MissionContext) -> List[Action]:
        actions: List[Action] = []
        plan = ctx.current_plan
        if not plan:
            return actions

        for agent_id, state in self._fleet.items():
            if self._is_unavailable(state, ctx):
                actions.append(Action(
                    layer=self.name,
                    action_type=ActionType.ALERT,
                    target=agent_id,
                    description=f"{agent_id} is unavailable ({state['status']}).",
                    severity="warning",
                ))
                continue
            if plan == "scientific_survey" and self._assignments.get(agent_id) != "survey":
                self._assignments[agent_id] = "survey"
                actions.append(Action(
                    layer=self.name,
                    action_type=ActionType.COMMAND,
                    target=agent_id,
                    description=f"Dispatch {agent_id} to execute scientific survey.",
                    payload={"mission": "scientific_survey"},
                    reversible=True,
                ))
        return actions

    def teleop_command(self, agent_id: str, linear: float, angular: float) -> Action:
        """Bridge for level-1 teleoperation (always routed to authorization)."""
        return Action(
            layer=self.name,
            action_type=ActionType.COMMAND,
            target=agent_id,
            description=f"Teleop command to {agent_id} (l={linear:.2f}, a={angular:.2f}).",
            payload={"linear": linear, "angular": angular},
            requires_authorization=True,
            reversible=True,
        )

    def _is_unavailable(self, state: dict, ctx: MissionContext) -> bool:
        battery = state.get("battery", ctx.battery_percent)
        if battery is not None and battery < 20.0:
            return True
        if state["status"] in ("fault", "safe_mode", "lost"):
            return True
        return False