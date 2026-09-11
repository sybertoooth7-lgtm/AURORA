"""AuroraStack: orchestrates layers in priority order with fail-safe invariant.

The stack is the single execution point of the multi-planetary AI.  Each
decision cycle runs all layers, collects their proposals, passes them
through mission control's safety/authority filter, then executes only
approved actions.  If the fail-safe controller trips, the stack freezes
all layers and emits a safe-mode sequence.

Design principles
-----------------
* **Fail-safe is a system invariant:** safe mode must always be reachable
  even if all layers malfunction.
* **Human oversight is never optional** for irreversible actions at
  autonomy < 5.
* **Radiation / watchdog events** immediately escalate to safe mode --
  no layer can suppress them.
"""

from typing import List, Optional

from app.multiplanetary.layers.core import (
    Action,
    ActionType,
    Layer,
    MissionContext,
    StackDecision,
)
from app.multiplanetary.layers.mission_control import MissionControlLayer
from app.multiplanetary.layers.scientific import ScientificIntelligenceLayer
from app.multiplanetary.layers.robotics import RoboticsLayer
from app.multiplanetary.layers.navigation_layer import NavigationLayer
from app.multiplanetary.layers.resource_management import ResourceManagementLayer
from app.multiplanetary.layers.infrastructure import InfrastructureLayer
from app.multiplanetary.layers.human_assistance import HumanAssistanceLayer


class AuroraStack:
    """Orchestration layer for the full multi-planetary AI stack."""

    def __init__(
        self,
        mission_control: Optional[MissionControlLayer] = None,
        scientific: Optional[ScientificIntelligenceLayer] = None,
        robotics: Optional[RoboticsLayer] = None,
        navigation: Optional[NavigationLayer] = None,
        resources: Optional[ResourceManagementLayer] = None,
        infrastructure: Optional[InfrastructureLayer] = None,
        human_assistance: Optional[HumanAssistanceLayer] = None,
    ):
        self.mission_control = mission_control or MissionControlLayer()
        self.scientific = scientific or ScientificIntelligenceLayer()
        self.robotics = robotics or RoboticsLayer()
        self.navigation = navigation or NavigationLayer()
        self.resources = resources or ResourceManagementLayer()
        self.infrastructure = infrastructure or InfrastructureLayer()
        self.human_assistance = human_assistance or HumanAssistanceLayer()
        self._layers: List[Layer] = [
            self.human_assistance,
            self.resources,
            self.infrastructure,
            self.navigation,
            self.robotics,
            self.scientific,
            self.mission_control,
        ]
        self._safe_mode = False
        self._cycle_count = 0

    def _check_fail_safe(self, ctx: MissionContext) -> Optional[str]:
        if ctx.battery_percent < 5.0:
            return "battery critically low"
        if ctx.environment_sensor.get("radiation_event", False):
            return "radiation event detected"
        if ctx.environment_sensor.get("watchdog_reset", False):
            return "watchdog reset detected"
        if ctx.temperature_c > 70.0:
            return "temperature exceeds survival threshold"
        return None

    def _safe_mode_actions(self) -> List[Action]:
        return [
            Action(
                layer="stack",
                action_type=ActionType.COMMAND,
                target="infrastructure",
                description="SAFE MODE: suspend all ISRU operations.",
                payload={"action": "safe_mode", "isru": "off"},
                reversible=True,
                severity="critical",
            ),
            Action(
                layer="stack",
                action_type=ActionType.COMMAND,
                target="robotics",
                description="SAFE MODE: halt all rover motion.",
                payload={"action": "safe_mode", "motion": "stop"},
                reversible=True,
                severity="critical",
            ),
            Action(
                layer="stack",
                action_type=ActionType.COMMAND,
                target="infrastructure",
                description="SAFE MODE: enter minimal power mode (only comms and thermal).",
                payload={"action": "safe_mode", "power": "minimal"},
                reversible=True,
                severity="critical",
            ),
            Action(
                layer="stack",
                action_type=ActionType.ALERT,
                target="human",
                description=(
                    "SAFE MODE ACTIVE. All non-critical operations suspended. "
                    "Awaiting ground command."
                ),
                severity="critical",
            ),
        ]

    def step(self, ctx: MissionContext) -> StackDecision:
        self._cycle_count += 1
        fail_safe_trip = self._check_fail_safe(ctx)

        if fail_safe_trip or self._safe_mode:
            self._safe_mode = True
            safe_actions = self._safe_mode_actions()
            return StackDecision(
                timestamp=ctx.timestamp,
                approved_actions=safe_actions,
                safe_mode_active=True,
                warnings=[fail_safe_trip or "safe mode active"],
            )

        proposed: List[Action] = []
        for layer in self._layers:
            try:
                actions = layer.evaluate(ctx)
                proposed.extend(actions)
            except Exception as exc:
                proposed.append(Action(
                    layer="stack",
                    action_type=ActionType.ALERT,
                    target=layer.name,
                    description=f"Layer {layer.name} exception: {exc}",
                    severity="critical",
                ))

        approved, pending, rejected = self.mission_control.filter_actions(proposed, ctx)

        if any(a.severity == "critical" for a in rejected):
            self._safe_mode = True
            approved = approved + self._safe_mode_actions()
            pending = []
            rejected = []

        return StackDecision(
            timestamp=ctx.timestamp,
            approved_actions=approved,
            pending_authorization=pending,
            rejected_actions=rejected,
            safe_mode_active=self._safe_mode,
        )

    def authorize_action(self, action_dict: dict) -> Action:
        """Called by a human operator to approve a pending action."""
        return Action(
            layer="human",
            action_type=ActionType.COMMAND,
            target=action_dict.get("target", ""),
            description=f"HUMAN-AUTHORIZED: {action_dict.get('description', '')}",
            payload=action_dict.get("payload", {}),
            reversible=action_dict.get("reversible", True),
        )

    @property
    def is_safe_mode(self) -> bool:
        return self._safe_mode

    def reset_safe_mode(self) -> None:
        self._safe_mode = False