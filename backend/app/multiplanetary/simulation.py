"""Planetary environment models: Lunar, Mars, Asteroid.

Each environment defines gravity, atmosphere, lighting, dust, terrain
roughness, and temperature -- all parameters that affect the same robot
software differently depending on which body it is operating on.
"""

import math
import random
from dataclasses import dataclass


@dataclass
class PlanetaryEnvironment:
    name: str = "earth"
    gravity_ms2: float = 9.81
    atmosphere_pressure_pa: float = 101325.0
    has_atmosphere: bool = True
    solar_flux_wm2: float = 1361.0
    temperature_range_c: tuple[float, float] = (-40.0, 60.0)
    mean_temperature_c: float = 15.0
    day_length_s: float = 86400.0
    dust_density: float = 0.0
    radiation_multiplier: float = 1.0
    terrain_roughness: float = 0.1
    slope_range_deg: tuple[float, float] = (0.0, 30.0)
    regolith_depth_m: float = 5.0

    def generate_height_map(
        self, width: int, height: int, resolution: float = 1.0, seed: int = 42
    ) -> list[list[float]]:
        rng = random.Random(seed)
        hmap = [[0.0] * width for _ in range(height)]
        for gy in range(height):
            for gx in range(width):
                x = gx * resolution
                y = gy * resolution
                h = (
                    0.3 * math.sin(x * 0.1) * math.cos(y * 0.1)
                    + 0.1 * rng.gauss(0, self.terrain_roughness)
                    + 0.05 * math.sin(x * 0.5 + y * 0.3)
                )
                hmap[gy][gx] = h
        return hmap

    def generate_obstacles(
        self, count: int, area_km2: float = 1.0, seed: int = 42
    ) -> list[dict]:
        rng = random.Random(seed)
        obstacles = []
        side_m = math.sqrt(area_km2) * 1000
        for _ in range(count):
            x = rng.uniform(0, side_m)
            y = rng.uniform(0, side_m)
            if self.name == "lunar":
                r = rng.uniform(0.5, 5.0)
                obs_type = rng.choice(["crater", "boulder", "ridge"])
            elif self.name == "mars":
                r = rng.uniform(0.3, 8.0)
                obs_type = rng.choice(["rock", "dune", "crater", "ridge"])
            else:
                r = rng.uniform(0.2, 3.0)
                obs_type = rng.choice(["rock", "boulder", "debris"])
            obstacles.append({"x": x, "y": y, "radius": r, "type": obs_type})
        return obstacles

    def light_conditions(self, time_of_day_s: float) -> dict:
        if not self.has_atmosphere:
            fraction = max(0.0, math.sin(2 * math.pi * time_of_day_s / self.day_length_s))
            return {"illumination": fraction, "shadow_length_factor": 1.0 / max(fraction, 0.01)}
        return {"illumination": 1.0, "shadow_length_factor": 1.0}


class LunarEnvironment(PlanetaryEnvironment):
    def __init__(self):
        super().__init__(
            name="lunar",
            gravity_ms2=1.62,
            atmosphere_pressure_pa=0.0,
            has_atmosphere=False,
            solar_flux_wm2=1361.0,
            temperature_range_c=(-173.0, 127.0),
            mean_temperature_c=-20.0,
            day_length_s=29.5 * 86400.0,
            dust_density=0.01,
            radiation_multiplier=2.5,
            terrain_roughness=0.15,
            slope_range_deg=(0.0, 35.0),
            regolith_depth_m=10.0,
        )


class MarsEnvironment(PlanetaryEnvironment):
    def __init__(self):
        super().__init__(
            name="mars",
            gravity_ms2=3.72,
            atmosphere_pressure_pa=600.0,
            has_atmosphere=True,
            solar_flux_wm2=589.0,
            temperature_range_c=(-140.0, 20.0),
            mean_temperature_c=-60.0,
            day_length_s=88775.0,
            dust_density=0.05,
            radiation_multiplier=1.5,
            terrain_roughness=0.2,
            slope_range_deg=(0.0, 40.0),
            regolith_depth_m=5.0,
        )


class AsteroidEnvironment(PlanetaryEnvironment):
    def __init__(self):
        super().__init__(
            name="asteroid",
            gravity_ms2=0.001,
            atmosphere_pressure_pa=0.0,
            has_atmosphere=False,
            solar_flux_wm2=1361.0,
            temperature_range_c=(-200.0, 100.0),
            mean_temperature_c=-80.0,
            day_length_s=43200.0,
            dust_density=0.0,
            radiation_multiplier=5.0,
            terrain_roughness=0.3,
            slope_range_deg=(0.0, 90.0),
            regolith_depth_m=0.5,
        )


def get_environment(name: str) -> PlanetaryEnvironment:
    envs = {
        "earth": PlanetaryEnvironment(),
        "lunar": LunarEnvironment(),
        "mars": MarsEnvironment(),
        "asteroid": AsteroidEnvironment(),
    }
    return envs.get(name, PlanetaryEnvironment())
