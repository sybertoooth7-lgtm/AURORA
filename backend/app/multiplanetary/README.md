# AURORA Multi-Planetary AI

One autonomous-robot brain that works on Earth, the Moon, Mars, and asteroids.
Environment differences (gravity, atmosphere, lighting, dust, terrain) are
injected as config — never hardcoded — so the same codebase evolves with the
mission.

## Capabilities

| Module | Capability |
|---|---|
| `sensors.py` | Stereo camera, hazard camera, LiDAR, environmental (temp/pressure/radiation/dust/wind) |
| `vision.py` | Frame-to-frame visual odometry; terrain-relative navigation for landing/localization |
| `navigation.py` | Terrain-aware A* with slope + roughness constraints |
| `mapping.py` | 3D occupancy map (OctoMap-style), 2.5D terrain height/slope map |
| `avoidance.py` | Reactive (bug-algorithm) + artificial potential field avoidance |
| `autonomy.py` | Behavior trees; autonomy levels 1–5; default rover behavior tree |
| `telemetry.py` | Store-and-forward deep-space relay, DTN-style link model |
| `simulation.py` | `PlanetaryEnvironment`, `LunarEnvironment`, `MarsEnvironment`, `AsteroidEnvironment` |

## Environment constants (simulation vs. hardware honest separation)

Environment parameters come from `PlanetaryEnvironment` config — gravity, solar
flux, day length, atmosphere, dust, roughness, radiation. The **same**
navigation/perception/autonomy code runs against any environment. Sensor noise
and simulated flags make it impossible to mistake simulated telemetry for
physical readings.

## Usage

```python
from app.multiplanetary.environment import get_environment  # from simulation
from app.multiplanetary.navigation import TerrainGridMap, TerrainNavigator, Waypoint
from app.multiplanetary.simulation import MarsEnvironment

env = MarsEnvironment()
hmap = env.generate_height_map(64, 64, resolution=5.0)
grid = TerrainGridMap(64, 64, resolution=5.0)
for gy in range(64):
    for gx in range(64):
        grid.set_elevation(gx, gy, hmap[gy][gx])

nav = TerrainNavigator(grid)
path = nav.plan_path(Waypoint(5, 5), Waypoint(300, 300))
```

## Autonomy levels

| Level | Meaning | AURORA support |
|---|---|---|
| 1 | Teleoperation | Remote-control interface (planned to reuse `/ai/infer` + telemetry API) |
| 2 | Assisted driving (keep-in-lane, blobs) | `ReactiveAvoidance` |
| 3 | Semi-autonomous (waypoint with human approval) | `TerrainNavigator` + behavior trees |
| 4 | Autonomous with human override | `AutonomousController`, autonomy levels, FDIR |
| 5 | Fully autonomous (long-duration, self-aware) | Extended behavior trees, store-and-forward ops |

## Evolution path

Earth rover → **same interfaces** → lunar rover → Mars rover → asteroid hopper.
New properties per body are added in `simulation.py` config only; no perception
or navigation logic changes.