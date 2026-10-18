"""Space Resource Program endpoints: TRL registry, ISRU yield, economics,
prospecting and programme roadmap (Stage 0).

These expose ``app.space_resources`` -- a set of hand-entered technology models
whose numbers are planning estimates. Nothing here is a contracted price, a
measured yield or a flight-qualified device: every extractor reduces to "power
in, resource out" against one simplified energy-to-mass constant, and the cost
profiles are single literals per destination. The responses say so, because a
savings percentage from this code is an argument for more study, not a business
case.

Yields are energy-limited rather than feedstock-limited: asking for more
regolith does not produce more water once the power budget is spent.
"""

import math

from fastapi import APIRouter, Depends, Query

from app.ai.base import Provenance
from app.exceptions import NotFoundError
from app.models.user import User
from app.schemas.space_resources import (
    EconomicsResponse,
    ExtractionRequest,
    ExtractionResponse,
    OccurrenceViability,
    ProspectingRequest,
    ProspectingResponse,
    ProspectPlan,
    RoadmapPhase,
    RoadmapResponse,
    TechnologyDetailResponse,
    TechnologyListResponse,
    TechnologyOut,
)
from app.security import get_current_user
from app.space_resources.economics import EconomicsModel
from app.space_resources.extraction import (
    ConstructionMaterialSinterer,
    ExtractionProcess,
    MetalExtractor,
    OxygenFromRegolith,
    WaterIceExtractor,
)
from app.space_resources.maturity import ResourceTechnology, register_default_technologies
from app.space_resources.prospecting import (
    ProspectingPlanner,
    ProspectSite,
    ResourceOccurrence,
    ResourceSignificance,
    SitePriority,
)
from app.space_resources.roadmap import ProgramRoadmap

router = APIRouter(prefix="/space-resources", tags=["Space Resources"])

_PROCESSES: dict[str, type[ExtractionProcess]] = {
    "water_ice": WaterIceExtractor,
    "oxygen_regolith": OxygenFromRegolith,
    "metals": MetalExtractor,
    "construction_material": ConstructionMaterialSinterer,
    "generic": ExtractionProcess,
}

_TECH_LIMITATIONS = [
    "TRLs, masses, power draws and rates are hand-entered planning values",
    "risk and timeline numbers are analyst estimates, not scored assessments",
    "no technology here is flight-qualified or even hardware-complete",
]

_ECONOMICS_LIMITATIONS = [
    "cost per kilogram is one literal per destination, not a market price",
    "assumes the mass you ask for is the mass you have to deliver",
    "excludes development, launch-vehicle, ops and insurance costs",
    "ISRU cost is a steady-state figure: no plant amortisation in this view",
]

_EXTRACTION_LIMITATIONS = [
    "all four processes share one simplified energy-to-mass constant",
    "yield is energy-limited: extra feedstock beyond the power budget changes nothing",
    "mass_waste_kg is balanced against the extractable fraction of the feedstock, "
    "so produced plus waste does not equal the feedstock mass you supplied",
    "no process heat management, no consumables, no maintenance downtime",
    "product purity, containment and boil-off are not modelled per process",
    "the sinterer needs feedstock to report anything and reads offline without "
    "it, while the other three processes are purely energy-limited",
    "specific_energy_kwh_per_kg is null for a run that produced nothing",
]

_PROSPECTING_LIMITATIONS = [
    "occurrence masses and concentrations are caller-supplied guesses",
    "site value is a fixed weighted sum (0.4 mass, 0.2 solar, 0.2 access, 0.2 terrain)",
    "significance-to-viability factors are hand-tuned, not measured",
    "no remote-sensing input: nothing here looks at real orbital data",
]

_ROADMAP_LIMITATIONS = [
    "phase durations are a fixed table, not a scheduled plan",
    "milestone costs are order-of-magnitude estimates",
    "the dependency graph is declared by hand and is not resource-levelled",
]


def _technology_out(tech: ResourceTechnology) -> TechnologyOut:
    return TechnologyOut(
        id=tech.id,
        name=tech.name,
        resource_type=tech.resource_type,
        trl=int(tech.trl.value),
        readiness=tech.development_readiness,
        mass_kg=tech.mass_kg,
        power_w=tech.power_w,
        production_kg_per_day=tech.production_rate_kg_per_day,
        production_efficiency=round(tech.production_efficiency, 6),
        risk_overall=round(tech.risk.overall, 3),
        total_timeline_years=tech.timeline.total_years,
        target_body=tech.target_body,
        terrestrial_heritage=tech.terrestrial_heritage,
    )


