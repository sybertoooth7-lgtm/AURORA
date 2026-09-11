"""Space resource program roadmap.

Eight phases from Earth-based testing through asteroid resource
development, each with concrete milestones, technology dependencies,
and risk assessments.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class ProgramPhase(Enum):
    EARTH_TESTING = 1
    LUNAR_PROSPECTING = 2
    LUNAR_PILOT_PLANT = 3
    LUNAR_PRODUCTION = 4
    MARS_PRECURSOR = 5
    MARS_PRODUCTION = 6
    ORBITAL_INFRASTRUCTURE = 7
    ASTEROID_RESOURCES = 8

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").title()

    @property
    def estimated_duration_years(self) -> float:
        return {
            1: 3.0,
            2: 4.0,
            3: 5.0,
            4: 6.0,
            5: 7.0,
            6: 8.0,
            7: 10.0,
            8: 12.0,
        }[self.value]

    @property
    def cumulative_start_year(self) -> float:
        total = 0.0
        for p in ProgramPhase:
            if p.value < self.value:
                total += p.estimated_duration_years
        return total

    @property
    def description(self) -> str:
        return {
            1: (
                "Laboratory validation of extraction processes on "
                "regolith simulants.  TRL 3→5 progression."
            ),
            2: (
                "Robotic lunar lander with prospecting instruments.  "
                "Orbital survey → targeted surface sampling."
            ),
            3: (
                "Small-scale ISRU plant on lunar surface.  Water "
                "extraction for propellant production demonstration."
            ),
            4: (
                "Scaled-up production.  LOX/LH2 propellant depot.  "
                "Regolith sintering for landing pad and habitat."
            ),
            5: (
                "MOXIE-derived Mars ISRU precursor.  Atmospheric CO2 → O2.  "
                "Water ice confirmation at Phoenix/arcadia regions."
            ),
            6: (
                "Mars surface propellant production.  Fuel for return "
                "ascent vehicle.  Oxygen for crew life support."
            ),
            7: (
                "Cislunar propellant depot.  Asteroid water prospecting.  "
                "In-space manufacturing infrastructure."
            ),
            8: (
                "Operational asteroid mining.  Water, metals, and "
                "construction materials from C-type and M-type asteroids."
            ),
        }[self.value]


@dataclass
class ProgramMilestone:
    id: str
    name: str
    phase: ProgramPhase
    description: str
    technology_ids: List[str] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)
    risk_notes: str = ""
    estimated_cost_usd: float = 0.0
    is_critical_path: bool = False

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "phase": self.phase.label,
            "phase_number": self.phase.value,
            "description": self.description,
            "technologies": self.technology_ids,
            "success_criteria": self.success_criteria,
            "critical_path": self.is_critical_path,
            "cost_usd": self.estimated_cost_usd,
        }


class ProgramRoadmap:
    def __init__(self):
        self._milestones: List[ProgramMilestone] = []

    def add_milestone(self, milestone: ProgramMilestone) -> None:
        self._milestones.append(milestone)

    def milestones_for_phase(self, phase: ProgramPhase) -> List[ProgramMilestone]:
        return [m for m in self._milestones if m.phase == phase]

    @property
    def all_milestones(self) -> List[ProgramMilestone]:
        return sorted(self._milestones, key=lambda m: (m.phase.value, m.id))

    def phase_summary(self) -> List[Dict]:
        summary = []
        for phase in ProgramPhase:
            milestones = self.milestones_for_phase(phase)
            total_cost = sum(m.estimated_cost_usd for m in milestones)
            critical = [m for m in milestones if m.is_critical_path]
            summary.append({
                "phase": phase.label,
                "phase_number": phase.value,
                "milestone_count": len(milestones),
                "critical_milestones": len(critical),
                "total_cost_usd": total_cost,
                "duration_years": phase.estimated_duration_years,
                "start_year": phase.cumulative_start_year,
                "end_year": phase.cumulative_start_year + phase.estimated_duration_years,
            })
        return summary

    def program_summary(self) -> Dict:
        total_cost = sum(m.estimated_cost_usd for m in self._milestones)
        total_years = sum(p.estimated_duration_years for p in ProgramPhase)
        critical = [m for m in self._milestones if m.is_critical_path]
        return {
            "total_milestones": len(self._milestones),
            "total_cost_usd": total_cost,
            "total_duration_years": total_years,
            "critical_path_milestones": len(critical),
            "phases": self.phase_summary(),
        }

    def technology_dependency_graph(self) -> Dict[str, List[str]]:
        graph: Dict[str, List[str]] = {}
        for m in self._milestones:
            for tech_id in m.technology_ids:
                graph.setdefault(tech_id, []).append(m.id)
        return graph

    def generate_default_roadmap(self) -> None:
        _defaults = [
            ProgramMilestone(
                id="M-E1",
                name="Extraction Process Validation",
                phase=ProgramPhase.EARTH_TESTING,
                description="Validate water extraction on lunar regolith simulant at >40% yield.",
                technology_ids=["lunar_water_electrodialysis"],
                success_criteria=["Water yield >40%", "Power <100W", "Mass <50kg"],
                risk_notes="Electrodialysis membranes degrade in abrasive regolith",
                estimated_cost_usd=15_000_000,
                is_critical_path=True,
            ),
            ProgramMilestone(
                id="M-E2",
                name="Sintered Regolith Lab Demo",
                phase=ProgramPhase.EARTH_TESTING,
                description="Demonstrate regolith sintering into structural bricks.",
                technology_ids=["sintered_regolith_brick"],
                success_criteria=["Compressive strength >10MPa", "Production rate >1kg/hr"],
                estimated_cost_usd=8_000_000,
                is_critical_path=False,
            ),
            ProgramMilestone(
                id="M-L1",
                name="Lunar Prospecting Lander",
                phase=ProgramPhase.LUNAR_PROSPECTING,
                description="Small lander with neutron spectrometer and drill to confirm water ice.",
                technology_ids=["lunar_water_electrodialysis"],
                success_criteria=[
                    "Water confirmation at PSR",
                    "Concentration map at 10m resolution",
                ],
                risk_notes="Landing near PSR is high-risk; terrain hazards.",
                estimated_cost_usd=250_000_000,
                is_critical_path=True,
            ),
            ProgramMilestone(
                id="M-L2",
                name="ISRU Pilot Plant",
                phase=ProgramPhase.LUNAR_PILOT_PLANT,
                description="Deploy small-scale water extraction plant. Produce 0.5kg/day.",
                technology_ids=["lunar_water_electrodialysis", "lunar_oxygen_rwire"],
                success_criteria=["0.5kg water/day", "90% uptime over 30 days"],
                estimated_cost_usd=400_000_000,
                is_critical_path=True,
            ),
            ProgramMilestone(
                id="M-L3",
                name="Propellant Production Demo",
                phase=ProgramPhase.LUNAR_PRODUCTION,
                description="Produce LOX/LH2 propellant from lunar water.",
                technology_ids=["propellant_lox_lh2", "lunar_water_electrodialysis"],
                success_criteria=[
                    "10kg LOX/LH2 per month",
                    "Propellant quality meets NASA-STD-2065",
                ],
                estimated_cost_usd=800_000_000,
                is_critical_path=True,
            ),
            ProgramMilestone(
                id="M-M1",
                name="MOXIE Heritage O2 Production",
                phase=ProgramPhase.MARS_PRECURSOR,
                description="Mars lander with MOXIE-derived O2 production.",
                technology_ids=["mars_moxygen"],
                success_criteria=["0.1kg O2/day", "100 sol continuous operation"],
                estimated_cost_usd=1_200_000_000,
                is_critical_path=True,
            ),
            ProgramMilestone(
                id="M-A1",
                name="Asteroid Water Prospector",
                phase=ProgramPhase.ASTEROID_RESOURCES,
                description="Demonstrate water extraction from C-type asteroid simulant.",
                technology_ids=["asteroid_water_heating", "asteroid_metals_electrorefining"],
                success_criteria=["Water detection confirmed", "Mass <30kg payload"],
                risk_notes="Microgravity regolith handling never tested",
                estimated_cost_usd=300_000_000,
                is_critical_path=True,
            ),
        ]
        for ms in _defaults:
            self._milestones.append(ms)