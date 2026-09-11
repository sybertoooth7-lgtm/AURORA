"""AURORA Multi-Planetary AI: layered architecture.

The full AI stack separates concerns into seven cooperating layers,
each with distinct responsibilities, plus a mission-control authority
guard that enforces safety, human oversight, and fail-safe invariants.

Stack order (high to low authority)
-----------------------------------
1. Mission control      - authority, autonomy budget, safety interlocks
2. Scientific intel     - hypotheses, survey plans, science value
3. Robotics             - fleet coordination, agent dispatch, teleop bridge
4. Navigation           - terrain-aware path planning + obstacle avoidance
5. Resource management  - inventory, allocation, energy budget
6. Infrastructure       - ISRU plants, power grid, comms network, habitats
7. Human assistance     - advisories, verification, plain-language reports

The stack runs every decision cycle: each layer proposes ``Action``s;
``MissionControlLayer`` filters them through the autonomy budget and
safety interlocks; anything irreversible or outside the autonomy budget
is turned into a ``request_authorization`` action for human oversight.
"""

from app.multiplanetary.layers.core import (
    Action,
    ActionType,
    Layer,
    MissionContext,
    StackDecision,
)
from app.multiplanetary.layers.human_assistance import HumanAssistanceLayer
from app.multiplanetary.layers.infrastructure import InfrastructureLayer
from app.multiplanetary.layers.mission_control import MissionControlLayer
from app.multiplanetary.layers.navigation_layer import NavigationLayer
from app.multiplanetary.layers.resource_management import ResourceManagementLayer
from app.multiplanetary.layers.robotics import RoboticsLayer
from app.multiplanetary.layers.scientific import ScientificIntelligenceLayer
from app.multiplanetary.layers.stack import AuroraStack

__all__ = [
    "Action", "ActionType", "Layer", "MissionContext", "StackDecision",
    "MissionControlLayer", "ScientificIntelligenceLayer", "RoboticsLayer",
    "NavigationLayer", "ResourceManagementLayer", "InfrastructureLayer",
    "HumanAssistanceLayer", "AuroraStack",
]
