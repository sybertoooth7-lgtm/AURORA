"""3D mapping: OctoMap-style occupancy grid and terrain maps.

Provides a volumetric 3D occupancy map (OctoMap-like) for obstacle
mapping and a 2.5D terrain height map for slope analysis.
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class Voxel:
    x: int
    y: int
    z: int
    occupancy: float = 0.5
    color: Optional[Tuple[int, int, int]] = None
    observation_count: int = 0

    @property
    def is_occupied(self) -> bool:
        return self.occupancy > 0.5


class OctoMap:
    """Simplified OctoMap using a flat dictionary of voxels.

    Full octree implementation would be complex; this gives the same
    API surface and can be upgraded to a real octree later.
    """

    def __init__(self, resolution: float = 0.1, max_range: float = 10.0):
        self.resolution = resolution
        self.max_range = max_range
        self._voxels: Dict[Tuple[int, int, int], Voxel] = {}
        self._hit_count = 0
        self._miss_count = 0

    def world_to_voxel(self, x: float, y: float, z: float) -> Tuple[int, int, int]:
        return (
            int(x / self.resolution),
            int(y / self.resolution),
            int(z / self.resolution),
        )

    def voxel_to_world(self, vx: int, vy: int, vz: int) -> Tuple[float, float, float]:
        return (
            vx * self.resolution + self.resolution / 2,
            vy * self.resolution + self.resolution / 2,
            vz * self.resolution + self.resolution / 2,
        )

    def insert_point(self, x: float, y: float, z: float, hit: bool = True) -> None:
        vx, vy, vz = self.world_to_voxel(x, y, z)
        key = (vx, vy, vz)
        if key not in self._voxels:
            self._voxels[key] = Voxel(x=vx, y=vy, z=vz)
        voxel = self._voxels[key]
        voxel.observation_count += 1
        alpha = 0.1
        if hit:
            voxel.occupancy = voxel.occupancy + alpha * (1.0 - voxel.occupancy)
            self._hit_count += 1
        else:
            voxel.occupancy = voxel.occupancy * (1.0 - alpha)
            self._miss_count += 1

    def insert_ray(self, origin: Tuple[float, float, float], endpoint: Tuple[float, float, float]) -> None:
        step = self.resolution * 0.5
        dx = endpoint[0] - origin[0]
        dy = endpoint[1] - origin[1]
        dz = endpoint[2] - origin[2]
        dist = math.sqrt(dx ** 2 + dy ** 2 + dz ** 2)
        if dist < 1e-6:
            return
        steps = int(dist / step)
        for i in range(steps):
            t = i / max(steps, 1)
            x = origin[0] + dx * t
            y = origin[1] + dy * t
            z = origin[2] + dz * t
            self.insert_point(x, y, z, hit=False)
        self.insert_point(endpoint[0], endpoint[1], endpoint[2], hit=True)

    def is_occupied(self, x: float, y: float, z: float) -> bool:
        vx, vy, vz = self.world_to_voxel(x, y, z)
        voxel = self._voxels.get((vx, vy, vz))
        return voxel.is_occupied if voxel else False

    def occupied_voxels(self) -> List[Voxel]:
        return [v for v in self._voxels.values() if v.is_occupied]

    @property
    def size(self) -> int:
        return len(self._voxels)

    @property
    def occupied_count(self) -> int:
        return len(self.occupied_voxels())

    def clear(self) -> None:
        self._voxels.clear()
        self._hit_count = 0
        self._miss_count = 0


class OccupancyGrid3D(OctoMap):
    """3D occupancy grid (alias of OctoMap with fixed resolution).

    The MVP uses a flat voxel map; a true octree can replace the
    backing store without changing the public API.
    """

    def __init__(self, resolution: float = 0.1, max_range: float = 10.0):
        super().__init__(resolution=resolution, max_range=max_range)


class TerrainMap:
    """2.5D terrain height map for slope and roughness analysis."""

    def __init__(self, width: int, height: int, resolution: float = 1.0):
        self.width = width
        self.height = height
        self.resolution = resolution
        self._elevation = [[0.0] * width for _ in range(height)]
        self._confidence = [[0.0] * width for _ in range(height)]

    def set_height(self, gx: int, gy: int, height_m: float, confidence: float = 1.0) -> None:
        if 0 <= gx < self.width and 0 <= gy < self.height:
            self._elevation[gy][gx] = height_m
            self._confidence[gy][gx] = confidence

    def get_height(self, gx: int, gy: int) -> float:
        if 0 <= gx < self.width and 0 <= gy < self.height:
            return self._elevation[gy][gx]
        return 0.0

    def compute_slope(self, gx: int, gy: int) -> float:
        neighbors = []
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = gx + dx, gy + dy
            if 0 <= nx < self.width and 0 <= ny < self.height:
                diff = self._elevation[gy][gx] - self._elevation[ny][nx]
                neighbors.append(abs(diff) / self.resolution)
        if not neighbors:
            return 0.0
        avg_gradient = sum(neighbors) / len(neighbors)
        return math.degrees(math.atan(avg_gradient))

    def compute_roughness(self, gx: int, gy: int) -> float:
        heights = []
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                nx, ny = gx + dx, gy + dy
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    heights.append(self._elevation[ny][nx])
        if len(heights) < 2:
            return 0.0
        mean_h = sum(heights) / len(heights)
        variance = sum((h - mean_h) ** 2 for h in heights) / len(heights)
        return math.sqrt(variance) / self.resolution