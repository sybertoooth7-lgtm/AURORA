"""AURORA Multi-Planetary AI: sensors, vision, navigation, mapping.

Design so the same codebase handles Earth, Moon, Mars, and asteroid
missions.  Environment-specific parameters (gravity, atmosphere,
lighting, dust) are injected via config, not hardcoded.

Design goals
------------
* Visual odometry, terrain-relative navigation, and SLAM work the same
  way on every body -- only the constants change.
* Obstacle avoidance is reactive (no global map required) and supports
  store-and-forward for comms-delayed commanding.
* Behavior trees handle autonomy levels 1-5 (teleop -> fully autonomous).
* A seven-layer AI stack (mission control, scientific, robotics,
  navigation, resource management, infrastructure, human assistance)
  keeps authority, safety, and human oversight explicit.

Subpackages
-----------
* ``layers``  -- the 7-layer decision stack and AuroraStack orchestrator.
* ``ops``     -- comms-delay budgets, radiation model, disconnected ops,
                 fail-safe controller, and command/cyber security.
"""

from app.multiplanetary.sensors import StereoCamera, HazardCamera, LidarSensor, EnvironmentalSensor
from app.multiplanetary.vision import VisualOdometry, TerrainRelativeNavigation
from app.multiplanetary.navigation import TerrainNavigator, SlopeConstraint, RoughnessConstraint
from app.multiplanetary.mapping import OctoMap, OccupancyGrid3D, TerrainMap
from app.multiplanetary.avoidance import ReactiveAvoidance, PotentialFieldAvoidance
from app.multiplanetary.autonomy import BehaviorTree, AutonomyLevel, AutonomousController
from app.multiplanetary.telemetry import DeepSpaceTelemetry, StoreAndForwardRelay
from app.multiplanetary.simulation import PlanetaryEnvironment, LunarEnvironment, MarsEnvironment, AsteroidEnvironment
from app.multiplanetary.layers import (
    AuroraStack,
    MissionControlLayer,
    Action,
    ActionType,
    Layer,
    MissionContext,
    StackDecision,
)

__all__ = [
    "StereoCamera", "HazardCamera", "LidarSensor", "EnvironmentalSensor",
    "VisualOdometry", "TerrainRelativeNavigation",
    "TerrainNavigator", "SlopeConstraint", "RoughnessConstraint",
    "OctoMap", "OccupancyGrid3D", "TerrainMap",
    "ReactiveAvoidance", "PotentialFieldAvoidance",
    "BehaviorTree", "AutonomyLevel", "AutonomousController",
    "DeepSpaceTelemetry", "StoreAndForwardRelay",
    "PlanetaryEnvironment", "LunarEnvironment", "MarsEnvironment", "AsteroidEnvironment",
    "AuroraStack", "MissionControlLayer", "Action", "ActionType", "Layer",
    "MissionContext", "StackDecision",
]