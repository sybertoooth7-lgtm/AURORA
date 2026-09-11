"""Tests for the AURORA space resource program (TRL, extraction, ISRU, economics, prospecting, roadmap)."""

from app.space_resources.economics import DeliveryCostProfile, EconomicsModel, InfrastructureAsset
from app.space_resources.extraction import (
    ConstructionMaterialSinterer,
    ExtractionStatus,
    WaterIceExtractor,
)
from app.space_resources.isru import ISRUComponent, ISRUPlant, StorageTank
from app.space_resources.maturity import (
    TRL,
    ResourceTechnology,
    RiskProfile,
    Timeline,
    register_default_technologies,
)
from app.space_resources.prospecting import (
    ProspectingPlanner,
    ProspectSite,
    ResourceOccurrence,
    ResourceSignificance,
)
from app.space_resources.roadmap import ProgramMilestone, ProgramPhase, ProgramRoadmap

# ─── TRL Registry ───

def test_register_default_technologies():
    registry = register_default_technologies()
    assert registry.count == 8
    assert registry.get("mars_moxygen") is not None

def test_technology_fields():
    registry = register_default_technologies()
    moxie = registry.get("mars_moxygen")
    assert moxie.trl == TRL.PROTOTYPE
    assert moxie.production_efficiency > 0
    assert moxie.development_readiness == "demonstration"

def test_registry_by_resource():
    registry = register_default_technologies()
    water = registry.by_resource("water")
    assert len(water) == 3
    assert all(t.resource_type == "water" for t in water)

def test_registry_by_trl():
    registry = register_default_technologies()
    advanced = registry.by_trl(min_trl=6)
    assert registry.get("mars_moxygen") in advanced

def test_registry_dependency_chain():
    registry = register_default_technologies()
    chain = registry.dependency_chain("propellant_lox_lh2")
    assert "propellant_lox_lh2" in chain
    assert "lunar_water_electrodialysis" in chain

def test_registry_blocks_missing_dependency():
    registry = register_default_technologies()
    tech = ResourceTechnology(
        id="orphan_tech",
        name="Orphan",
        resource_type="water",
        trl=TRL.LAB,
        mass_kg=1.0,
        power_w=1.0,
        production_rate_kg_per_day=0.1,
        risk=RiskProfile(0.5, 0.5, 0.5, 0.5),
        timeline=Timeline(1, 1, 1),
        description="missing dep",
        dependency_ids=["nonexistent-tech"],
    )
    try:
        registry.register(tech)
        raise AssertionError("should raise for missing dependency")
    except ValueError:
        pass

def test_risk_profile_overall():
    risk = RiskProfile(technical=0.5, schedule=0.5, cost=0.5, reliability=0.5)
    assert risk.overall == 0.5

def test_timeline_total():
    tl = Timeline(2.0, 3.0, 4.0)
    assert tl.total_years == 9.0


# ─── Extraction ───

def test_water_extractor_running():
    extractor = WaterIceExtractor(efficiency=0.5, power_w=100.0)
    extractor.start()
    result = extractor.extract(hours=10.0)
    assert result.resource_type == "water"
    assert result.mass_produced_kg > 0
    assert result.status == ExtractionStatus.RUNNING

def test_water_extractor_offline():
    extractor = WaterIceExtractor()
    result = extractor.extract(hours=10.0)
    assert result.mass_produced_kg == 0.0
    assert result.status == ExtractionStatus.OFFLINE

def test_water_extractor_with_feedstock():
    extractor = WaterIceExtractor(efficiency=0.5, power_w=100.0, regolith_moisture_fraction=0.03)
    extractor.start()
    result = extractor.extract(hours=1.0, feedstock_kg=100.0)
    # 100 kg regolith at 3% moisture = 3 kg available water, capped by power
    assert result.mass_produced_kg <= 3.0
    assert extractor.total_extracted_kg > 0

def test_water_extractor_yield_fraction():
    extractor = WaterIceExtractor(efficiency=0.4, power_w=100.0)
    extractor.start()
    result = extractor.extract(hours=10.0)
    assert 0.0 < result.yield_fraction <= 1.0

def test_sinterer_with_feedstock():
    sinterer = ConstructionMaterialSinterer(efficiency=0.85, power_w=300.0)
    sinterer.start()
    result = sinterer.extract(hours=2.0, feedstock_kg=50.0)
    assert result.mass_produced_kg == 42.5
    assert result.mass_waste_kg == 7.5

def test_sinterer_offline_no_feedstock():
    sinterer = ConstructionMaterialSinterer()
    result = sinterer.extract(hours=2.0, feedstock_kg=50.0)
    assert result.mass_produced_kg == 0.0
    assert result.status == ExtractionStatus.OFFLINE

def test_extraction_specific_energy():
    extractor = WaterIceExtractor(efficiency=0.5, power_w=100.0)
    extractor.start()
    result = extractor.extract(hours=1.0)
    assert result.specific_energy_kwh_per_kg > 0


# ─── ISRU Plant ───

