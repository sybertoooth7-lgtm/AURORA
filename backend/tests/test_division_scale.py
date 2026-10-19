"""Tests for the breadth scaling round: the five division route surfaces.

Two things are checked everywhere. First the honesty envelope -- every Stage 0
division response must arrive labelled as simulation, with the specific limits
of the model that produced it, so a number from this code cannot be forwarded
as a measurement. Second the engine truth -- the assertions below are the
behaviours the underlying models actually have, including the ones that look
like bugs (a fixed orbital period, an always-zero payload counter, yields that
stop rising when the power budget runs out).
"""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.job_metrics import COUNTER_NAMES, record
from app.models.user import User
from app.queue import get_redis
from app.schemas.simulation import STAGE
from main import app

_ACCOUNT_SEQ = 0

_SIMULATED_SURFACE = [
    ("POST", "/spacecraft/simulate", {"altitude_km": 500.0, "duration_s": 3600.0, "dt_s": 20.0, "sample_points": 5}),
    ("GET", "/spacecraft/link-budget?distance_km=1200", None),
    ("GET", "/spacecraft/orbit?altitude_km=500", None),
    ("POST", "/space-division/constellation", {"satellites": [{"id": "sat-1", "plane": {}}]}),
    (
        "POST",
        "/space-division/ground-contacts",
        {"requests": [{"satellite_id": "sat-1", "ground_station": "gs-0", "start_s": 0.0, "end_s": 60.0}]},
    ),
    (
        "POST",
        "/mission-planning/schedule",
        {"tasks": [{"id": "t-1", "latest_finish_s": 600.0, "duration_s": 60.0}]},
    ),
    ("POST", "/multiplanetary/decide", {"environment": "lunar", "target_body": "moon"}),
    ("GET", "/multiplanetary/environments", None),
    ("GET", "/multiplanetary/environments/lunar", None),
    ("GET", "/multiplanetary/comms-delay/mars", None),
    ("GET", "/space-resources/technologies", None),
    ("GET", "/space-resources/technologies/lunar_water_electrodialysis", None),
    ("GET", "/space-resources/economics/water?mass_kg=250&destination=lunar", None),
    ("POST", "/space-resources/extraction", {"process": "water_ice", "hours": 24.0, "feedstock_kg": 1000.0}),
    (
        "POST",
        "/space-resources/prospecting",
        {
            "sites": [
                {
                    "id": "site-1",
                    "body": "lunar",
                    "resources": [{"resource_type": "water", "estimated_mass_kg": 5e5}],
                }
            ]
        },
    ),
    ("GET", "/space-resources/roadmap", None),
]


