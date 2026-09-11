"""Navigation Layer: terrain-aware path planning and obstacle avoidance.

Wraps the lower-level navigation primitives (TerrainNavigator, A* path
planning, reactive avoidance) into a layer that proposes navigation
commands to the stack.  The layer itself never drives anything -- it
emits ``COMMAND`` actions that mission control vets before any actor
executes them.
"""


from app.multiplanetary.layers.core import Action, ActionType, Layer, MissionContext
from app.multiplanetary.navigation import Path, TerrainNavigator, Waypoint


class NavigationLayer(Layer):
    name = "navigation"

    def __init__(self, navigator: TerrainNavigator | None = None):
        super().__init__()
        self._navigator = navigator
        self._goal: Waypoint | None = None
        self._path: Path | None = None
        self._last_confidence = 1.0

    def set_goal(self, goal: Waypoint) -> None:
        self._goal = goal
        self._path = None

    def _plan(self, current: Waypoint) -> Path | None:
        if self._navigator is None:
            return None
        if self._goal is None:
            return None
        self._path = self._navigator.plan_path(current, self._goal)
        return self._path

    def evaluate(self, ctx: MissionContext) -> list[Action]:
        actions: list[Action] = []
        current = None
        pos = ctx.navigation.get("position")
        if isinstance(pos, dict):
            current = Waypoint(x=pos.get("x", 0.0), y=pos.get("y", 0.0))
        elif isinstance(pos, Waypoint):
            current = pos

        if self._goal is None or current is None:
            return actions

        if self._path is None:
            path = self._plan(current)
            if path is None:
                actions.append(Action(
                    layer=self.name,
                    action_type=ActionType.ALERT,
                    target="context",
                    description="No feasible path to goal; requesting replan.",
                    severity="warning",
                ))
                return actions
            self._last_confidence = 1.0 - min(0.5, path.cost / 100.0)
            ctx.navigation["confidence"] = self._last_confidence
            actions.append(Action(
                layer=self.name,
                action_type=ActionType.PLAN,
                target="rover-1",
                description=(
                    f"Plan {len(path.waypoints)} waypoints to goal "
                    f"(cost {path.cost:.1f})."
                ),
                payload={"path_length": path.length(), "cost": path.cost},
                reversible=True,
            ))

        next_wp = self._next_waypoint(current)
        if next_wp is not None:
            actions.append(Action(
                layer=self.name,
                action_type=ActionType.COMMAND,
                target="rover-1",
                description=(
                    f"Proceed toward waypoint ({next_wp.x:.1f}, {next_wp.y:.1f})."
                ),
                payload={"waypoint": {"x": next_wp.x, "y": next_wp.y}},
                reversible=True,
            ))
        return actions

    def _next_waypoint(self, current: Waypoint) -> Waypoint | None:
        if self._path is None or not self._path.waypoints:
            return None
        for wp in self._path.waypoints:
            if wp.distance_to(current) > 0.5:
                return wp
        return self._path.waypoints[-1] if self._path.waypoints else None

    def set_navigator(self, navigator: TerrainNavigator) -> None:
        self._navigator = navigator
