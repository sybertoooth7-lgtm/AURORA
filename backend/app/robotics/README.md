# AURORA Robotics Foundation

Modular, simulation-first architecture for autonomous robots. Designed so the
same abstractions scale from Earth robots (agriculture, inspection,
environmental monitoring) to CubeSat spacecraft and future lunar/Mars/asteroid
rovers.

## Design principles

1. **Simulation-first.** Every component has a deterministic simulation backend.
   Nothing talks to real motors/cameras unless a concrete ROS 2 / hardware
   backend is explicitly selected.
2. **Hardware-agnostic interfaces.** A ROS 2 node, a CAN-bus driver, and a
   simulation stub all implement the same abstract `Sensor`/`Actuator`/`Robot`
   interfaces. Swapping backends never touches navigation or perception code.
3. **Honest provenance.** Simulated data is always labelled `is_simulated=True`
   so it can never be mistaken for real sensor data.

## Components

| Module | Purpose |
|---|---|
| `core/robot.py` | `Robot`, `Sensor`, `Actuator`, `Pose3D`, `RobotSnapshot` |
| `navigation.py` | `Navigator`, `Waypoint`, `Path`, `GridMap`, A* planner |
| `perception.py` | `PerceptionEngine`, detections, bounding boxes, segmentation |
| `control.py` | `PIDController`, velocity/position PID wrappers |
| `simulation.py` | `GridMap` world, kinematic simulator, battery model |
| `telemetry.py` | structured telemetry logging (`TelemetryLogger`) |
| `config.py` | dataclass configs for every subsystem |

## Usage (offline simulation)

```python
from app.robotics.simulation import SimConfig, SimulatedWorld, KinematicSimulator
from app.robotics.navigation import GridMap
from app.robotics.perception import SyntheticPerceptionEngine

world = SimulatedWorld(GridMap(40, 40))
world.add_random_obstacles(8)
sim = KinematicSimulator(world, SimConfig(dt=0.1, battery_capacity_wh=50.0))
sim.reset()
for step in range(100):
    snap = sim.tick(linear_vel=0.3, angular_vel=0.0)
    if sim.battery_percent < 20:
        break
```

## ROS 2 integration (future/optional)

ROS 2 nodes would implement the same `Sensor`/`Actuator` interfaces:
- `Robot → node`, publishing `RobotSnapshot` on `~/pose`, `~/state`.
- `Sensor.read() → subscription` to camera/image_raw, lidar scans, IMU.
- `Navigator → action server` for `NavigateToPose`.
- `PerceptionEngine → publisher` of detected objects.

The abstraction layer is deliberately dependency-free so the core stays
importable without a ROS 2 install.

## Testing

```bash
cd backend
pytest tests/robotics/
```

81 offline tests cover robotics + spacecraft + multi-planetary subsystems; no
DB, no network, no ROS daemon required.