"""AURORA Space Resources: technology readiness, ISRU, extraction, economics.

Models the realistic progression from Earth-based testing through lunar
prospecting, resource mapping, robotic extraction, ISRU, propellant
production, orbital infrastructure, and asteroid resources.  No fictional
capabilities -- every technology entry carries a real-world TRL, hardware
spec, energy budget, risk profile, and development timeline.
"""

from app.space_resources.economics import DeliveryCostProfile, EconomicsModel
from app.space_resources.extraction import (
    ConstructionMaterialSinterer,
    ExtractionProcess,
    MetalExtractor,
    OxygenFromRegolith,
    WaterIceExtractor,
)
from app.space_resources.isru import ISRUComponent, ISRUPlant
from app.space_resources.maturity import TRL, ResourceTechnology, register_default_technologies
from app.space_resources.prospecting import ProspectingPlanner, ProspectSite
from app.space_resources.roadmap import ProgramMilestone, ProgramPhase, ProgramRoadmap

__all__ = [
    "TRL", "ResourceTechnology", "register_default_technologies",
    "ExtractionProcess", "WaterIceExtractor", "OxygenFromRegolith",
    "MetalExtractor", "ConstructionMaterialSinterer",
    "ISRUPlant", "ISRUComponent",
    "EconomicsModel", "DeliveryCostProfile",
    "ProspectSite", "ProspectingPlanner",
    "ProgramPhase", "ProgramMilestone", "ProgramRoadmap",
]