@router.get("/technologies", response_model=TechnologyListResponse)
def list_technologies(
    target_body: str | None = Query(default=None, max_length=30),
    resource_type: str | None = Query(default=None, max_length=30),
    min_trl: int = Query(default=1, ge=1, le=9),
    max_trl: int = Query(default=9, ge=1, le=9),
    current_user: User = Depends(get_current_user),
):
    """The TRL-grounded technology registry, optionally filtered."""
    registry = register_default_technologies()
    if target_body is not None:
        technologies = registry.by_body(target_body)
    elif resource_type is not None:
        technologies = registry.by_resource(resource_type)
    else:
        technologies = registry.by_trl(min_trl=min_trl, max_trl=max_trl)
    if target_body is not None or resource_type is not None:
        technologies = [
            tech for tech in technologies if min_trl <= int(tech.trl.value) <= max_trl
        ]

    return TechnologyListResponse(
        provenance=Provenance.SIMULATED,
        count=len(technologies),
        technologies=[_technology_out(tech) for tech in technologies],
        model_limitations=_TECH_LIMITATIONS,
    )


@router.get("/technologies/{tech_id}", response_model=TechnologyDetailResponse)
def technology_detail(
    tech_id: str,
    current_user: User = Depends(get_current_user),
):
    """One technology in full, including what it depends on."""
    registry = register_default_technologies()
    tech = registry.get(tech_id)
    if tech is None:
        raise NotFoundError(f"Unknown technology '{tech_id}'")

    base = _technology_out(tech).model_dump()
    return TechnologyDetailResponse(
        **base,
        provenance=Provenance.SIMULATED,
        description=tech.description,
        hardware=list(tech.hardware),
        dependency_ids=list(tech.dependency_ids),
        dependency_chain=registry.dependency_chain(tech.id),
        risk={
            "technical": tech.risk.technical,
            "schedule": tech.risk.schedule,
            "cost": tech.risk.cost,
            "reliability": tech.risk.reliability,
        },
        timeline_years={
            "development": tech.timeline.development_years,
            "test": tech.timeline.test_years,
            "deployment": tech.timeline.deployment_years,
            "total": tech.timeline.total_years,
        },
        model_limitations=_TECH_LIMITATIONS,
    )


@router.get("/economics/{resource_type}", response_model=EconomicsResponse)
def delivery_economics(
    resource_type: str,
    mass_kg: float = Query(default=100.0, gt=0.0, le=1e7),
    destination: str = Query(default="lunar", max_length=20),
    current_user: User = Depends(get_current_user),
):
    """Delivering a mass from Earth vs producing it in situ."""
    model = EconomicsModel()
    profile = model.get_profile(resource_type)
    if profile is None:
        raise NotFoundError(
            f"No cost profile for resource '{resource_type}'",
            details={"known": sorted(_resource_types(model))},
        )

    analysis = model.cost_analysis(resource_type, mass_kg, destination)
    return EconomicsResponse(
        provenance=Provenance.SIMULATED,
        resource_type=resource_type,
        mass_kg=mass_kg,
        destination=destination,
        earth_launch_cost=round(analysis["earth_launch_cost"], 2),
        in_situ_cost=round(analysis["in_situ_cost"], 2),
        savings=round(analysis["savings"], 2),
        savings_percent=round(analysis["savings_percent"], 2),
        profile={
            "earth_launch_cost_per_kg": profile.earth_launch_cost_per_kg,
            "lunar_delivery_cost_per_kg": profile.lunar_delivery_cost_per_kg,
            "mars_delivery_cost_per_kg": profile.mars_delivery_cost_per_kg,
            "isru_cost_per_kg": profile.isru_cost_per_kg,
        },
        model_limitations=_ECONOMICS_LIMITATIONS,
    )


