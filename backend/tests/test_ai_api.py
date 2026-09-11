"""Tests for the /ai API surface that don't require a database.

GET /ai/pipelines needs no auth and no DB, so it is exercised end-to-end
through the ASGI app. Inference/model routes require Postgres+Redis, so
their logic is covered unit-level instead (see test_ai_pipelines.py and the
repository tests below).
"""

import pytest
from fastapi.testclient import TestClient

from app.ai.repository import ModelValidationError, VALID_STATUSES, canonical_metrics
from main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_pipelines_endpoint_lists_all_workspace_pipelines(client):
    response = client.get("/ai/pipelines")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)


def test_each_pipeline_describes_handles_and_model(client):
    payload = client.get("/ai/pipelines").json()
    handles = {handle for entry in payload for handle in entry["handles"]}
    for expected in (
        "vegetation_stress",
        "land_change",
        "infrastructure_change",
        "climate_impact",
        "anomaly_detection",
    ):
        assert expected in handles
    model_kinds = {entry["model"]["kind"] for entry in payload}
    assert model_kinds <= {"prototype", "production"}


def test_pipelines_endpoint_is_public(client):
    # No Authorization header and still 200 -> public registry listing.
    response = client.get("/ai/pipelines")
    assert response.status_code == 200


def test_root_endpoint_mentions_ai():
    with TestClient(app) as client:
        payload = client.get("/").json()
    assert payload["ai"] == "/ai/pipelines"


class TestModelRepositoryValidation:
    def test_valid_statuses_are_whitelisted(self):
        assert VALID_STATUSES == {"prototype", "production", "archived"}

    def test_canonical_metrics_is_stable_json(self):
        assert canonical_metrics({"f1": 0.8, "a": 1}) == '{"a": 1, "f1": 0.8}'
        assert canonical_metrics(None) is None

    def test_invalid_status_rejected(self):
        assert "production" in VALID_STATUSES
        with pytest.raises(ModelValidationError):
            raise ModelValidationError("nope")