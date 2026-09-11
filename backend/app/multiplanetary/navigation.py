"""Terrain-aware navigation for planetary rovers.

Extends the base A* navigator with slope and roughness constraints.
Lunar and Mars rovers must avoid slopes above ~20-25 degrees and
rough terrain exceeding wheel-traversal limits.
"""

import math
from dataclasses import dataclass

from app.robotics.navigation import GridMap, Path, Waypoint


@dataclass
class SlopeConstraint:
    max_slope_deg: float = 20.0
    slope_penalty_factor: float = 2.0


@dataclass
class RoughnessConstraint:
    max_roughness: float = 0.3
    roughness_penalty_factor: float = 1.5


class TerrainGridMap(GridMap):
    """Grid map with per-cell slope and roughness."""

    def __init__(self, width: int, height: int, resolution: float = 1.0):
        super().__init__(width, height, resolution)
        self._slope: list[list[float]] = [[0.0] * width for _ in range(height)]
        self._roughness: list[list[float]] = [[0.0] * width for _ in range(height)]
        self._elevation: list[list[float]] = [[0.0] * width for _ in range(height)]

    def set_elevation(self, gx: int, gy: int, elevation: float) -> None:
        if self.in_bounds(gx, gy):
            self._elevation[gy][gx] = elevation

    def compute_slopes(self) -> None:
        for gy in range(self.height):
            for gx in range(self.width):
                if not self.in_bounds(gx, gy):
                    continue
                neighbors = []
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nx, ny = gx + dx, gy + dy
                    if self.in_bounds(nx, ny):
                        neighbors.append(self._elevation[ny][nx])
                if neighbors:
                    avg = sum(neighbors) / len(neighbors)
                    diff = abs(self._elevation[gy][gx] - avg)
                    self._slope[gy][gx] = math.degrees(math.atan2(diff, self.resolution))

    def get_slope(self, gx: int, gy: int) -> float:
        if self.in_bounds(gx, gy):
            return self._slope[gy][gx]
        return 90.0

    def get_roughness(self, gx: int, gy: int) -> float:
        if self.in_bounds(gx, gy):
            return self._roughness[gy][gx]
        return 1.0

    def set_roughness(self, gx: int, gy: int, roughness: float) -> None:
        if self.in_bounds(gx, gy):
            self._roughness[gy][gx] = roughness


def constrained_astar(
    grid: TerrainGridMap,
    start: Waypoint,
    goal: Waypoint,
    slope_constraint: SlopeConstraint | None = None,
    roughness_constraint: RoughnessConstraint | None = None,
) -> Path | None:
    """A* with slope + roughness constraints for planetary terrain."""
    sc = slope_constraint or SlopeConstraint()
    rc = roughness_constraint or RoughnessConstraint()

    sx, sy = grid.world_to_grid(start.x, start.y)
    gx, gy = grid.world_to_grid(goal.x, goal.y)

    if not grid.in_bounds(sx, sy) or not grid.in_bounds(gx, gy):
        return None

    import heapq
    open_set: list = []
    heapq.heappush(open_set, (0.0, sx, sy))
    came_from: dict[tuple[int, int], tuple[int, int] | None] = {(sx, sy): None}
    g_score = {(sx, sy): 0.0}

    def heuristic(ax, ay):
        return math.sqrt((ax - gx) ** 2 + (ay - gy) ** 2)

    while open_set:
        _, cx, cy = heapq.heappop(open_set)
        if (cx, cy) == (gx, gy):
            path_wps: list[Waypoint] = []
            cur: tuple[int, int] | None = (gx, gy)
            while cur is not None:
                wx, wy = grid.grid_to_world(cur[0], cur[1])
                path_wps.append(Waypoint(x=wx, y=wy))
                cur = came_from[cur]
            path_wps.reverse()
            return Path(waypoints=path_wps, cost=g_score[(gx, gy)])

        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]:
            nx, ny = cx + dx, cy + dy
            if not grid.is_free(nx, ny):
                continue
            slope = grid.get_slope(nx, ny)
            if slope > sc.max_slope_deg:
                continue
            roughness = grid.get_roughness(nx, ny)
            if roughness > rc.max_roughness:
                continue
            move_cost = grid.resolution * (1.414 if dx != 0 and dy != 0 else 1.0)
            move_cost *= 1.0 + sc.slope_penalty_factor * (slope / sc.max_slope_deg)
            move_cost *= 1.0 + rc.roughness_penalty_factor * roughness
            tentative = g_score[(cx, cy)] + move_cost
            if tentative < g_score.get((nx, ny), float("inf")):
                came_from[(nx, ny)] = (cx, cy)
                g_score[(nx, ny)] = tentative
                heapq.heappush(open_set, (tentative + heuristic(nx, ny), nx, ny))
    return None


class TerrainNavigator:
    def __init__(self, terrain_grid: TerrainGridMap):
        self.terrain_grid = terrain_grid
        self.slope_constraint = SlopeConstraint()
        self.roughness_constraint = RoughnessConstraint()
        self._path: Path | None = None

    def plan_path(self, start: Waypoint, goal: Waypoint) -> Path | None:
        self.terrain_grid.compute_slopes()
        self._path = constrained_astar(
            self.terrain_grid, start, goal,
            self.slope_constraint, self.roughness_constraint,
        )
        return self._path

    def replan_if_needed(self, current: Waypoint, goal: Waypoint, threshold_m: float = 2.0) -> Path | None:
        if self._path is None:
            return self.plan_path(current, goal)
        if self._path.waypoints:
            last_wp = self._path.waypoints[-1]
            if last_wp.distance_to(goal) > threshold_m:
                return self.plan_path(current, goal)
        return None
