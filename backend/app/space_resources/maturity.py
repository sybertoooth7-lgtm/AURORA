"""Technology Readiness Level registry for space resource technologies.

Every technology has a real-world TRL, hardware spec, energy budget,
risk profile, and development timeline.  No fictional capabilities.
"""

from dataclasses import dataclass, field
from enum import IntEnum


class TRL(IntEnum):
    LAB = 1
    CONCEPT = 2
    PROOF = 3
    LAB_VALIDATED = 4
    RELEVANT_ENV = 5
    PROTOTYPE = 6
    DEMO = 7
    QUALIFIED = 8
    PROVEN = 9


@dataclass
class RiskProfile:
    technical: float  # 0.0-1.0
    schedule: float
    cost: float
    reliability: float

    @property
    def overall(self) -> float:
        return (self.technical + self.schedule + self.cost + (1.0 - self.reliability)) / 4.0


@dataclass
class Timeline:
    development_years: float
    test_years: float
    deployment_years: float
    total_years: float = 0.0

    def __post_init__(self):
        self.total_years = self.development_years + self.test_years + self.deployment_years


@dataclass
class ResourceTechnology:
    id: str
    name: str
    resource_type: str  # water, oxygen, metals, construction_material, propellant
    trl: TRL
    mass_kg: float
    power_w: float
    production_rate_kg_per_day: float
    risk: RiskProfile
    timeline: Timeline
    description: str
    hardware: list[str] = field(default_factory=list)
    target_body: str = "lunar"
    terrestrial_heritage: str = ""
    dependency_ids: list[str] = field(default_factory=list)

    @property
    def production_efficiency(self) -> float:
        if self.power_w <= 0:
            return 0.0
        return self.production_rate_kg_per_day / self.power_w

    @property
    def development_readiness(self) -> str:
        if self.trl <= 3:
            return "research"
        elif self.trl <= 5:
            return "development"
        elif self.trl <= 7:
            return "demonstration"
        else:
            return "operational"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "resource_type": self.resource_type,
            "trl": self.trl.value,
            "mass_kg": self.mass_kg,
            "power_w": self.power_w,
            "production_kg_per_day": self.production_rate_kg_per_day,
            "risk_overall": round(self.risk.overall, 3),
            "total_timeline_years": self.timeline.total_years,
            "target_body": self.target_body,
            "readiness": self.development_readiness,
        }


class TRLRegistry:
    def __init__(self):
        self._technologies: dict[str, ResourceTechnology] = {}

    def register(self, tech: ResourceTechnology) -> None:
        for dep_id in tech.dependency_ids:
            if dep_id not in self._technologies:
                raise ValueError(f"Dependency {dep_id} not registered for {tech.id}")
        self._technologies[tech.id] = tech

    def get(self, tech_id: str) -> ResourceTechnology | None:
        return self._technologies.get(tech_id)

    def by_trl(self, min_trl: int = 1, max_trl: int = 9) -> list[ResourceTechnology]:
        return [t for t in self._technologies.values() if min_trl <= t.trl.value <= max_trl]

    def by_resource(self, resource_type: str) -> list[ResourceTechnology]:
        return [t for t in self._technologies.values() if t.resource_type == resource_type]

    def by_body(self, target_body: str) -> list[ResourceTechnology]:
        return [t for t in self._technologies.values() if t.target_body == target_body]

    @property
    def all(self) -> list[ResourceTechnology]:
        return list(self._technologies.values())

    @property
    def count(self) -> int:
        return len(self._technologies)

    def dependency_chain(self, tech_id: str) -> list[str]:
        chain = [tech_id]
        tech = self._technologies.get(tech_id)
        if tech:
            for dep_id in tech.dependency_ids:
                chain.extend(self.dependency_chain(dep_id))
        return list(dict.fromkeys(chain))


