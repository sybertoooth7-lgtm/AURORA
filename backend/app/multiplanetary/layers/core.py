"""Shared primitives for the layered AI stack."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ActionType(Enum):
    """What kind of action a layer is proposing."""
    COMMAND = "command"                          # direct robot/spacecraft command
    PLAN = "plan"                                # multi-step plan to schedule
    ALERT = "alert"                              # advisory / warning
    REQUEST_AUTHORIZATION = "request_authorization"  # needs human oversight
    RELAY = "relay"                              # pass-through for another layer


class InvalidAction(Exception):
    """Raised when an action violates a safety interlock or is malformed."""


@dataclass
class Action:
    """A single proposal emitted by a layer in one decision cycle."""
    layer: str
    action_type: ActionType
    target: str                        # e.g. 'rover-1', 'isru-plant', 'comms'
    description: str
    payload: dict[str, Any] = field(default_factory=dict)
    requires_authorization: bool = False   # human oversight gate
    reversible: bool = True                # fail-safe invariant input
    severity: str = "info"                 # info|warning|critical
    timestamp: float = 0.0

    @property
    def is_irreversible(self) -> bool:
        return not self.reversible

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer": self.layer,
            "action_type": self.action_type.value,
            "target": self.target,
            "description": self.description,
            "payload": self.payload,
            "requires_authorization": self.requires_authorization,
            "reversible": self.reversible,
            "severity": self.severity,
            "timestamp": self.timestamp,
        }


@dataclass
class MissionContext:
    """Shared, layer-visible mission state for the current decision cycle.

    Layers read from ``ctx`` and may append advisories; they never mutate
    ``ctx`` structure directly (immutability enforced by convention plus
    the stack applying actions after the pass).
    """

    timestamp: float = 0.0
    environment: str = "earth"             # earth|orbital|lunar|mars|deep_space
    target_body: str = "earth"
    autonomy_level: int = 3                # 1..5
    one_way_delay_s: float = 0.0
    in_contact: bool = True
    battery_percent: float = 100.0
    power_available_w: float = 100.0
    power_demand_w: float = 50.0
    temperature_c: float = 25.0
    navigation: dict[str, Any] = field(default_factory=dict)
    inventory: dict[str, float] = field(default_factory=dict)   # kg / units
    infrastructure: dict[str, Any] = field(default_factory=dict)
    fleet: dict[str, Any] = field(default_factory=dict)
    environment_sensor: dict[str, Any] = field(default_factory=dict)
    science_hypotheses: list[dict[str, Any]] = field(default_factory=list)
    current_plan: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "environment": self.environment,
            "target_body": self.target_body,
            "autonomy_level": self.autonomy_level,
            "one_way_delay_s": self.one_way_delay_s,
            "in_contact": self.in_contact,
            "battery_percent": self.battery_percent,
            "power_available_w": self.power_available_w,
            "power_demand_w": self.power_demand_w,
            "temperature_c": self.temperature_c,
            "navigation": self.navigation,
            "inventory": self.inventory,
            "infrastructure": self.infrastructure,
            "fleet": self.fleet,
            "science_hypotheses": self.science_hypotheses,
            "current_plan": self.current_plan,
            "warnings": self.warnings,
        }


class Layer(ABC):
    """Base class for a stack layer.

    A layer reads the :class:`MissionContext` and proposes :class:`Action`s.
    It is pure and stateless between cycles where possible; any state it
    needs (e.g. latency counters) lives in dedicated managers owned by the
    stack.
    """

    name: str = "layer"

    def __init__(self) -> None:
        self.last_actions: list[Action] = []

    @abstractmethod
    def evaluate(self, ctx: MissionContext) -> list[Action]:
        """Examine the context and return proposed actions for this cycle."""

    def record(self, actions: list[Action]) -> None:
        self.last_actions = actions


@dataclass
class StackDecision:
    """Result of one full stack decision cycle."""
    timestamp: float
    approved_actions: list[Action] = field(default_factory=list)
    pending_authorization: list[Action] = field(default_factory=list)
    rejected_actions: list[Action] = field(default_factory=list)
    safe_mode_active: bool = False
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "approved": [a.to_dict() for a in self.approved_actions],
            "pending_authorization": [a.to_dict() for a in self.pending_authorization],
            "rejected": [a.to_dict() for a in self.rejected_actions],
            "safe_mode_active": self.safe_mode_active,
            "warnings": self.warnings,
        }