@router.post("/extraction", response_model=ExtractionResponse)
def simulate_extraction(
    request: ExtractionRequest,
    current_user: User = Depends(get_current_user),
):
    """Run one extraction process for a window and report what it produced."""
    process_class = _PROCESSES[request.process]
    kwargs: dict[str, float] = {}
    if request.power_w is not None:
        kwargs["power_w"] = request.power_w
    if request.efficiency is not None:
        kwargs["efficiency"] = request.efficiency

    process = process_class(**kwargs)
    # Extraction only runs once the process is started; calling extract() on an
    # offline process returns a zero result, which is not what a caller asking
    # for a yield wants.
    process.start()
    result = process.extract(request.hours, request.feedstock_kg)
    specific_energy = result.specific_energy_kwh_per_kg

    return ExtractionResponse(
        provenance=Provenance.SIMULATED,
        process=request.process,
        resource_type=result.resource_type,
        hours=result.duration_hours,
        feedstock_kg=request.feedstock_kg,
        mass_produced_kg=round(result.mass_produced_kg, 4),
        mass_waste_kg=round(result.mass_waste_kg, 4),
        energy_used_wh=round(result.energy_used_wh, 3),
        yield_fraction=round(result.yield_fraction, 5),
        # A run that produced nothing reports infinity for specific energy,
        # which has no JSON representation and no meaning for a planner.
        specific_energy_kwh_per_kg=None if math.isfinite(specific_energy) else None,
        status=result.status.value,
        model_limitations=_EXTRACTION_LIMITATIONS,
    )


@router.post("/prospecting", response_model=ProspectingResponse)
def rank_prospect_sites(
    request: ProspectingRequest,
    current_user: User = Depends(get_current_user),
):
    """Score and rank candidate sites supplied by the caller."""
    planner = ProspectingPlanner()
    for entry in request.sites:
        planner.add_site(
            ProspectSite(
                id=entry.id,
                name=entry.name or entry.id,
                body=entry.body,
                coordinates=dict(entry.coordinates),
                resources=[
                    ResourceOccurrence(
                        resource_type=occurrence.resource_type,
                        significance=ResourceSignificance[occurrence.significance.upper()],
                        estimated_mass_kg=occurrence.estimated_mass_kg,
                        concentration_fraction=occurrence.concentration_fraction,
                        depth_m=occurrence.depth_m,
                        extraction_method=occurrence.extraction_method,
                    )
                    for occurrence in entry.resources
                ],
                terrain_difficulty=entry.terrain_difficulty,
                solar_power_availability=entry.solar_power_availability,
                access_window_hours=entry.access_window_hours,
                priority=SitePriority[entry.priority.upper()],
            )
        )

    ranked = planner.ranked_sites(request.body)

    return ProspectingResponse(
        provenance=Provenance.SIMULATED,
        ranked=[
            ProspectPlan(
                id=site.id,
                name=site.name,
                body=site.body,
                value_score=round(site.site_value_score, 4),
                total_mass_kg=site.total_resource_mass_kg,
                primary_resources=[
                    occurrence.resource_type for occurrence in site.primary_resources
                ],
                viability=[
                    OccurrenceViability(
                        resource_type=occurrence.resource_type,
                        significance=occurrence.significance.value,
                        estimated_mass_kg=occurrence.estimated_mass_kg,
                        viability=round(occurrence.extraction_viability, 4),
                    )
                    for occurrence in site.resources
                ],
            )
            for site in ranked
        ],
        summary=planner.summary(),
        model_limitations=_PROSPECTING_LIMITATIONS,
    )


@router.get("/roadmap", response_model=RoadmapResponse)
def program_roadmap(current_user: User = Depends(get_current_user)):
    """The eight-phase programme, its default milestones and total cost."""
    roadmap = ProgramRoadmap()
    roadmap.generate_default_roadmap()
    summary = roadmap.program_summary()

    return RoadmapResponse(
        provenance=Provenance.SIMULATED,
        total_milestones=summary["total_milestones"],
        total_cost_usd=float(summary["total_cost_usd"]),
        total_duration_years=float(summary["total_duration_years"]),
        critical_path_milestones=summary["critical_path_milestones"],
        phases=[RoadmapPhase(**phase) for phase in summary["phases"]],
        milestones=[milestone.to_dict() for milestone in roadmap.all_milestones],
        model_limitations=_ROADMAP_LIMITATIONS,
    )


def _resource_types(model: EconomicsModel) -> set[str]:
    # EconomicsModel seeds its profiles privately and exposes no lister, so the
    # known set is mirrored here to make the 404 helpful rather than opaque.
    return {
        resource
        for resource in ("water", "oxygen", "metals", "propellant", "construction_material")
        if model.get_profile(resource) is not None
    }