def _auth_headers(client, *, admin=False, password="correcthorsebatterystaple"):
    global _ACCOUNT_SEQ
    _ACCOUNT_SEQ += 1
    username = f"division_user_{_ACCOUNT_SEQ}"
    client.post(
        "/auth/register",
        json={"email": f"{username}@test.com", "username": username, "password": password},
    )
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        assert user is not None
        user.email_verified_at = datetime.now(UTC)
        if admin:
            user.is_admin = True
        db.commit()
    finally:
        db.close()
    token = client.post(
        "/auth/token", json={"username": username, "password": password}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def headers(client):
    return _auth_headers(client)


@pytest.fixture(autouse=True)
def _clean_state():
    redis = get_redis()

    def _wipe():
        for prefix in ("auth:*", "quota:*", "ratelimit:*", "jobs:*"):
            for key in redis.keys(prefix):
                redis.delete(key)

    _wipe()
    yield
    _wipe()


class TestSimulationEnvelope:
    """Every division response carries its own disclaimer; none of them is optional."""

    @pytest.mark.parametrize("method,path,payload", _SIMULATED_SURFACE)
    def test_surface_is_labelled_simulation(self, client, headers, method, path, payload):
        response = client.request(method, path, json=payload, headers=headers)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["provenance"] == "simulated"
        assert body["stage"] == STAGE
        assert len(body["model_limitations"]) >= 2

    def test_telemetry_endpoint_is_the_one_real_source(self, client, headers):
        """Data readiness reports the platform's own observed state, so it says real."""
        body = client.get("/mission-planning/data-readiness", headers=headers).json()

        assert body["provenance"] == "real"
        assert body["stage"] == "platform_telemetry"
        assert len(body["model_limitations"]) >= 1

    @pytest.mark.parametrize("method,path,payload", _SIMULATED_SURFACE)
    def test_surface_requires_a_user(self, client, method, path, payload):
        assert client.request(method, path, json=payload).status_code == 401


class TestRequestBounds:
    """Bounds are enforced at the schema, so a bad request never reaches the engine."""

    @pytest.mark.parametrize(
        "payload",
        [
            {"altitude_km": 100.0},
            {"altitude_km": 5000.0},
            {"inclination_deg": 200.0},
            {"duration_s": 10.0},
            {"dt_s": 0.5},
            {"sample_points": 1},
            {"sample_points": 5000},
        ],
    )
    def test_simulate_bounds(self, client, headers, payload):
        body = {"altitude_km": 400.0, "duration_s": 600.0, "dt_s": 10.0, "sample_points": 10}
        body.update(payload)
        assert client.post("/spacecraft/simulate", json=body, headers=headers).status_code == 422

    @pytest.mark.parametrize(
        "path",
        [
            "/spacecraft/link-budget?distance_km=0",
            "/spacecraft/link-budget?distance_km=99999",
            "/spacecraft/orbit?altitude_km=100",
            "/space-resources/economics/water?mass_kg=0",
            "/space-resources/technologies?min_trl=12",
        ],
    )
    def test_query_bounds(self, client, headers, path):
        assert client.get(path, headers=headers).status_code == 422

    def test_extraction_window_is_bounded(self, client, headers):
        assert (
            client.post(
                "/space-resources/extraction",
                json={"process": "water_ice", "hours": 0.0},
                headers=headers,
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/space-resources/extraction",
                json={"process": "not_a_process", "hours": 1.0},
                headers=headers,
            ).status_code
            == 422
        )

    def test_task_that_cannot_fit_its_window_is_rejected(self, client, headers):
        response = client.post(
            "/mission-planning/schedule",
            json={
                "tasks": [
                    {"id": "t-1", "earliest_start_s": 0.0, "latest_finish_s": 30.0, "duration_s": 60.0}
                ]
            },
            headers=headers,
        )

        assert response.status_code == 422
        assert "cannot fit" in response.text

    def test_contact_window_must_run_forward(self, client, headers):
        response = client.post(
            "/space-division/ground-contacts",
            json={
                "requests": [
                    {"satellite_id": "sat-1", "ground_station": "gs-0", "start_s": 120.0, "end_s": 60.0}
                ]
            },
            headers=headers,
        )

        assert response.status_code == 422
        assert "ends before it starts" in response.text

    def test_empty_collections_are_rejected(self, client, headers):
        assert (
            client.post("/space-division/constellation", json={"satellites": []}, headers=headers).status_code
            == 422
        )
        assert (
            client.post("/space-resources/prospecting", json={"sites": []}, headers=headers).status_code
            == 422
        )


class TestSpacecraftSimulation:
    def test_payload_counter_stays_zero_as_documented(self, client, headers):
        """The coupled loop never triggers the payload; the limitation says so."""
        body = client.post(
            "/spacecraft/simulate",
            json={"duration_s": 5550.0, "dt_s": 30.0, "sample_points": 20},
            headers=headers,
        ).json()

        assert body["images_captured"] == 0
        assert any("images_captured" in line for line in body["model_limitations"])

    def test_coupled_loop_holds_its_period_while_orbit_uses_kepler(self, client, headers):
        low = client.get("/spacecraft/orbit?altitude_km=400", headers=headers).json()
        high = client.get("/spacecraft/orbit?altitude_km=800", headers=headers).json()
        sim = client.post(
            "/spacecraft/simulate",
            json={"altitude_km": 800.0, "duration_s": 600.0, "dt_s": 30.0},
            headers=headers,
        ).json()

        assert high["period_min"] > low["period_min"]
        assert sim["orbital_period_s"] == 5550.0
        assert any("5550" in line for line in sim["model_limitations"])

    def test_kepler_velocity_and_period_are_consistent(self, client, headers):
        body = client.get("/spacecraft/orbit?altitude_km=500", headers=headers).json()

        assert 7.4 < body["velocity_kms"] < 7.7
        assert body["eclipse_fraction_assumed"] == 0.35

    def test_trajectory_is_sampled_to_the_requested_size(self, client, headers):
        body = client.post(
            "/spacecraft/simulate",
            json={"duration_s": 3600.0, "dt_s": 10.0, "sample_points": 6},
            headers=headers,
        ).json()

        assert body["steps"] == 360
        assert len(body["trajectory"]) <= 6

    def test_eclipse_fraction_tracks_the_fixed_shadow_model(self, client, headers):
        body = client.post(
            "/spacecraft/simulate",
            json={"duration_s": 5550.0, "dt_s": 10.0, "sample_points": 3},
            headers=headers,
        ).json()

        assert 0.30 <= body["eclipse_fraction"] <= 0.40

    def test_link_budget_worsens_with_range(self, client, headers):
        near = client.get("/spacecraft/link-budget?distance_km=500", headers=headers).json()
        far = client.get("/spacecraft/link-budget?distance_km=30000", headers=headers).json()

        assert far["path_loss_db"] > near["path_loss_db"]
        assert far["received_power_dbm"] < near["received_power_dbm"]
        assert near["snr_db"] > far["snr_db"]


class TestSpaceDivision:
    def test_fleet_reports_planes_and_revisit(self, client, headers):
        satellites = [
            {"id": f"sat-{plane}-{index}", "plane": {"inclination_deg": 97.4, "altitude_km": 500.0, "raan_deg": plane * 90.0}}
            for plane in (0, 1)
            for index in range(2)
        ]
        body = client.post(
            "/space-division/constellation",
            json={"name": "test-fleet", "satellites": satellites},
            headers=headers,
        ).json()

        assert body["satellites"] == 4
        assert body["operational"] == 4
        assert len(body["planes"]) == 2
        period_min = body["planes"][0]["period_min"]
        assert body["revisit_interval_hours"] == round(period_min / 60.0 / 4, 3)

    def test_fleet_with_no_operational_satellite_has_no_revisit(self, client, headers):
        body = client.post(
            "/space-division/constellation",
            json={
                "satellites": [
                    {"id": "sat-1", "status": "decommissioned", "plane": {"altitude_km": 500.0}}
                ]
            },
            headers=headers,
        ).json()

        assert body["operational"] == 0
        assert body["revisit_interval_hours"] is None

    def test_station_grants_the_higher_priority_request(self, client, headers):
        shared = {"ground_station": "gs-0", "start_s": 100.0, "end_s": 200.0}
        body = client.post(
            "/space-division/ground-contacts",
            json={
                "requests": [
                    {"satellite_id": "low", "priority": 10, **shared},
                    {"satellite_id": "high", "priority": 90, "ground_station": "gs-0", "start_s": 150.0, "end_s": 260.0},
                ]
            },
            headers=headers,
        ).json()

        assert body["requested"] == 2
        assert [item["satellite_id"] for item in body["granted"]] == ["high"]
        assert len(body["conflicts"]) == 1
        assert "gs-0" in body["conflicts"][0]["reason"]
        assert "high" in body["conflicts"][0]["reason"]

    def test_non_overlapping_requests_both_grant(self, client, headers):
        body = client.post(
            "/space-division/ground-contacts",
            json={
                "requests": [
                    {"satellite_id": "sat-1", "ground_station": "gs-0", "start_s": 0.0, "end_s": 60.0},
                    {"satellite_id": "sat-2", "ground_station": "gs-0", "start_s": 60.0, "end_s": 120.0},
                ]
            },
            headers=headers,
        ).json()

        assert len(body["granted"]) == 2
        assert body["conflicts"] == []


class TestMissionPlanningSchedule:
    def test_priority_decides_who_gets_the_only_slot(self, client, headers):
        body = client.post(
            "/mission-planning/schedule",
            json={
                "tasks": [
                    {"id": "routine", "priority": "low", "earliest_start_s": 0.0, "latest_finish_s": 60.0, "duration_s": 60.0, "resource_requirements": {"power": 1.0}},
                    {"id": "urgent", "priority": "critical", "earliest_start_s": 0.0, "latest_finish_s": 60.0, "duration_s": 60.0, "resource_requirements": {"power": 1.0}},
                ],
                "budgets": [{"name": "power", "capacity": 1.0, "unit": "kW"}],
            },
            headers=headers,
        ).json()

        assert [item["id"] for item in body["scheduled"]] == ["urgent"]
        assert body["conflicts"][0]["id"] == "routine"

    def test_demand_above_capacity_is_rejected_with_the_numbers(self, client, headers):
        body = client.post(
            "/mission-planning/schedule",
            json={
                "tasks": [{"id": "big", "latest_finish_s": 60.0, "duration_s": 60.0, "resource_requirements": {"power": 5.0}}],
                "budgets": [{"name": "power", "capacity": 2.0, "unit": "kW"}],
            },
            headers=headers,
        ).json()

        assert body["scheduled"] == []
        assert "5.0kW" in body["conflicts"][0]["reason"]
        assert "2.0kW" in body["conflicts"][0]["reason"]

    def test_contact_task_without_a_window_explains_itself(self, client, headers):
        body = client.post(
            "/mission-planning/schedule",
            json={
                "tasks": [{"id": "downlink", "latest_finish_s": 60.0, "duration_s": 30.0, "requires_contact": True}]
            },
            headers=headers,
        ).json()

        assert "none are registered" in body["conflicts"][0]["reason"]

    def test_contact_window_makes_the_task_placeable(self, client, headers):
        body = client.post(
            "/mission-planning/schedule",
            json={
                "tasks": [{"id": "downlink", "earliest_start_s": 0.0, "latest_finish_s": 500.0, "duration_s": 30.0, "requires_contact": True}],
                "contact_windows": [{"ground_station": "gs-0", "start_s": 200.0, "end_s": 300.0}],
            },
            headers=headers,
        ).json()

        assert body["scheduled"][0]["start_s"] == 200.0
        assert body["window_start_s"] == 0.0
        assert body["window_end_s"] == 500.0

    def test_schedule_is_ordered_by_start(self, client, headers):
        body = client.post(
            "/mission-planning/schedule",
            json={
                "tasks": [
                    {"id": "a", "earliest_start_s": 0.0, "latest_finish_s": 100.0, "duration_s": 50.0},
                    {"id": "b", "earliest_start_s": 50.0, "latest_finish_s": 150.0, "duration_s": 50.0},
                ],
                "budgets": [{"name": "cpu", "capacity": 1.0}],
            },
            headers=headers,
        ).json()

        starts = [item["start_s"] for item in body["scheduled"]]
        assert starts == sorted(starts)


class TestDataReadiness:
    def test_a_day_with_no_jobs_reads_as_unknown_not_healthy(self, client, headers):
        body = client.get("/mission-planning/data-readiness", headers=headers).json()

        demo = next(item for item in body["sources"] if item["name"] == "demo")
        assert demo["status"] == "unknown"
        assert set(body["observations"]) == set(COUNTER_NAMES)
        assert body["observations"] == {name: 0 for name in COUNTER_NAMES}

    def test_status_follows_job_outcomes(self, client, headers):
        record("completed", 3)
        healthy = next(
            item
            for item in client.get("/mission-planning/data-readiness", headers=headers).json()["sources"]
            if item["name"] == "demo"
        )
        assert healthy["status"] == "healthy"

        record("failed", 1)
        degraded = next(
            item
            for item in client.get("/mission-planning/data-readiness", headers=headers).json()["sources"]
            if item["name"] == "demo"
        )
        assert degraded["status"] == "degraded"

    def test_everything_failing_reads_as_down(self, client, headers):
        record("failed", 4)
        body = client.get("/mission-planning/data-readiness", headers=headers).json()

        demo = next(item for item in body["sources"] if item["name"] == "demo")
        assert demo["status"] == "down"
        assert body["overall"] in {"down", "degraded"}

    def test_credentialless_live_source_is_reported_down(self, client, headers):
        """Without Copernicus credentials the real source cannot serve anything."""
        body = client.get("/mission-planning/data-readiness", headers=headers).json()

        sentinel = next(item for item in body["sources"] if item["name"] == "sentinel-2-l2a")
        assert sentinel["status"] == "down"
        assert sentinel["schedulable"] is False
        assert "health probe" in body["basis"]


class TestMultiPlanetaryStack:
    def test_healthy_context_produces_seven_layers(self, client, headers):
        body = client.post(
            "/multiplanetary/decide",
            json={"environment": "lunar", "target_body": "moon", "battery_percent": 90.0},
            headers=headers,
        ).json()

        assert len(body["layers_evaluated"]) == 7
        assert body["layers_evaluated"][-1] == "mission_control"
        assert any("never executed" in line for line in body["model_limitations"])

    def test_critical_battery_trips_safe_mode(self, client, headers):
        body = client.post(
            "/multiplanetary/decide",
            json={"environment": "lunar", "target_body": "moon", "battery_percent": 3.0},
            headers=headers,
        ).json()

        assert body["safe_mode_active"] is True
        assert body["warnings"] == ["battery critically low"]
        assert body["approved"] and all(item["severity"] == "critical" for item in body["approved"])

    def test_safe_mode_does_not_persist_across_requests(self, client, headers):
        client.post(
            "/multiplanetary/decide",
            json={"environment": "lunar", "battery_percent": 1.0},
            headers=headers,
        )
        body = client.post(
            "/multiplanetary/decide",
            json={"environment": "lunar", "battery_percent": 95.0},
            headers=headers,
        ).json()

        assert body["safe_mode_active"] is False

    def test_radiation_event_is_a_fail_safe_too(self, client, headers):
        body = client.post(
            "/multiplanetary/decide",
            json={"environment": "mars", "battery_percent": 80.0, "environment_sensor": {"radiation_event": True}},
            headers=headers,
        ).json()

        assert body["warnings"] == ["radiation event detected"]

    def test_context_bounds_are_enforced(self, client, headers):
        assert (
            client.post("/multiplanetary/decide", json={"autonomy_level": 9}, headers=headers).status_code == 422
        )
        assert (
            client.post("/multiplanetary/decide", json={"battery_percent": -1.0}, headers=headers).status_code == 422
        )

    def test_environment_catalogue(self, client, headers):
        body = client.get("/multiplanetary/environments", headers=headers).json()

        assert [item["name"] for item in body["environments"]] == ["earth", "lunar", "mars", "asteroid"]
        lunar = next(item for item in body["environments"] if item["name"] == "lunar")
        earth = next(item for item in body["environments"] if item["name"] == "earth")
        assert lunar["gravity_ms2"] < earth["gravity_ms2"]
        assert lunar["has_atmosphere"] is False

    def test_unknown_environment_is_a_404_not_a_silent_earth(self, client, headers):
        """``get_environment`` falls back to Earth; the endpoint must not."""
        response = client.get("/multiplanetary/environments/luunar", headers=headers)

        assert response.status_code == 404
        assert response.json()["details"]["known"] == ["earth", "lunar", "mars", "asteroid"]

    def test_environment_detail_carries_the_envelope(self, client, headers):
        body = client.get("/multiplanetary/environments/mars", headers=headers).json()

        assert body["provenance"] == "simulated"
        assert body["environment"]["name"] == "mars"
        assert len(body["model_limitations"]) >= 1

    def test_light_time_drives_the_autonomy_level(self, client, headers):
        moon = client.get("/multiplanetary/comms-delay/moon", headers=headers).json()
        mars = client.get("/multiplanetary/comms-delay/mars", headers=headers).json()
        leo = client.get("/multiplanetary/comms-delay/earth_leo", headers=headers).json()

        assert leo["real_time"] is True
        assert moon["owlt_s"] < mars["owlt_s"]
        assert mars["autonomy_level"] > moon["autonomy_level"]
        assert mars["rtt_s"] == pytest.approx(2 * mars["owlt_s"], abs=0.2)

    def test_unknown_delay_target_is_rejected(self, client, headers):
        assert client.get("/multiplanetary/comms-delay/pluto", headers=headers).status_code == 422


class TestSpaceResources:
    def test_registry_contents(self, client, headers):
        body = client.get("/space-resources/technologies", headers=headers).json()

        assert body["count"] == 8
        assert {item["resource_type"] for item in body["technologies"]} == {
            "water",
            "oxygen",
            "metals",
            "construction_material",
            "propellant",
        }
        for item in body["technologies"]:
            assert 1 <= item["trl"] <= 9
            assert item["readiness"] in {"research", "development", "demonstration", "operational"}

    def test_filters_narrow_the_registry(self, client, headers):
        mars = client.get("/space-resources/technologies?target_body=mars", headers=headers).json()
        advanced = client.get("/space-resources/technologies?min_trl=5", headers=headers).json()

        assert [item["id"] for item in mars["technologies"]] == ["mars_moxygen"]
        assert {item["id"] for item in advanced["technologies"]} == {"mars_moxygen", "propellant_lox_lh2"}

    def test_technology_detail_exposes_dependencies(self, client, headers):
        body = client.get(
            "/space-resources/technologies/lunar_water_electrodialysis", headers=headers
        ).json()

        assert body["provenance"] == "simulated"
        assert body["dependency_chain"] == ["lunar_water_electrodialysis"]
        assert set(body["risk"]) == {"technical", "schedule", "cost", "reliability"}
        assert body["timeline_years"]["total"] == body["total_timeline_years"]

    def test_unknown_technology_is_a_404(self, client, headers):
        assert (
            client.get("/space-resources/technologies/no-such-thing", headers=headers).status_code == 404
        )

    def test_economics_prefers_in_situ_for_water(self, client, headers):
        body = client.get(
            "/space-resources/economics/water?mass_kg=250&destination=lunar", headers=headers
        ).json()

        assert body["in_situ_cost"] < body["earth_launch_cost"]
        assert body["savings"] == round(body["earth_launch_cost"] - body["in_situ_cost"], 2)
        assert 0 < body["savings_percent"] < 100
        assert any("not a market price" in line for line in body["model_limitations"])

    def test_unknown_resource_lists_what_exists(self, client, headers):
        response = client.get("/space-resources/economics/unobtainium", headers=headers)

        assert response.status_code == 404
        assert response.json()["details"]["known"] == [
            "construction_material",
            "metals",
            "oxygen",
            "propellant",
            "water",
        ]

    def test_yield_is_energy_limited_not_feedstock_limited(self, client, headers):
        small = client.post(
            "/space-resources/extraction",
            json={"process": "water_ice", "hours": 24.0, "feedstock_kg": 1000.0},
            headers=headers,
        ).json()
        huge = client.post(
            "/space-resources/extraction",
            json={"process": "water_ice", "hours": 24.0, "feedstock_kg": 100000.0},
            headers=headers,
        ).json()

        assert small["mass_produced_kg"] == huge["mass_produced_kg"]
        assert any("energy-limited" in line for line in small["model_limitations"])

    def test_thin_feedstock_becomes_the_binding_limit(self, client, headers):
        ample = client.post(
            "/space-resources/extraction",
            json={"process": "water_ice", "hours": 24.0, "feedstock_kg": 1000.0},
            headers=headers,
        ).json()
        scarce = client.post(
            "/space-resources/extraction",
            json={"process": "water_ice", "hours": 24.0, "feedstock_kg": 1.0},
            headers=headers,
        ).json()

        assert scarce["mass_produced_kg"] < ample["mass_produced_kg"]

    def test_more_power_more_yield_at_one_constant(self, client, headers):
        half = client.post(
            "/space-resources/extraction",
            json={"process": "water_ice", "hours": 24.0, "feedstock_kg": 0.0, "power_w": 80.0},
            headers=headers,
        ).json()
        double = client.post(
            "/space-resources/extraction",
            json={"process": "water_ice", "hours": 24.0, "feedstock_kg": 0.0, "power_w": 160.0},
            headers=headers,
        ).json()

        assert double["mass_produced_kg"] == pytest.approx(2 * half["mass_produced_kg"], rel=1e-3)
        assert double["energy_used_wh"] == 2 * half["energy_used_wh"]

    def test_overridden_efficiency_shows_up_in_specific_energy(self, client, headers):
        lean = client.post(
            "/space-resources/extraction",
            json={"process": "generic", "hours": 10.0, "feedstock_kg": 0.0, "efficiency": 0.9},
            headers=headers,
        ).json()

        assert lean["resource_type"] == "unknown"
        assert lean["yield_fraction"] == pytest.approx(0.9, rel=1e-3)

    def test_sintering_needs_feedstock(self, client, headers):
        empty = client.post(
            "/space-resources/extraction",
            json={"process": "construction_material", "hours": 10.0, "feedstock_kg": 0.0},
            headers=headers,
        ).json()
        loaded = client.post(
            "/space-resources/extraction",
            json={"process": "construction_material", "hours": 10.0, "feedstock_kg": 500.0},
            headers=headers,
        ).json()

        assert empty["mass_produced_kg"] == 0.0
        assert empty["specific_energy_kwh_per_kg"] is None
        assert loaded["mass_produced_kg"] == pytest.approx(500.0 * 0.85, rel=1e-6)
        assert any("sinterer" in line for line in loaded["model_limitations"])

    def test_waste_balance_is_against_the_extractable_fraction(self, client, headers):
        """Documented quirk: produced + waste is not the raw feedstock mass."""
        body = client.post(
            "/space-resources/extraction",
            json={"process": "water_ice", "hours": 1.0, "feedstock_kg": 1000.0},
            headers=headers,
        ).json()

        assert body["mass_produced_kg"] + body["mass_waste_kg"] < body["feedstock_kg"]
        assert any("does not equal" in line for line in body["model_limitations"])

    def test_sites_are_ranked_by_the_fixed_weighting(self, client, headers):
        body = client.post(
            "/space-resources/prospecting",
            json={
                "sites": [
                    {
                        "id": "poor",
                        "body": "lunar",
                        "resources": [{"resource_type": "water", "estimated_mass_kg": 1e3, "significance": "trace"}],
                        "solar_power_availability": 0.2,
                        "terrain_difficulty": 0.9,
                    },
                    {
                        "id": "rich",
                        "body": "lunar",
                        "resources": [{"resource_type": "water", "estimated_mass_kg": 5e6, "significance": "primary"}],
                        "solar_power_availability": 0.9,
                        "terrain_difficulty": 0.2,
                    },
                ]
            },
            headers=headers,
        ).json()

        assert [item["id"] for item in body["ranked"]] == ["rich", "poor"]
        assert body["ranked"][0]["value_score"] > body["ranked"][1]["value_score"]
        assert body["ranked"][0]["viability"][0]["significance"] == "primary"
        assert any("0.4 mass" in line for line in body["model_limitations"])

    def test_body_filter_limits_the_ranking(self, client, headers):
        body = client.post(
            "/space-resources/prospecting",
            json={
                "sites": [
                    {"id": "moon-site", "body": "lunar", "resources": [{"resource_type": "water", "estimated_mass_kg": 1e4}]},
                    {"id": "mars-site", "body": "mars", "resources": [{"resource_type": "water", "estimated_mass_kg": 1e4}]},
                ],
                "body": "mars",
            },
            headers=headers,
        ).json()

        assert [item["id"] for item in body["ranked"]] == ["mars-site"]

    def test_site_priority_is_a_closed_set(self, client, headers):
        assert (
            client.post(
                "/space-resources/prospecting",
                json={
                    "sites": [
                        {
                            "id": "s",
                            "body": "lunar",
                            "priority": "critical",
                            "resources": [{"resource_type": "water", "estimated_mass_kg": 1.0}],
                        }
                    ]
                },
                headers=headers,
            ).status_code
            == 422
        )

    def test_roadmap_phases_and_totals(self, client, headers):
        body = client.get("/space-resources/roadmap", headers=headers).json()

        assert len(body["phases"]) == 8
        assert body["total_milestones"] == len(body["milestones"])
        assert body["total_cost_usd"] > 0
        assert body["critical_path_milestones"] > 0
        for phase in body["phases"]:
            assert phase["end_year"] == pytest.approx(
                phase["start_year"] + phase["duration_years"], abs=1e-6
            )


class TestCapabilitiesListTheNewSurfaces:
    """The index has to point at the routes, not only at the engines."""

    @pytest.mark.parametrize(
        "subsystem,route_module",
        [
            ("spacecraft", "app.routes.spacecraft"),
            ("multiplanetary", "app.routes.multiplanetary"),
            ("space_resources", "app.routes.space_resources"),
            ("space_division", "app.routes.space_division"),
            ("mission_planning", "app.routes.mission_planning"),
        ],
    )
    def test_division_entry_documents_its_http_surface(self, client, subsystem, route_module):
        payload = client.get("/system/capabilities").json()
        entry = next(item for item in payload["subsystems"] if item["id"] == subsystem)

        assert route_module in entry["modules"]
