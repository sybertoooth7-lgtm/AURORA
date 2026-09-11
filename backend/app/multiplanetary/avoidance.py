"""Reactive obstacle avoidance for planetary rovers.

Two algorithms:
1. ReactiveAvoidance: Bug-algorithm style, purely reactive.
2. PotentialFieldAvoidance: Artificial potential field method.

Both are real-time, map-free, and work identically in simulation
and on hardware.
"""

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class Obstacle:
    x: float
    y: float
    distance_m: float = 0.0
    bearing_rad: float = 0.0
    size_m: float = 1.0


@dataclass
class AvoidanceCommand:
    linear_velocity: float
    angular_velocity: float
    obstacle_detected: bool
    closest_distance_m: float = float("inf")
    metadata: dict = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> dict:
        return {
            "linear_velocity": round(self.linear_velocity, 4),
            "angular_velocity": round(self.angular_velocity, 4),
            "obstacle_detected": self.obstacle_detected,
            "closest_distance_m": round(self.closest_distance_m, 3),
        }


class ReactiveAvoidance:
    """Bug-algorithm reactive obstacle avoidance.

    When no obstacle is detected, drives forward.
    When an obstacle is detected, turns away from it.
    """

    def __init__(
        self,
        safe_distance_m: float = 2.0,
        stop_distance_m: float = 0.5,
        forward_speed: float = 0.3,
        turn_speed: float = 0.5,
    ):
        self.safe_distance_m = safe_distance_m
        self.stop_distance_m = stop_distance_m
        self.forward_speed = forward_speed
        self.turn_speed = turn_speed

    def compute(self, obstacles: List[Obstacle]) -> AvoidanceCommand:
        if not obstacles:
            return AvoidanceCommand(
                linear_velocity=self.forward_speed,
                angular_velocity=0.0,
                obstacle_detected=False,
            )

        closest = min(obstacles, key=lambda o: o.distance_m)

        if closest.distance_m < self.stop_distance_m:
            return AvoidanceCommand(
                linear_velocity=0.0,
                angular_velocity=self.turn_speed,
                obstacle_detected=True,
                closest_distance_m=closest.distance_m,
            )

        if closest.distance_m < self.safe_distance_m:
            turn_dir = 1.0 if closest.bearing_rad > 0 else -1.0
            speed_scale = max(0.1, closest.distance_m / self.safe_distance_m)
            return AvoidanceCommand(
                linear_velocity=self.forward_speed * speed_scale,
                angular_velocity=self.turn_speed * turn_dir,
                obstacle_detected=True,
                closest_distance_m=closest.distance_m,
            )

        return AvoidanceCommand(
            linear_velocity=self.forward_speed,
            angular_velocity=0.0,
            obstacle_detected=False,
            closest_distance_m=closest.distance_m,
        )


class PotentialFieldAvoidance:
    """Artificial potential field method.

    Attractive field toward goal, repulsive field from obstacles.
    Produces smooth velocity commands.
    """

    def __init__(
        self,
        attractive_gain: float = 1.0,
        repulsive_gain: float = 5.0,
        influence_distance: float = 5.0,
        max_speed: float = 0.5,
    ):
        self.attractive_gain = attractive_gain
        self.repulsive_gain = repulsive_gain
        self.influence_distance = influence_distance
        self.max_speed = max_speed

    def compute(
        self,
        current_pos: Tuple[float, float],
        goal: Tuple[float, float],
        obstacles: List[Obstacle],
    ) -> AvoidanceCommand:
        dx = goal[0] - current_pos[0]
        dy = goal[1] - current_pos[1]
        dist_to_goal = math.sqrt(dx ** 2 + dy ** 2)

        if dist_to_goal < 0.1:
            return AvoidanceCommand(linear_velocity=0, angular_velocity=0, obstacle_detected=False)

        fx_attract = self.attractive_gain * dx / dist_to_goal
        fy_attract = self.attractive_gain * dy / dist_to_goal

        fx_repulse = 0.0
        fy_repulse = 0.0
        closest_dist = float("inf")

        for obs in obstacles:
            if obs.distance_m < closest_dist:
                closest_dist = obs.distance_m
            if obs.distance_m < self.influence_distance and obs.distance_m > 0.01:
                ox = -math.cos(obs.bearing_rad) * obs.distance_m
                oy = -math.sin(obs.bearing_rad) * obs.distance_m
                factor = self.repulsive_gain * (1.0 / obs.distance_m - 1.0 / self.influence_distance) / (obs.distance_m ** 2)
                fx_repulse += factor * ox
                fy_repulse += factor * oy

        fx = fx_attract + fx_repulse
        fy = fy_attract + fy_repulse
        magnitude = math.sqrt(fx ** 2 + fy ** 2)
        if magnitude > 0:
            fx = fx / magnitude * min(magnitude, self.max_speed)
            fy = fy / magnitude * min(magnitude, self.max_speed)

        linear = math.sqrt(fx ** 2 + fy ** 2)
        angular = math.atan2(fy, fx) if linear > 0.01 else 0.0

        return AvoidanceCommand(
            linear_velocity=linear,
            angular_velocity=angular,
            obstacle_detected=obstacles is not None and len(obstacles) > 0,
            closest_distance_m=closest_dist,
        )