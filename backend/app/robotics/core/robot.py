"""Core abstractions for AURORA robotics.

Defines the Robot, Sensor, and Actuator base classes that every concrete
robot (Earth rover, CubeSat, lunar lander) implements. These are deliberately
hardware-agnostic: a ROS 2 backend, a simulation backend, and a direct-I2C
backend all implement the same interfaces.

Robot lifecycle
---------------
1. Construct with a config dict.
2. ``attach_sensor(sensor)`` / ``attach_actuator(actuator)``.
3. ``tick(dt)`` advances the simulation / read-hardware cycle by one timestep.
4. ``state`` gives the current odometry / pose / battery snapshot.
5. ``shutdown()`` gracefully stops all subsystems.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RobotState(Enum):
    """High-level lifecycle state of a robot."""
    INIT = "init"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    SHUTDOWN = "shutdown"


@dataclass
class Pose3D:
    """Position + orientation in 3D (quaternion)."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    qw: float = 1.0
    qx: float = 0.0
    qy: float = 0.0
    qz: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {"x": self.x, "y": self.y, "z": self.z,
                "qw": self.qw, "qx": self.qx, "qy": self.qy, "qz": self.qz}


@dataclass
class Velocity3D:
    """Linear + angular velocity."""
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    wx: float = 0.0
    wy: float = 0.0
    wz: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {"vx": self.vx, "vy": self.vy, "vz": self.vz,
                "wx": self.wx, "wy": self.wy, "wz": self.wz}


@dataclass
class RobotSnapshot:
    """Immutable snapshot of robot state at one instant."""
    timestamp: float
    pose: Pose3D
    velocity: Velocity3D
    battery_percent: float
    state: RobotState
    sensor_readings: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "pose": self.pose.to_dict(),
            "velocity": self.velocity.to_dict(),
            "battery_percent": self.battery_percent,
            "state": self.state.value,
            "sensor_readings": self.sensor_readings,
            "metadata": self.metadata,
        }


class Sensor(ABC):
    """Abstract sensor interface.

    Concrete sensors (camera, lidar, IMU, GPS, multispectral) implement
    ``read()`` which returns a ``SensorReading``. In simulation mode the
    sensor draws from the simulated world; in hardware mode it reads from
    the physical device. The caller never needs to know which backend it is.
    """

    name: str = "unnamed_sensor"
    sensor_type: str = "unknown"
    sampling_hz: float = 10.0
    is_simulated: bool = True

    @abstractmethod
    def read(self) -> "SensorReading":
        """Sample the sensor and return a reading."""

    def initialize(self) -> None:
        """One-time hardware / simulation setup."""

    def shutdown(self) -> None:
        """Release resources."""


@dataclass
class SensorReading:
    """One sensor sample at one timestamp."""
    sensor_name: str
    sensor_type: str
    timestamp: float
    data: dict[str, Any]
    is_simulated: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "sensor_name": self.sensor_name,
            "sensor_type": self.sensor_type,
            "timestamp": self.timestamp,
            "data": self.data,
            "is_simulated": self.is_simulated,
        }


class Actuator(ABC):
    """Abstract actuator interface.

    Motors, servos, thrusters, reaction wheels, magnetorquers -- all
    implement ``command()`` which returns the actual state after
    execution. Same simulation / hardware duality as sensors.
    """

    name: str = "unnamed_actuator"
    actuator_type: str = "unknown"
    is_simulated: bool = True

    @abstractmethod
    def command(self, value: float) -> "ActuatorCommand":
        """Send a command value (velocity, torque, angle, ...). Returns actual."""

    def initialize(self) -> None:
        pass

    def shutdown(self) -> None:
        pass


@dataclass
class ActuatorCommand:
    """Result of commanding an actuator."""
    actuator_name: str
    actuator_type: str
    timestamp: float
    commanded: float
    actual: float
    is_simulated: bool = True


class Robot(ABC):
    """Base robot class.

    A robot owns a set of sensors and actuators and exposes a single
    ``tick(dt)`` method that advances all subsystems by one timestep.
    The concrete subclass decides what happens inside tick (odometry,
    state estimation, health checks).

    Subclasses must set:
        name, config defaults, and implement tick() + _estimate_state().
    """

    name: str = "unnamed_robot"
    config: dict[str, Any] = {}

    def __post_init__(self):
        self._sensors: list[Sensor] = []
        self._actuators: list[Actuator] = []
        self._state = RobotState.INIT
        self._pose = Pose3D()
        self._velocity = Velocity3D()
        self._battery_percent = 100.0
        self._tick_count = 0
        self._sim_time = 0.0

    def attach_sensor(self, sensor: Sensor) -> None:
        self._sensors.append(sensor)

    def attach_actuator(self, actuator: Actuator) -> None:
        self._actuators.append(actuator)

    def initialize(self) -> None:
        for s in self._sensors:
            s.initialize()
        for a in self._actuators:
            a.initialize()
        self._state = RobotState.READY

    @abstractmethod
    def tick(self, dt: float) -> RobotSnapshot:
        """Advance the robot by dt seconds. Subclass defines the physics."""

    @abstractmethod
    def _estimate_state(self) -> None:
        """Update pose/velocity from sensor fusion."""

    def snapshot(self) -> RobotSnapshot:
        readings = {}
        for s in self._sensors:
            readings[s.name] = s.read().data
        return RobotSnapshot(
            timestamp=self._sim_time,
            pose=self._pose,
            velocity=self._velocity,
            battery_percent=self._battery_percent,
            state=self._state,
            sensor_readings=readings,
            metadata={"tick_count": self._tick_count},
        )

    @property
    def state(self) -> RobotState:
        return self._state

    @property
    def pose(self) -> Pose3D:
        return self._pose

    @property
    def sim_time(self) -> float:
        return self._sim_time

    def shutdown(self) -> None:
        for s in self._sensors:
            s.shutdown()
        for a in self._actuators:
            a.shutdown()
        self._state = RobotState.SHUTDOWN
