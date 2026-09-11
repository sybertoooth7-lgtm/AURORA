"""Multi-planetary sensors: stereo cameras, hazard cameras, environmental.

Same abstract sensor interfaces as Earth robotics, but configured for
harsh planetary environments (vacuum, radiation, extreme temperatures).
"""

import math
import random
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PointCloud:
    points: list[tuple[float, float, float]]
    intensities: list[float] | None = None
    timestamp: float = 0.0
    frame_id: str = "body_frame"

    @property
    def size(self) -> int:
        return len(self.points)

    def bounds(self) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        zs = [p[2] for p in self.points]
        return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))


@dataclass
class HazardMap:
    width: int
    height: int
    resolution_m: float
    hazard_level: list[list[float]]
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_hazardous(self, gx: int, gy: int, threshold: float = 0.5) -> bool:
        if 0 <= gx < self.width and 0 <= gy < self.height:
            return self.hazard_level[gy][gx] >= threshold
        return True


class StereoCamera:
    def __init__(
        self,
        name: str = "stereo_cam",
        baseline_m: float = 0.12,
        focal_length_px: float = 640.0,
        resolution: tuple[int, int] = (640, 480),
        fov_deg: float = 60.0,
        is_simulated: bool = True,
    ):
        self.name = name
        self.baseline_m = baseline_m
        self.focal_length_px = focal_length_px
        self.resolution = resolution
        self.fov_deg = fov_deg
        self.is_simulated = is_simulated
        self._rng = random.Random(42)

    def compute_depth(self, disparity_px: float) -> float:
        if disparity_px <= 0:
            return float("inf")
        return (self.baseline_m * self.focal_length_px) / disparity_px

    def generate_point_cloud(self, depth_map: Any, timestamp: float = 0.0) -> PointCloud:
        h, w = self.resolution[1], self.resolution[0]
        points: list[tuple[float, float, float]] = []
        step = max(1, h // 50)
        for y in range(0, h, step):
            for x in range(0, w, step):
                if isinstance(depth_map, list) and y < len(depth_map) and x < len(depth_map[y]):
                    d = depth_map[y][x]
                else:
                    d = 5.0 + self._rng.gauss(0, 0.1)
                if 0.1 < d < 100.0:
                    fx = self.focal_length_px
                    cx, cy = w / 2, h / 2
                    px = (x - cx) * d / fx
                    py = (y - cy) * d / fx
                    points.append((px, py, d))
        return PointCloud(points=points, timestamp=timestamp, frame_id=self.name)


class HazardCamera:
    def __init__(self, name: str = "hazard_cam", fov_deg: float = 120.0, is_simulated: bool = True):
        self.name = name
        self.fov_deg = fov_deg
        self.is_simulated = is_simulated

    def detect_hazards(self, point_cloud: PointCloud, slope_threshold_deg: float = 25.0) -> HazardMap:
        w, h = 20, 20
        hazard_level = [[0.0] * w for _ in range(h)]
        for px, py, pz in point_cloud.points:
            gx = min(w - 1, max(0, int((px + 10) * w / 20)))
            gy = min(h - 1, max(0, int((py + 10) * h / 20)))
            if pz > 0.5:
                hazard_level[gy][gx] = min(1.0, hazard_level[gy][gx] + 0.1)
        return HazardMap(width=w, height=h, resolution_m=1.0, hazard_level=hazard_level)


class LidarSensor:
    def __init__(self, name: str = "lidar", max_range_m: float = 100.0, angular_res_deg: float = 0.5, is_simulated: bool = True):
        self.name = name
        self.max_range_m = max_range_m
        self.angular_res_deg = angular_res_deg
        self.is_simulated = is_simulated
        self._rng = random.Random(42)

    def scan(self, num_rays: int = 360, timestamp: float = 0.0) -> PointCloud:
        points: list[tuple[float, float, float]] = []
        for i in range(num_rays):
            angle = 2 * math.pi * i / num_rays
            r = self.max_range_m * (0.3 + 0.7 * self._rng.random())
            points.append((r * math.cos(angle), r * math.sin(angle), 0.0))
        return PointCloud(points=points, timestamp=timestamp, frame_id=self.name)


@dataclass
class EnvironmentalReading:
    timestamp: float
    temperature_c: float = -170.0
    pressure_pa: float = 0.0
    radiation_mgymy_h: float = 0.0
    dust_opacity: float = 0.0
    wind_speed_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class EnvironmentalSensor:
    def __init__(self, environment: str = "lunar", is_simulated: bool = True):
        self.environment = environment
        self.is_simulated = is_simulated
        self._rng = random.Random(42)

    def read(self, timestamp: float = 0.0) -> EnvironmentalReading:
        if self.environment == "lunar":
            return EnvironmentalReading(
                timestamp=timestamp,
                temperature_c=self._rng.gauss(-170, 50),
                pressure_pa=0.0,
                radiation_mgymy_h=self._rng.uniform(0.5, 5.0),
            )
        elif self.environment == "mars":
            return EnvironmentalReading(
                timestamp=timestamp,
                temperature_c=self._rng.gauss(-60, 20),
                pressure_pa=600.0 + self._rng.gauss(0, 50),
                radiation_mgymy_h=self._rng.uniform(0.1, 1.0),
                dust_opacity=self._rng.uniform(0.0, 0.5),
                wind_speed_ms=self._rng.uniform(0.0, 20.0),
            )
        else:
            return EnvironmentalReading(timestamp=timestamp)
