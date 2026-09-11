# AURORA Multi-Planetary AI

One autonomous-robot brain that works on Earth, the Moon, Mars, and asteroids.
Environment differences (gravity, atmosphere, lighting, dust, terrain) are
injected as config — never hardcoded — so the same codebase evolves with the
mission.

## Subpackages

| Package | Purpose |
|---|---|
| `(root modules)` | Sensors, vision, navigation, mapping, avoidance, autonomy, telemetry, simulation |
| `layers/` | 7-layer AI decision stack + `AuroraStack` orchestrator |
| `ops/` | Comms-delay budgets, radiation model, disconnected ops, fail-safe, cyber security |

## Capabilities (root modules)

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

## Layered AI stack (`layers/`)

```
1. mission_control     authority, autonomy budget, safety interlocks, oversight
2. scientific          hypotheses, survey plans, science value
3. robotics            fleet coordination, agent dispatch, teleop bridge
4. navigation          terrain-aware path planning + obstacle avoidance
5. resource_management inventory, allocation, energy budget
6. infrastructure      ISRU plants, power grid, comms network, habitats
7. human_assistance    advisories, verification, plain-language reporting
```

The stack runs every decision cycle: each layer proposes `Action`s, the
`MissionControlLayer` filters them through the autonomy budget and safety
interlocks, and anything irreversible or outside the autonomy budget becomes
a `request_authorization` action for human oversight.

```python
from app.multiplanetary.layers import AuroraStack, MissionContext
from app.multiplanetary.ops.fail_safe import FailSafeController, SafeModeLevel

stack = AuroraStack()                      # wires all seven layers
ctx = MissionContext(battery_percent=90.0, power_available_w=100.0,
                     power_demand_w=50.0, one_way_delay_s=1.3)
decision = stack.step(ctx)                 # StackDecision: approved / pending / rejected
for action in decision.approved_actions:
    print(action.description)
```

Fail-safe invariant: the stack checks battery, radiation, temperature, and
watchdog health *before* running any layer.  Any trip forces safe mode, which
suspends ISRU, halts rover motion, and enters minimal-power comms/thermal mode.

```python
from app.multiplanetary.ops.comms_delay import CommsDelayModel, TargetBody
from app.multiplanetary.ops.security import CyberSecurityLayer
from app.multiplanetary.ops.disconnected import DisconnectedOpsManager, MissionPlaybook

delay = CommsDelayModel.for_target(TargetBody.MARS)      # 13 min one-way -> autonomy ~4
sec = CyberSecurityLayer(secret_key=b"real-key")         # HMAC command auth, anti-replay
ops = DisconnectedOpsManager(auto=delay.autonomy_level)  # preplanned playbook execution
```

## Operations (`ops/`)

| Module | Capability |
|---|---|
| `comms_delay.py` | One-way light time per target body; autonomy budget derived from RTT |
| `radiation.py` | GCR + SPE dose model; rad-hard strategy (watchdog, latchup, EOL tracking) |
| `disconnected.py` | Disconnected ops manager: playbook execution, safe-mode fallback |
| `fail_safe.py` | `FailSafeController` with signal thresholds and command-loss detection |
| `security.py` | HMAC-signed commands, anti-replay nonce window, config integrity, rate limiting |

## Space Resource Program (`../space_resources/`)

Companion package for ISRU technology readiness, extraction process models,
plant simulation, economics, prospecting, and an 8-phase roadmap.  See
`app/space_resources/README.md`.

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