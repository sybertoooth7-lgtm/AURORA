"""Behavior trees and autonomous control for multi-planetary missions.

Defines autonomy levels 1-5 (from full teleoperation to fully
autonomous) and a simple behavior-tree executor that can run
offline for testing.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class AutonomyLevel(Enum):
    LEVEL_1_TELEOP = 1
    LEVEL_2_ASSISTED = 2
    LEVEL_3_SEMI_AUTONOMOUS = 3
    LEVEL_4_AUTONOMOUS = 4
    LEVEL_5_FULLY_AUTONOMOUS = 5


class NodeStatus(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    RUNNING = "running"


@dataclass
class BehaviorNode(ABC):
    name: str = "node"

    @abstractmethod
    def tick(self, context: Dict[str, Any]) -> NodeStatus:
        pass

    def reset(self) -> None:
        pass


class ConditionNode(BehaviorNode):
    def __init__(self, name: str, check: Callable[[Dict[str, Any]], bool]):
        super().__init__(name=name)
        self._check = check

    def tick(self, context: Dict[str, Any]) -> NodeStatus:
        return NodeStatus.SUCCESS if self._check(context) else NodeStatus.FAILURE


class ActionNode(BehaviorNode):
    def __init__(self, name: str, action: Callable[[Dict[str, Any]], NodeStatus]):
        super().__init__(name=name)
        self._action = action

    def tick(self, context: Dict[str, Any]) -> NodeStatus:
        return self._action(context)


class SequenceNode(BehaviorNode):
    def __init__(self, name: str, children: List[BehaviorNode]):
        super().__init__(name=name)
        self._children = children
        self._current = 0

    def tick(self, context: Dict[str, Any]) -> NodeStatus:
        while self._current < len(self._children):
            status = self._children[self._current].tick(context)
            if status == NodeStatus.RUNNING:
                return NodeStatus.RUNNING
            if status == NodeStatus.FAILURE:
                self._current = 0
                return NodeStatus.FAILURE
            self._current += 1
        self._current = 0
        return NodeStatus.SUCCESS

    def reset(self) -> None:
        self._current = 0
        for child in self._children:
            child.reset()


class SelectorNode(BehaviorNode):
    def __init__(self, name: str, children: List[BehaviorNode]):
        super().__init__(name=name)
        self._children = children
        self._current = 0

    def tick(self, context: Dict[str, Any]) -> NodeStatus:
        while self._current < len(self._children):
            status = self._children[self._current].tick(context)
            if status == NodeStatus.RUNNING:
                return NodeStatus.RUNNING
            if status == NodeStatus.SUCCESS:
                self._current = 0
                return NodeStatus.SUCCESS
            self._current += 1
        self._current = 0
        return NodeStatus.FAILURE

    def reset(self) -> None:
        self._current = 0
        for child in self._children:
            child.reset()


@dataclass
class BehaviorTree:
    root: BehaviorNode
    name: str = "main_tree"
    tick_count: int = 0

    def tick(self, context: Dict[str, Any]) -> NodeStatus:
        self.tick_count += 1
        return self.root.tick(context)

    def reset(self) -> None:
        self.root.reset()
        self.tick_count = 0


class AutonomousController:
    """Top-level autonomous controller.

    Manages autonomy level, executes behavior tree, and produces
    velocity commands.  The behavior tree can be swapped based on
    mission phase and autonomy level.
    """

    def __init__(self, autonomy_level: AutonomyLevel = AutonomyLevel.LEVEL_3_SEMI_AUTONOMOUS):
        self.autonomy_level = autonomy_level
        self._trees: Dict[str, BehaviorTree] = {}
        self._active_tree: Optional[BehaviorTree] = None
        self._command_log: List[Dict[str, Any]] = []

    def register_tree(self, name: str, tree: BehaviorTree) -> None:
        self._trees[name] = tree

    def select_tree(self, name: str) -> None:
        self._active_tree = self._trees.get(name)

    def tick(self, context: Dict[str, Any]) -> Dict[str, Any]:
        if self._active_tree is None:
            return {"status": "no_tree", "command": {"linear": 0, "angular": 0}}
        context["autonomy_level"] = self.autonomy_level.value
        status = self._active_tree.tick(context)
        command = context.get("command", {"linear": 0, "angular": 0})
        entry = {"tick": self._active_tree.tick_count, "status": status.value, "command": command}
        self._command_log.append(entry)
        if len(self._command_log) > 200:
            self._command_log = self._command_log[-200:]
        return entry

    def set_autonomy_level(self, level: AutonomyLevel) -> None:
        self.autonomy_level = level

    @property
    def command_log(self) -> List[Dict[str, Any]]:
        return list(self._command_log)

    def build_default_rover_tree(self) -> BehaviorTree:
        has_obstacle = ConditionNode("has_obstacle", lambda ctx: ctx.get("obstacle_count", 0) > 0)
        battery_ok = ConditionNode("battery_ok", lambda ctx: ctx.get("battery_percent", 100) > 20)
        drive = ActionNode("drive_forward", lambda ctx: ctx.update({"command": {"linear": 0.3, "angular": 0}}) or NodeStatus.SUCCESS)
        avoid = ActionNode("avoid_obstacle", lambda ctx: ctx.update({"command": {"linear": 0.1, "angular": 0.5}}) or NodeStatus.SUCCESS)
        stop = ActionNode("stop", lambda ctx: ctx.update({"command": {"linear": 0, "angular": 0}}) or NodeStatus.SUCCESS)

        drive_branch = SequenceNode("drive_branch", [battery_ok, drive])
        avoid_branch = SequenceNode("avoid_branch", [has_obstacle, avoid])
        tree = BehaviorTree(
            root=SelectorNode("rover_main", [avoid_branch, drive_branch, stop]),
            name="default_rover",
        )
        self.register_tree("default_rover", tree)
        self.select_tree("default_rover")
        return tree