"""Prospecting planner for resource sites.

Models candidate resource extraction sites, ranks them by value,
accessibility, and risk, and produces a survey/extraction plan.
"""

from dataclasses import dataclass, field
from enum import Enum


class SitePriority(Enum):
    HIGH = 3
    MEDIUM = 2
    LOW = 1


class ResourceSignificance(Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    TRACE = "trace"


@dataclass
class ResourceOccurrence:
    resource_type: str
    significance: ResourceSignificance
    estimated_mass_kg: float
    concentration_fraction: float = 0.01
    depth_m: float = 0.5
    extraction_method: str = ""

    @property
    def extraction_viability(self) -> float:
        score = {
            ResourceSignificance.PRIMARY: 1.0,
            ResourceSignificance.SECONDARY: 0.6,
            ResourceSignificance.TRACE: 0.3,
        }[self.significance]
        if self.depth_m > 2.0:
            score *= 0.5
        if self.concentration_fraction < 0.005:
            score *= 0.3
        return min(1.0, score)


@dataclass
class ProspectSite:
    id: str
    name: str
    body: str
    coordinates: dict[str, float]
    resources: list[ResourceOccurrence] = field(default_factory=list)
    terrain_difficulty: float = 0.5
    solar_power_availability: float = 0.7
    thermal_environment_c: float = -173.0
    access_window_hours: float = 0.0
    priority: SitePriority = SitePriority.MEDIUM

    @property
    def total_resource_mass_kg(self) -> float:
        return sum(r.estimated_mass_kg for r in self.resources)

    @property
    def primary_resources(self) -> list[ResourceOccurrence]:
        return [r for r in self.resources if r.significance == ResourceSignificance.PRIMARY]

    @property
    def site_value_score(self) -> float:
        if not self.resources:
            return 0.0
        resource_score = sum(r.extraction_viability for r in self.resources) / len(self.resources)
        access_score = 1.0 - min(1.0, self.terrain_difficulty)
        power_score = self.solar_power_availability
        thermal_score = max(0.0, 1.0 - abs(self.thermal_environment_c + 20) / 200)
        return (resource_score * 0.4 + access_score * 0.2 +
                power_score * 0.2 + thermal_score * 0.2)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "body": self.body,
            "coordinates": self.coordinates,
            "priority": self.priority.name,
            "value_score": round(self.site_value_score, 3),
            "total_mass_kg": self.total_resource_mass_kg,
            "primary_resources": [r.resource_type for r in self.primary_resources],
            "terrain_difficulty": self.terrain_difficulty,
            "solar_power": self.solar_power_availability,
        }


@dataclass
class ProspectingTask:
    site_id: str
    task_type: str
    duration_hours: float
    priority: int
    required_instruments: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)


class ProspectingPlanner:
    def __init__(self):
        self._sites: dict[str, ProspectSite] = {}
        self._tasks: list[ProspectingTask] = []

    def add_site(self, site: ProspectSite) -> None:
        self._sites[site.id] = site

    def remove_site(self, site_id: str) -> bool:
        if site_id in self._sites:
            del self._sites[site_id]
            return True
        return False

    def get_site(self, site_id: str) -> ProspectSite | None:
        return self._sites.get(site_id)

    @property
    def sites(self) -> list[ProspectSite]:
        return list(self._sites.values())

    def ranked_sites(self, body: str | None = None) -> list[ProspectSite]:
        candidates = list(self._sites.values())
        if body:
            candidates = [s for s in candidates if s.body == body]
        return sorted(candidates, key=lambda s: -s.site_value_score)

    def generate_survey_plan(self, site_id: str) -> list[ProspectingTask]:
        site = self._sites.get(site_id)
        if not site:
            return []
        tasks: list[ProspectingTask] = []
        tasks.append(ProspectingTask(
            site_id=site_id,
            task_type="orbital_reconnaissance",
            duration_hours=2.0,
            priority=1,
            required_instruments=["multispectral_camera", "lidar"],
        ))
        tasks.append(ProspectingTask(
            site_id=site_id,
            task_type="surface_sampling",
            duration_hours=8.0,
            priority=2,
            required_instruments=["drill", "spectrometer"],
            dependencies=["orbital_reconnaissance"],
        ))
        for res in site.resources:
            tasks.append(ProspectingTask(
                site_id=site_id,
                task_type=f"assess_{res.resource_type}",
                duration_hours=4.0,
                priority=3,
                required_instruments=["mass_spectrometer"],
                dependencies=["surface_sampling"],
            ))
        return tasks

    def generate_extraction_plan(self, site_id: str) -> dict:
        site = self._sites.get(site_id)
        if not site:
            return {"error": "site not found"}
        primary = site.primary_resources
        if not primary:
            return {"site_id": site_id, "extraction_targets": [], "recommendation": "no primary resources"}
        return {
            "site_id": site_id,
            "site_name": site.name,
            "extraction_targets": [
                {
                    "resource": r.resource_type,
                    "estimated_mass_kg": r.estimated_mass_kg,
                    "concentration": r.concentration_fraction,
                    "method": r.extraction_method or "default",
                    "viability": round(r.extraction_viability, 3),
                }
                for r in primary
            ],
            "total_mass_kg": site.total_resource_mass_kg,
            "value_score": round(site.site_value_score, 3),
            "recommendation": (
                "proceed_with_extraction" if site.site_value_score > 0.5
                else "additional_prospecting_required"
            ),
        }

    def summary(self) -> dict:
        sites = self.sites
        bodies: dict[str, list[ProspectSite]] = {}
        for s in sites:
            bodies.setdefault(s.body, []).append(s)
        return {
            "total_sites": len(sites),
            "by_body": {
                body: {
                    "count": len(body_sites),
                    "avg_value": round(
                        sum(s.site_value_score for s in body_sites) / len(body_sites), 3
                    ),
                }
                for body, body_sites in bodies.items()
            },
        }
