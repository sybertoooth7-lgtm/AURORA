"""Tests for the field-boundary crop analysis endpoint (POST /crop/analyze).

Local runs use the deterministic demo provider, so the happy path asserts
the honest simulated provenance and the persisted analysis/result rows.
A separate test injects a fake real-sensor provider to verify the real-data
path reports provenance="real" end to end. Boundary validation is exercised
against the geo-reasoning the endpoint depends on.
"""

import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.models.analysis import Analysis, AnalysisResult
from app.models.user import User
from app.queue import get_redis
from app.routes.crop import _survey_area
from app.satellite.providers import SatelliteObservation
from main import app

_ACCOUNT_SEQ = 0


def _boundary(lon=36.8219, lat=-1.2921, span=0.01):
    """Closed GeoJSON square ring around a point."""
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [lon - span, lat - span],
                [lon + span, lat - span],
                [lon + span, lat + span],
                [lon - span, lat + span],
                [lon - span, lat - span],
            ]
        ],
    }


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean_redis():
    redis = get_redis()
    for key in redis.keys("auth:*") + redis.keys("quota:*") + redis.keys("ratelimit:*"):
        redis.delete(key)
    yield
    for key in redis.keys("auth:*") + redis.keys("quota:*") + redis.keys("ratelimit:*"):
        redis.delete(key)


