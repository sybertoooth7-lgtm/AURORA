"""AURORA Robotics: modular architecture for autonomous robots."""

from app.robotics.core.robot import Robot, RobotState, Pose3D, Velocity3D, Sensor, SensorReading, Actuator, ActuatorCommand
from app.robotics.navigation import Navigator, Waypoint
from app.robotics.perception import PerceptionEngine, PerceptionResult

__all__ = [
    "Robot", "RobotState", "Pose3D", "Velocity3D",
    "Sensor", "SensorReading", "Actuator", "ActuatorCommand",
    "Navigator", "Waypoint", "PerceptionEngine", "PerceptionResult",
]