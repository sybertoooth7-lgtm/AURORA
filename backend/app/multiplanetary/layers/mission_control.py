"""Mission Control Layer: authority, autonomy budget, safety interlocks.

The highest-authority AI layer. Its job is not to do the mission but to
guard it:

* **Autonomy budget** -- how much autonomy the stack may exercise grows
  with communication delay but shrinks with risk. Derived from
  ``one_way_delay_s`` and the operations plan.
* **Safety interlocks** -- hard constraints (battery, thermal, navigation
  confidence, radiation) that veto actions regardless of anything else.
* **Oversight** -- irreversible actions and actions beyond the autonomy
  budget are funneled to ``request_authorization`` for human review.
* **Fail-safe invariant** -- safe mode must always be reachable; the
  mission control layer is the last word before fail-safe.

The rest of the stack "*proposes*", mission control "*disposes*".
"""

import math
from typing import List, Optional

from app.multiplanetary.layers.core import (
    Action,
    ActionType,
    InvalidAction,
    Layer,
    MissionContext,
)


class MissionControlLayer(Layer):
    name = "mission_control"

    def __init__(
        self,
        min_battery_percent: float = 15.0,
        max_temperature_c: float = 55.0,
        min_navigation_confidence: float = 0.3,
        max_radiation_dose_gy: float = 100.0,
    ):
        super().__init__()
        self.min_battery_percent = min_battery_percent
        self.max_temperature_c = max_temperature_c
        self.min_navigation_confidence = min_navigation_confidence
        self.max_radiation_dose_gy = max_radiation_dose_gy
        self._approved: List[str] = []
        self._rejected: List[str] = []

    def autonomy_budget(self, ctx: MissionContext) -> int:
        """Realistic autonomy level affordable this cycle.

        Lonelier (longer delay) -> more autonomy needed, but the budget
        is never bashful about risk: battery/temperature/contact degrade it.
        """
        level = min(5, max(1, int(round(ctx.one_way_delay_s / 5.0)) + 1))
        if ctx.battery_percent < 30.0:
            level = min(level, 2)
        if ctx.battery_percent < self.min_battery_percent:
            level = 1
        if ctx.temperature_c > self.max_temperature_c:
            level = 1
        if not ctx.in_contact and level < 3:
            level = 3  # disconnected handling requires at least level 3
        return level

    def _safety_check(self, action: Action, ctx: MissionContext) -> Optional[str]:
        """Returns a rejection reason if the action violates an interlock."""
        if action.target == "rover" or action.target.startswith("rover"):
            nav_conf = ctx.navigation.get("confidence", 1.0)
            if ctx.navigation.get("uncertain", False) and nav_conf < self.min_navigation_confidence:
                return "navigation confidence too low to move"
            if ctx.navigation.get("blocked", False):
                return "navigation blocked by hazard"
        if action.target in ("isru", "isru-plant", "power"):
            if ctx.power_available_w < ctx.power_demand_w * 1.2 and action.action_type == ActionType.COMMAND:
                return "insufficient power margin for command"
        if action.severity == "critical" and ctx.battery_percent < self.min_battery_percent:
            return "critical action while battery below safe floor"
        if getattr(action, "is_irreversible", False) and not action.requires_authorization:
            return "irreversible action missing authorization gate"
        return None

    def evaluate(self, ctx: MissionContext) -> List[Action]:
        actions: List[Action] = []
        budget = self.autonomy_budget(ctx)
        if ctx.autonomy_level > budget:
            actions.append(Action(
                layer=self.name,
                action_type=ActionType.ALERT,
                target="stack",
                description=(
                    f"Reducing autonomy from {ctx.autonomy_level} to {budget} "
                    f"(delay {ctx.one_way_delay_s:.0f}s, battery {ctx.battery_percent:.0f}%)."
                ),
                severity="warning",
                payload={"new_autonomy": budget},
            ))
        for warning in ctx.warnings:
            actions.append(Action(
                layer=self.name,
                action_type=ActionType.ALERT,
                target="context",
                description=warning,
                severity="warning",
            ))
        return actions

    def filter_actions(
        self,
        proposed: List[Action],
        ctx: MissionContext,
    ) -> tuple[List[Action], List[Action], List[Action]]:
        """Split proposed into approved / pending-authorization / rejected."""
        approved: List[Action] = []
        pending: List[Action] = []
        rejected: List[Action] = []
        budget = self.autonomy_budget(ctx)

        for action in proposed:
            if action.layer == self.name and action.action_type in (
                ActionType.ALERT, ActionType.REQUEST_AUTHORIZATION,
            ):
                rejected.append(action)
                continue
            reason = self._safety_check(action, ctx)
            if reason:
                rejection = Action(
                    layer=self.name,
                    action_type=ActionType.ALERT,
                    target=action.layer,
                    description=f"Rejected action from {action.layer}: {reason}",
                    severity="warning",
                )
                rejected.append(rejection)
                continue
            if action.requires_authorization or (
                not action.reversible and ctx.autonomy_level < 4
            ):
                auth = Action(
                    layer=self.name,
                    action_type=ActionType.REQUEST_AUTHORIZATION,
                    target=action.layer,
                    description=f"Requesting authorization for: {action.description}",
                    payload={"original": action.to_dict()},
                    severity="info",
                )
                pending.append(auth)
            elif ctx.autonomy_level >= budget and action.reversible:
                approved.append(action)
            else:
                pending.append(action)
        self._approved = [a.description for a in approved]
        self._rejected = [a.description for a in rejected]
        return approved, pending, rejected