def register_default_technologies() -> TRLRegistry:
    registry = TRLRegistry()
    _defaults = [
        ResourceTechnology(
            id="lunar_water_electrodialysis",
            name="Lunar Water Extraction (Electrodialysis)",
            resource_type="water",
            trl=TRL.PROOF,
            mass_kg=45.0,
            power_w=80.0,
            production_rate_kg_per_day=0.5,
            risk=RiskProfile(technical=0.6, schedule=0.5, cost=0.4, reliability=0.5),
            timeline=Timeline(4.0, 3.0, 2.0),
            description=(
                "Electrodialysis extraction of bound water from permanently "
                "shadowed lunar regolith.  Heritage from MOXIE precursor work."
            ),
            hardware=["electrodialysis_reactor", "regolith_heater", "water_cold_trap"],
            target_body="lunar",
            terrestrial_heritage="MOXIE, Linux IQP extraction demos",
        ),
        ResourceTechnology(
            id="lunar_oxygen_rwire",
            name="Lunar Oxygen (Reaction of Iron with Water/Ice)",
            resource_type="oxygen",
            trl=TRL.CONCEPT,
            mass_kg=35.0,
            power_w=60.0,
            production_rate_kg_per_day=0.3,
            risk=RiskProfile(technical=0.7, schedule=0.6, cost=0.5, reliability=0.4),
            timeline=Timeline(5.0, 3.0, 2.0),
            description=(
                "Producing oxygen from lunar ilmenite via hydrogen reduction. "
                "HERACLES precursor heritage."
            ),
            hardware=["ilmenite_reactor", "hydrogen_loop", "oxygen_separator"],
            target_body="lunar",
            dependency_ids=["lunar_water_electrodialysis"],
        ),
        ResourceTechnology(
            id="mars_moxygen",
            name="Mars Oxygen (MOXIE-derived solid oxide electrolysis)",
            resource_type="oxygen",
            trl=TRL.PROTOTYPE,
            mass_kg=15.0,
            power_w=250.0,
            production_rate_kg_per_day=0.12,
            risk=RiskProfile(technical=0.3, schedule=0.3, cost=0.3, reliability=0.7),
            timeline=Timeline(2.0, 2.0, 1.0),
            description=(
                "Solid oxide electrolysis of CO2 from Mars atmosphere. "
                "Direct heritage from Perseverance MOXIE demo (TRL 7)."
            ),
            hardware=["SOX_electrolyzer", "CO2_compressor", "O2_separator"],
            target_body="mars",
            terrestrial_heritage="Perseverance MOXIE (2021-2023)",
        ),
        ResourceTechnology(
            id="lunar_water_ferrovolatiles",
            name="Lunar Water (Ferrovolatiles Thermal Extraction)",
            resource_type="water",
            trl=TRL.PROOF,
            mass_kg=55.0,
            power_w=120.0,
            production_rate_kg_per_day=0.8,
            risk=RiskProfile(technical=0.55, schedule=0.5, cost=0.45, reliability=0.5),
            timeline=Timeline(4.5, 3.0, 2.0),
            description=(
                "Thermal extraction of ferrovolatiles from iron-bearing "
                "lunar regolith (reduction of Fe2+ to Fe0 releases bound H2O)."
            ),
            hardware=["thermal_reactor", "regolith_feeder", "water_condenser"],
            target_body="lunar",
            dependency_ids=["lunar_water_electrodialysis"],
        ),
        ResourceTechnology(
            id="asteroid_water_heating",
            name="Asteroid Water (Thermal Desorption)",
            resource_type="water",
            trl=TRL.CONCEPT,
            mass_kg=25.0,
            power_w=50.0,
            production_rate_kg_per_day=0.2,
            risk=RiskProfile(technical=0.7, schedule=0.6, cost=0.6, reliability=0.4),
            timeline=Timeline(6.0, 3.0, 2.0),
            description=(
                "Thermal desorption of water from C-type asteroid regolith. "
                "Requires low-gravity anchoring and regolith handling."
            ),
            hardware=["heater_array", "collection_funnel", "cold_trap"],
            target_body="asteroid",
        ),
        ResourceTechnology(
            id="asteroid_metals_electrorefining",
            name="Asteroid Metals (Electrorefining)",
            resource_type="metals",
            trl=TRL.CONCEPT,
            mass_kg=80.0,
            power_w=200.0,
            production_rate_kg_per_day=0.15,
            risk=RiskProfile(technical=0.8, schedule=0.7, cost=0.7, reliability=0.3),
            timeline=Timeline(7.0, 4.0, 2.0),
            description=(
                "Electrorefining of iron-nickel from M-type asteroid regolith "
                "in microgravity.  Never flight-tested."
            ),
            hardware=["electrorefiner", "vacuum_chamber", "regolith_processor"],
            target_body="asteroid",
        ),
        ResourceTechnology(
            id="sintered_regolith_brick",
            name="Sintered Regolith Bricks",
            resource_type="construction_material",
            trl=TRL.LAB_VALIDATED,
            mass_kg=120.0,
            power_w=300.0,
            production_rate_kg_per_day=2.0,
            risk=RiskProfile(technical=0.4, schedule=0.4, cost=0.3, reliability=0.6),
            timeline=Timeline(3.0, 2.0, 2.0),
            description=(
                "Sintering lunar regolith into structural bricks using "
                "microwave or infrared heating.  Lab validated (FSTAR, "
                "Exolith Lab)."
            ),
            hardware=["sintering_furnace", "regolith_press", "mold_system"],
            target_body="lunar",
            terrestrial_heritage="FSTAR, Exolith Lab regolith simulant sintering",
        ),
        ResourceTechnology(
            id="propellant_lox_lh2",
            name="LOX/LH2 Propellant Production",
            resource_type="propellant",
            trl=TRL.RELEVANT_ENV,
            mass_kg=200.0,
            power_w=500.0,
            production_rate_kg_per_day=0.5,
            risk=RiskProfile(technical=0.5, schedule=0.5, cost=0.5, reliability=0.5),
            timeline=Timeline(5.0, 3.0, 2.0),
            description=(
                "Electrolysis of water to LOX/LH2 for in-space propulsion. "
                "Water feedstock from lunar extraction."
            ),
            hardware=["electrolyzer", "LOX_cooler", "LH2_tank", "boiloff_management"],
            target_body="lunar",
            dependency_ids=["lunar_water_electrodialysis"],
        ),
    ]
    for tech in _defaults:
        registry.register(tech)
    return registry