def _register_and_login(client, password="correcthorsebatterystaple"):
    global _ACCOUNT_SEQ
    _ACCOUNT_SEQ += 1
    username = f"crop_user_{_ACCOUNT_SEQ}"
    email = f"{username}@test.com"
    client.post(
        "/auth/register",
        json={"email": email, "username": username, "password": password},
    )
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        assert user is not None
        user.email_verified_at = datetime.now(UTC)
        db.commit()
    finally:
        db.close()
    token = client.post(
        "/auth/token", json={"username": username, "password": password}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestSurveyAreaMath:
    def test_centroid_and_radius_from_square(self):
        lon, lat, radius_km, wkt = _survey_area(_boundary()["coordinates"])
        assert lon == pytest.approx(36.8219, abs=0.02)
        assert lat == pytest.approx(-1.2921, abs=0.02)
        assert 0.5 < radius_km < 5.0
        assert wkt.startswith("POLYGON((")
        assert wkt.endswith("))")

    def test_zero_area_polygon_rejected(self):
        coords = [[[0.0, 0.0], [1.0, 0.0], [2.0, 0.0], [0.0, 0.0]]]
        with pytest.raises(Exception) as excinfo:
            _survey_area(coords)
        assert excinfo.value.status_code == 422


class TestCropAnalysisApi:
    def test_requires_auth(self, client):
        response = client.post("/crop/analyze", json={"field_boundary": _boundary()})
        assert response.status_code == 401

    def test_requires_verified_email(self, client):
        client.post(
            "/auth/register",
            json={
                "email": "crop_unverified@test.com",
                "username": "crop_unverified",
                "password": "correcthorsebatterystaple",
            },
        )
        token = client.post(
            "/auth/token",
            json={"username": "crop_unverified", "password": "correcthorsebatterystaple"},
        ).json()["access_token"]
        response = client.post(
            "/crop/analyze",
            headers={"Authorization": f"Bearer {token}"},
            json={"field_boundary": _boundary()},
        )
        assert response.status_code == 403
        assert response.json()["code"] == "email_unverified"

    def test_full_report_over_simulated_observation(self, client):
        auth = _register_and_login(client)
        response = client.post(
            "/crop/analyze",
            headers=auth,
            json={
                "field_boundary": _boundary(),
                "description": "maize plot, Kisumu",
                "use_history": True,
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()

        # Simulated provider -> honest provenance everywhere.
        assert body["provenance"] == "simulated"
        assert body["observation"]["simulated"] is True
        assert body["observation"]["source"] == "demo"
        assert body["ndvi"] is not None
        assert -1.0 <= body["ndvi"] <= 1.0
        assert body["condition"] in {"healthy", "stressed", "critical"}
        assert 0.0 <= body["confidence"] <= 1.0
        assert body["analysis_id"] > 0

        # Report carries the observation, condition, and provenance lines.
        assert any(line.startswith("NDVI") for line in body["report"])
        assert any("Provenance: simulated" in line for line in body["report"])
        assert any(f"Crop condition: {body['condition']}" in line for line in body["report"])

        # The run was persisted as a completed vegetation analysis.
        db = SessionLocal()
        try:
            analysis = db.query(Analysis).filter(Analysis.id == body["analysis_id"]).first()
            assert analysis is not None
            assert analysis.status == "completed"
            assert analysis.analysis_type.value == "vegetation_stress"
            assert analysis.description == "maize plot, Kisumu"
            assert analysis.latitude == pytest.approx(body["latitude"], abs=0.02)
            row = db.query(AnalysisResult).filter(AnalysisResult.analysis_id == analysis.id).first()
            assert row is not None
            metadata = json.loads(row.metadata_json)
            assert metadata["provenance"] == "simulated"
            assert metadata["source"] == "demo"
        finally:
            db.close()

    def test_real_provider_path_reports_real_provenance(self, client, monkeypatch):
        class _FakeRealProvider:
            def fetch_latest(self, latitude, longitude, radius_km):
                return SatelliteObservation(
                    source="sentinel-2-l2a",
                    image_id="S2A_FAKE_20260930",
                    acquired_at=datetime(2026, 9, 30, 9, 30, tzinfo=UTC),
                    cloud_coverage=0.04,
                    resolution_m=10.0,
                    ndvi=0.62,
                    change_score=0.12,
                )

            def fetch_history(self, latitude, longitude, radius_km, limit=10):
                return []

        monkeypatch.setattr(
            "app.routes.ai.get_satellite_provider", lambda: _FakeRealProvider()
        )

        auth = _register_and_login(client)
        response = client.post(
            "/crop/analyze",
            headers=auth,
            json={"field_boundary": _boundary()},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["provenance"] == "real"
        assert body["observation"]["simulated"] is False
        assert body["observation"]["source"] == "sentinel-2-l2a"
        assert body["observation"]["image_id"] == "S2A_FAKE_20260930"

        db = SessionLocal()
        try:
            row = (
                db.query(AnalysisResult)
                .filter(AnalysisResult.analysis_id == body["analysis_id"])
                .first()
            )
            metadata = json.loads(row.metadata_json)
            assert metadata["provenance"] == "real"
            assert metadata["source"] == "sentinel-2-l2a"
            assert metadata["image_id"] == "S2A_FAKE_20260930"
        finally:
            db.close()


class TestFieldBoundaryValidation:
    def _post(self, client, boundary):
        auth = _register_and_login(client)
        return client.post(
            "/crop/analyze", headers=auth, json={"field_boundary": boundary}
        )

    def test_unclosed_ring_rejected(self, client):
        coords = _boundary()
        coords["coordinates"][0].pop()  # drop the closing duplicate
        response = self._post(client, coords)
        assert response.status_code == 422

    def test_too_few_positions_rejected(self, client):
        coords = {
            "type": "Polygon",
            "coordinates": [[[0.0, 0.0], [1.0, 0.0], [0.0, 0.0]]],
        }
        response = self._post(client, coords)
        assert response.status_code == 422

    def test_out_of_range_coordinate_rejected(self, client):
        coords = {
            "type": "Polygon",
            "coordinates": [[[0.0, 0.0], [200.0, 0.0], [1.0, 1.0], [0.0, 0.0]]],
        }
        response = self._post(client, coords)
        assert response.status_code == 422

    def test_interior_holes_rejected(self, client):
        coords = {
            "type": "Polygon",
            "coordinates": [
                _boundary()["coordinates"][0],
                _boundary()["coordinates"][0],
            ]
        }
        response = self._post(client, coords)
        assert response.status_code == 422

    def test_non_polygon_type_rejected(self, client):
        response = self._post(client, {"type": "Point", "coordinates": [0.0, 0.0]})
        assert response.status_code == 422

    def test_collinear_zero_area_rejected(self, client):
        coords = {
            "type": "Polygon",
            "coordinates": [[[0.0, 0.0], [1.0, 0.0], [2.0, 0.0], [0.0, 0.0]]],
        }
        response = self._post(client, coords)
        assert response.status_code == 422