def test_isru_plant_full_cycle():
    plant = ISRUPlant(max_power_w=500.0)
    extractor = WaterIceExtractor(efficiency=0.5, power_w=80.0)
    plant.add_component(ISRUComponent("water-ext-1", extractor, mass_kg=45.0))
    plant.add_tank(StorageTank(resource_type="water", capacity_kg=100.0))
    plant.start_all()
    results = plant.run_cycle(hours=24.0)
    assert len(results) == 1
    tank = plant.inventory()
    assert tank["water"] > 0
    assert plant.total_energy_wh > 0
    assert plant.production_count == 1

def test_isru_plant_power_limits():
    plant = ISRUPlant(max_power_w=50.0)
    extractor = WaterIceExtractor(efficiency=0.5, power_w=80.0)
    plant.add_component(ISRUComponent("water-ext-1", extractor, mass_kg=45.0))
    plant.start_all()
    assert len([c for c in plant._components.values() if c.is_running]) == 0
    assert plant.available_power_w() == 50.0

def test_storage_tank_capacity():
    tank = StorageTank(resource_type="water", capacity_kg=100.0)
    assert tank.add(120.0) == 100.0
    assert tank.level_kg == 100.0
    assert tank.available_capacity_kg == 0.0
    assert tank.fill_fraction == 1.0
    assert tank.remove(50.0) == 50.0

def test_storage_tank_boiloff():
    tank = StorageTank(resource_type="water", capacity_kg=100.0, level_kg=50.0,
                       boiloff_rate_kg_per_day=1.0)
    loss = tank.tick_boiloff(dt_days=2.0)
    assert loss == 2.0
    assert tank.level_kg == 48.0

def test_isru_plant_tick_boiloff():
    plant = ISRUPlant()
    plant.add_tank(StorageTank(resource_type="water", capacity_kg=100.0, level_kg=50.0,
                               boiloff_rate_kg_per_day=1.0))
    losses = plant.tick_boiloff(dt_days=1.0)
    assert losses["water"] == 1.0

def test_isru_plant_status():
    plant = ISRUPlant(name="test-plant")
    plant.add_component(ISRUComponent("ext", WaterIceExtractor(), mass_kg=10.0))
    status = plant.status
    assert status["name"] == "test-plant"
    assert "components" in status
    assert "tanks" in status


# ─── Economics ───

def test_delivery_cost_profile_savings():
    profile = DeliveryCostProfile(
        resource_type="water",
        earth_launch_cost_per_kg=100000.0,
        isru_cost_per_kg=50000.0,
    )
    savings = profile.savings_vs_earth_launch(mass_kg=100.0, destination="lunar")
    assert savings == 100_000.0 * 100 - 50_000.0 * 100

def test_delivery_cost_lunar():
    profile = DeliveryCostProfile(resource_type="water")
    assert profile.delivery_cost(1.0, "lunar") == 1_000_000.0

def test_capital_cost():
    asset = InfrastructureAsset(
        name="water-plant",
        mass_kg=45.0,
        development_cost=200_000_000.0,
        unit_cost=50_000_000.0,
        production_capacity_kg_per_day=0.5,
    )
    assert asset.capital_cost == 250_000_000.0

def test_asset_cost_per_kg():
    asset = InfrastructureAsset(
        name="water-plant",
        mass_kg=45.0,
        development_cost=100_000_000.0,
        unit_cost=0.0,
        production_capacity_kg_per_day=0.5,
        expected_lifespan_days=365.0,
    )
    total_production = 0.5 * 365.0  # 182.5 kg
    assert asset.cost_per_kg_produced == 100_000_000.0 / total_production

def test_economics_model_analysis():
    model = EconomicsModel()
    result = model.cost_analysis("water", mass_kg=1000.0, destination="lunar")
    assert result["savings"] > 0
    assert result["savings_percent"] > 0

def test_economics_model_unknown_resource():
    model = EconomicsModel()
    result = model.cost_analysis("dark_matter", mass_kg=1000.0)
    assert "error" in result

def test_economics_model_break_even():
    model = EconomicsModel()
    asset = InfrastructureAsset(
        name="water-plant",
        mass_kg=45.0,
        development_cost=100_000_000.0,
        unit_cost=0.0,
        production_capacity_kg_per_day=0.5,
        expected_lifespan_days=365.0,
        technology_id="water_*",
    )
    model.add_asset(asset)
    analysis = model.break_even_analysis("water", "lunar")
    assert len(analysis["assets"]) == 1
    assert analysis["assets"][0]["break_even_days"] > 0

def test_economics_model_portfolio():
    model = EconomicsModel()
    model.add_asset(InfrastructureAsset(
        name="a", mass_kg=1.0, development_cost=100.0, unit_cost=0.0,
        production_capacity_kg_per_day=1.0,
    ))
    portfolio = model.portfolio_analysis("lunar")
    assert portfolio["total_capital_cost"] == 100.0
    assert portfolio["asset_count"] == 1


# ─── Prospecting ───

