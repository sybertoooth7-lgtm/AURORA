"""Tests for the platform-wide system endpoints.

GET /system/capabilities needs no auth and no DB, so it is exercised
end-to-end through the ASGI app next to the public /ai/pipelines route.
"""

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_capabilities_endpoint_public(client):
    response = client.get("/system/capabilities")
    assert response.status_code == 200


def test_capabilities_lists_platform_and_version(client):
    payload = client.get("/system/capabilities").json()
    assert payload["platform"] == "AURORA"
    assert payload["version"] == get_settings().APP_VERSION


def test_capabilities_lists_all_subsystems(client):
    payload = client.get("/system/capabilities").json()
    subsystem_ids = {entry["id"] for entry in payload["subsystems"]}
    assert subsystem_ids == {
        "satellite",
        "ai",
        "insurance",
        "robotics_field_services",
        "onboarding",
        "robotics",
        "spacecraft",
        "multiplanetary",
        "space_resources",
    }


def test_capabilities_reports_ai_pipelines(client):
    payload = client.get("/system/capabilities").json()
    assert isinstance(payload["ai_pipelines"], list)
    handles = {h for p in payload["ai_pipelines"] for h in p["handles"]}
    assert "vegetation_stress" in handles
    assert "wildfire_risk" in handles
    assert "flood_monitoring" in handles
    assert "insurance_index" in handles
    assert "robotics_inspection" in handles


def test_capabilities_reports_satellite_sources(client):
    payload = client.get("/system/capabilities").json()
    source_ids = {s["id"] for s in payload["satellite_sources"]}
    assert "sentinel-2-l2a" in source_ids
    assert all(s["is_real"] for s in payload["satellite_sources"])


def test_health_version_matches_app_version(client):
    health = client.get("/health/").json()
    root = client.get("/").json()
    assert health["version"] == get_settings().APP_VERSION
    assert root["version"] == health["version"]


def test_root_mentions_capabilities(client):
    payload = client.get("/").json()
    assert payload["capabilities"] == "/system/capabilities"
