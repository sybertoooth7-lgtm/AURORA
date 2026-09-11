"""Deterministic physics simulation for robotics.

Simulates terrain (GridMap), robot kinematics, sensor noise, and
battery drain.  No external simulator dependency (no Gazebo, no MuJoCo).
Everything runs offline for tests and offline mission rehearsal.

Simulation model
----------------
* 2D kinematic model with optional 3D pose.
* Gaussian sensor noise (configurable per-sensor).
* Constant battery drain (configurable per-actuator + base draw).
* Occupancy-grid world with terrain roughness.
"""

import math
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.robotics.core.robot import Pose3D, Velocity3D, RobotSnapshot
from app.robotics.navigation import GridMap, Waypoint


@dataclass
class SimConfig:
    """Global simulation settings."""
    dt: float = 0.1
    max_time: float = 600.0
    sensor_noise_std: float = 0.02
    battery_base_draw_w: float = 5.0
    battery_capacity_wh: float = 100.0
    motor_efficiency: float = 0.85
    gravity: float = 9.81
    seed: int = 42


class SimulatedWorld:
    """Mutable world state for the simulator."""

    def __init__(self, grid: GridMap, config: Optional[SimConfig] = None):
        self.config = config or SimConfig()
        self.grid = grid
        self.obstacles: List[Dict[str, Any]] = []
        self.dynamic_obstacles: List[Dict[str, Any]] = []

    def add_obstacle(self, x: float, y: float, radius: float = 1.0) -> None:
        self.obstacles.append({"x": x, "y": y, "radius": radius})
        gx, gy = self.grid.world_to_grid(x, y)
        r_cells = int(math.ceil(radius / self.grid.resolution))
        for dx in range(-r_cells, r_cells + 1):
            for dy in range(-r_cells, r_cells + 1):
                if dx * dx + dy * dy <= r_cells * r_cells:
                    self.grid.set_occupied(gx + dx, gy + dy)

    def add_random_obstacles(self, count: int, rng: Optional[random.Random] = None) -> None:
        rng = rng or random.Random(self.config.seed)
        for _ in range(count):
            x = rng.uniform(0, self.grid.width * self.grid.resolution)
            y = rng.uniform(0, self.grid.height * self.grid.resolution)
            r = rng.uniform(0.5, 2.0)
            self.add_obstacle(x, y, r)


class KinematicSimulator:
    """2D kinematic robot simulator.

    Tracks pose (x, y, yaw), velocity, and battery.  Ticks the world
    and robot together so sensor readings reflect the simulated state.
    """

    def __init__(self, world: SimulatedWorld, config: Optional[SimConfig] = None):
        self.config = config or world.config
        self.world = world
        self.time = 0.0
        self._rng = random.Random(self.config.seed)
        self._x = 0.0
        self._y = 0.0
        self._yaw = 0.0
        self._vx = 0.0
        self._vy = 0.0
        self._battery_wh = self.config.battery_capacity_wh
        self._battery_percent = 100.0
        self._history: List[RobotSnapshot] = []

    def reset(self, x: float = 0.0, y: float = 0.0, yaw: float = 0.0) -> None:
        self.time = 0.0
        self._x = x
        self._y = y
        self._yaw = yaw
        self._vx = self._vy = 0.0
        self._battery_wh = self.config.battery_capacity_wh
        self._battery_percent = 100.0
        self._history.clear()

    def _add_noise(self, value: float) -> float:
        return value + self._rng.gauss(0, self.config.sensor_noise_std)

    def _drain_battery(self, motor_power_w: float, dt: float) -> None:
        draw = (motor_power_w / self.config.motor_efficiency + self.config.battery_base_draw_w) * dt / 3600.0
        self._battery_wh = max(0.0, self._battery_wh - draw)
        self._battery_percent = (self._battery_wh / self.config.battery_capacity_wh) * 100.0

    def tick(self, linear_vel: float, angular_vel: float, dt: Optional[float] = None) -> RobotSnapshot:
        dt = dt or self.config.dt
        self._yaw += angular_vel * dt
        self._vx = linear_vel * math.cos(self._yaw)
        self._vy = linear_vel * math.sin(self._yaw)
        new_x = self._x + self._vx * dt
        new_y = self._y + self._vy * dt
        gx, gy = self.world.grid.world_to_grid(new_x, new_y)
        if self.world.grid.is_free(gx, gy):
            self._x, self._y = new_x, new_y
        motor_power = abs(linear_vel) * 10.0 + abs(angular_vel) * 5.0
        self._drain_battery(motor_power, dt)
        self.time += dt
        snapshot = RobotSnapshot(
            timestamp=self.time,
            pose=Pose3D(x=self._add_noise(self._x), y=self._add_noise(self._y), z=0.0),
            velocity=Velocity3D(vx=self._vx, vy=self._vy),
            battery_percent=round(self._battery_percent, 2),
            state=None,  # type: ignore[arg-type]
            metadata={"yaw": self._yaw},
        )
        self._history.append(snapshot)
        return snapshot

    @property
    def position(self) -> Waypoint:
        return Waypoint(x=self._x, y=self._y)

    @property
    def battery_percent(self) -> float:
        return self._battery_percent

    @property
    def history(self) -> List[RobotSnapshot]:
        return list(self._history)

    @property
    def is_depleted(self) -> bool:
        return self._battery_percent <= 0.0