def test_prospect_site_value():
    site = ProspectSite(
        id="psr-1",
        name="Permanently Shadowed Crater",
        body="moon",
        coordinates={"x": 10.0, "y": 20.0},
        resources=[
            ResourceOccurrence(
                resource_type="water",
                significance=ResourceSignificance.PRIMARY,
                estimated_mass_kg=5000.0,
                concentration_fraction=0.03,
                depth_m=0.5,
            ),
        ],
    )
    assert site.total_resource_mass_kg == 5000.0
    assert len(site.primary_resources) == 1
    assert site.site_value_score > 0.3

def test_prospect_site_empty_value():
    site = ProspectSite(id="empty", name="Empty", body="moon", coordinates={})
    assert site.site_value_score == 0.0

def test_prospecting_planner_rank():
    planner = ProspectingPlanner()
    planner.add_site(ProspectSite(id="a", name="Poor", body="moon", coordinates={},
                                  terrain_difficulty=0.9, solar_power_availability=0.1))
    planner.add_site(ProspectSite(id="b", name="Good", body="moon", coordinates={},
                                  resources=[
                                      ResourceOccurrence("water", ResourceSignificance.PRIMARY,
                                                         1000.0, 0.05, 0.3)
                                  ],
                                  terrain_difficulty=0.1, solar_power_availability=0.9))
    ranked = planner.ranked_sites(body="moon")
    assert ranked[0].id == "b"

def test_prospecting_survey_plan():
    planner = ProspectingPlanner()
    site = ProspectSite(id="psr-1", name="PSR", body="moon", coordinates={},
                        resources=[
                            ResourceOccurrence("water", ResourceSignificance.PRIMARY,
                                               1000.0, 0.05, 0.3)
                        ])
    planner.add_site(site)
    tasks = planner.generate_survey_plan("psr-1")
    assert len(tasks) == 3
    assert tasks[0].task_type == "orbital_reconnaissance"
    assert "surface_sampling" in [t.task_type for t in tasks]

def test_prospecting_extraction_plan():
    planner = ProspectingPlanner()
    good = ProspectSite(id="good", name="Good", body="moon", coordinates={},
                        resources=[
                            ResourceOccurrence("water", ResourceSignificance.PRIMARY,
                                               1000.0, 0.08, 0.2)
                        ],
                        terrain_difficulty=0.2, solar_power_availability=0.8)
    planner.add_site(good)
    plan = planner.generate_extraction_plan("good")
    assert plan["recommendation"] == "proceed_with_extraction"
    assert len(plan["extraction_targets"]) == 1

def test_prospecting_summary():
    planner = ProspectingPlanner()
    planner.add_site(ProspectSite(id="a", name="A", body="moon", coordinates={}))
    planner.add_site(ProspectSite(id="b", name="B", body="mars", coordinates={}))
    summary = planner.summary()
    assert summary["total_sites"] == 2
    assert "moon" in summary["by_body"]
    assert "mars" in summary["by_body"]


# ─── Roadmap ───

def test_phase_enum():
    assert ProgramPhase.EARTH_TESTING.value == 1
    assert ProgramPhase.ASTEROID_RESOURCES.value == 8
    assert ProgramPhase.LUNAR_PROSPECTING.label == "Lunar Prospecting"

def test_phase_duration():
    assert ProgramPhase.EARTH_TESTING.estimated_duration_years == 3.0
    assert ProgramPhase.ASTEROID_RESOURCES.estimated_duration_years == 12.0

def test_phase_description():
    assert "laboratory" in ProgramPhase.EARTH_TESTING.description.lower()

def test_default_roadmap():
    roadmap = ProgramRoadmap()
    roadmap.generate_default_roadmap()
    assert len(roadmap.all_milestones) == 7
    assert len(roadmap.milestones_for_phase(ProgramPhase.EARTH_TESTING)) == 2

def test_roadmap_summary():
    roadmap = ProgramRoadmap()
    roadmap.generate_default_roadmap()
    summary = roadmap.program_summary()
    assert summary["total_milestones"] == 7
    assert summary["total_duration_years"] > 50
    assert summary["critical_path_milestones"] == 6

def test_roadmap_phase_summary():
    roadmap = ProgramRoadmap()
    roadmap.generate_default_roadmap()
    phases = roadmap.phase_summary()
    assert len(phases) == 8
    assert phases[0]["phase"] == "Earth Testing"
    assert phases[0]["milestone_count"] == 2

def test_roadmap_dependency_graph():
    roadmap = ProgramRoadmap()
    roadmap.generate_default_roadmap()
    graph = roadmap.technology_dependency_graph()
    assert "lunar_water_electrodialysis" in graph
    assert "mars_moxygen" in graph

def test_milestone_to_dict():
    ms = ProgramMilestone(
        id="M-T", name="Test", phase=ProgramPhase.EARTH_TESTING,
        description="Desc", success_criteria=["A"],
    )
    d = ms.to_dict()
    assert d["phase_number"] == 1
    assert d["critical_path"] is False
