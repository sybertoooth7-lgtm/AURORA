"""Navigation abstractions: SLAM, path planning, obstacle avoidance.

Provides Navigator (abstract), Waypoint, and A* path planner.
All navigation runs on a 2D/3D grid that is either simulated or
populated from real sensor data.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple
import heapq
import math


class NavMode(Enum):
    WAYPOINT_FOLLOWING = "waypoint_following"
    EXPLORATION = "exploration"
    RETURN_TO_BASE = "return_to_base"
    HOLD_POSITION = "hold_position"


@dataclass(frozen=True)
class Waypoint:
    """A target position in 2D or 3D."""
    x: float
    y: float
    z: float = 0.0
    yaw: Optional[float] = None
    label: str = ""

    def distance_to(self, other: "Waypoint") -> float:
        return math.sqrt(
            (self.x - other.x) ** 2
            + (self.y - other.y) ** 2
            + (self.z - other.z) ** 2
        )


@dataclass
class Path:
    """Ordered list of waypoints from start to goal."""
    waypoints: List[Waypoint]
    cost: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def length(self) -> float:
        if len(self.waypoints) < 2:
            return 0.0
        return sum(
            self.waypoints[i].distance_to(self.waypoints[i + 1])
            for i in range(len(self.waypoints) - 1)
        )


class GridMap:
    """Simple occupancy grid (0 = free, 1 = occupied).

    Can represent terrain roughness (float 0..1) or binary occupancy.
    The grid is axis-aligned with a given resolution in metres/cell.
    """

    def __init__(self, width: int, height: int, resolution: float = 1.0):
        self.width = width
        self.height = height
        self.resolution = resolution
        self._grid: List[List[float]] = [
            [0.0 for _ in range(width)] for _ in range(height)
        ]

    def in_bounds(self, gx: int, gy: int) -> bool:
        return 0 <= gx < self.width and 0 <= gy < self.height

    def is_free(self, gx: int, gy: int) -> bool:
        return self.in_bounds(gx, gy) and self._grid[gy][gx] < 0.5

    def set_occupied(self, gx: int, gy: int, cost: float = 1.0) -> None:
        if self.in_bounds(gx, gy):
            self._grid[gy][gx] = max(0.0, min(1.0, cost))

    def set_free(self, gx: int, gy: int) -> None:
        if self.in_bounds(gx, gy):
            self._grid[gy][gx] = 0.0

    def get(self, gx: int, gy: int) -> float:
        if self.in_bounds(gx, gy):
            return self._grid[gy][gx]
        return 1.0

    def world_to_grid(self, wx: float, wy: float) -> Tuple[int, int]:
        return int(wx / self.resolution), int(wy / self.resolution)

    def grid_to_world(self, gx: int, gy: int) -> Tuple[float, float]:
        return gx * self.resolution + self.resolution / 2, gy * self.resolution + self.resolution / 2

    def occupied_count(self) -> int:
        return sum(1 for row in self._grid for v in row if v >= 0.5)


def astar(grid: GridMap, start: Waypoint, goal: Waypoint) -> Optional[Path]:
    """A* path planning on a GridMap.

    Returns a Path if reachable, None otherwise. Moves are 8-connected.
    """
    sx, sy = grid.world_to_grid(start.x, start.y)
    gx, gy = grid.world_to_grid(goal.x, goal.y)

    if not grid.in_bounds(sx, sy) or not grid.in_bounds(gx, gy):
        return None

    open_set: list = []
    heapq.heappush(open_set, (0.0, sx, sy))
    came_from: Dict[Tuple[int, int], Optional[Tuple[int, int]]] = {(sx, sy): None}
    g_score: Dict[Tuple[int, int], float] = {(sx, sy): 0.0}

    def heuristic(ax: int, ay: int) -> float:
        return math.sqrt((ax - gx) ** 2 + (ay - gy) ** 2)

    while open_set:
        _, cx, cy = heapq.heappop(open_set)
        if (cx, cy) == (gx, gy):
            path_wps: List[Waypoint] = []
            cur: Optional[Tuple[int, int]] = (gx, gy)
            while cur is not None:
                wx, wy = grid.grid_to_world(cur[0], cur[1])
                path_wps.append(Waypoint(x=wx, y=wy))
                cur = came_from[cur]
            path_wps.reverse()
            return Path(waypoints=path_wps, cost=g_score[(gx, gy)])

        for dx, dy in [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]:
            nx, ny = cx + dx, cy + dy
            if not grid.is_free(nx, ny):
                continue
            move_cost = grid.resolution * (1.414 if dx != 0 and dy != 0 else 1.0)
            tentative = g_score[(cx, cy)] + move_cost
            if tentative < g_score.get((nx, ny), float("inf")):
                came_from[(nx, ny)] = (cx, cy)
                g_score[(nx, ny)] = tentative
                heapq.heappush(open_set, (tentative + heuristic(nx, ny), nx, ny))

    return None


class Navigator(ABC):
    """Abstract navigator.

    Concrete implementations (ROS 2 Navigation2 stack, simulation path
    planner, spacecraft trajectory planner) all expose ``navigate_to()``
    and ``update()``.
    """

    mode: NavMode = NavMode.WAYPOINT_FOLLOWING
    current_goal: Optional[Waypoint] = None

    @abstractmethod
    def navigate_to(self, waypoint: Waypoint) -> Optional[Path]:
        """Plan a path and start following it."""

    @abstractmethod
    def update(self, current_pose: Any, dt: float) -> Optional[Waypoint]:
        """Return the next waypoint to follow, or None if at goal."""

    def cancel(self) -> None:
        self.current_goal = None
        self.mode = NavMode.HOLD_POSITION


class SimpleNavigator(Navigator):
    """Simulation-friendly navigator that uses A* on a GridMap."""

    def __init__(self, grid: GridMap):
        self.grid = grid
        self._path: Optional[Path] = None
        self._wp_index: int = 0
        self._reached_threshold: float = 0.5

    def navigate_to(self, waypoint: Waypoint) -> Optional[Path]:
        if self.current_goal is None:
            raise ValueError("Set current_goal before navigating")
        self.current_goal = waypoint
        self.mode = NavMode.WAYPOINT_FOLLOWING
        return self._path

    def navigate_from_to(self, start: Waypoint, goal: Waypoint) -> Optional[Path]:
        self.current_goal = goal
        self.mode = NavMode.WAYPOINT_FOLLOWING
        self._path = astar(self.grid, start, goal)
        self._wp_index = 0
        return self._path

    def update(self, current_pose: Any, dt: float) -> Optional[Waypoint]:
        if self._path is None or self._wp_index >= len(self._path.waypoints):
            return None
        wp = self._path.waypoints[self._wp_index]
        cx = getattr(current_pose, "x", 0.0)
        cy = getattr(current_pose, "y", 0.0)
        dist = math.sqrt((cx - wp.x) ** 2 + (cy - wp.y) ** 2)
        if dist < self._reached_threshold:
            self._wp_index += 1
            if self._wp_index >= len(self._path.waypoints):
                return None
            return self._path.waypoints[self._wp_index]
        return wp