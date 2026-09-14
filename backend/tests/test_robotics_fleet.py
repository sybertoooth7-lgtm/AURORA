"""Fleet dashboard tests: flight listing, per-flight telemetry (capped by
``limit``), the ``POST /robotics/simulate`` spawner with honest
``is_simulated`` labelling, and 404 semantics for unknown flights.

The ``FlightStore`` is a per-process singleton shared across every
flight/telemetry/simulate test module, so this module clears it before each
test to stay order-independent.
"""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.models.user import User
from app.queue import get_redis
from app.robotics.flight import flight_store
from main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean_flight_store():
    flight_store.clear()
    yield
    flight_store.clear()


@pytest.fixture(autouse=True)
def _clean_redis():
    redis = get_redis()
    for key in redis.keys("auth:*") + redis.keys("quota:*"):
        redis.delete(key)
    yield
    for key in redis.keys("auth:*") + redis.keys("quota:*"):
        redis.delete(key)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    from app.queue import get_redis

    def _clear():
        redis = get_redis()
        keys = redis.keys("ratelimit:*")
        if keys:
            redis.delete(*keys)

    _clear()
    yield
    _clear()


_SEQ = 0


def _register(client, *, verified: bool = True):
    global _SEQ
    _SEQ += 1
    username = f"fleet_user_{_SEQ}"
    email = f"{username}@test.com"
    client.post("/auth/register", json={"email": email, "username": username, "password": "testpass123"})
    if verified:
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == username).first()
            user.email_verified_at = datetime.now(UTC)
            db.commit()
        finally:
            db.close()
    token = client.post(
        "/auth/token", json={"username": username, "password": "testpass123"}
    ).json()["access_token"]
    return username, {"Authorization": f"Bearer {token}"}


class TestFleetDashboard:
    def test_ingested_flight_appears_in_list_with_telemetry_count(self, client):
        _, headers = _register(client)
        client.post(
            "/robotics/flights/test-flight-1/telemetry",
            headers=headers,
            json={"battery_percent": 90.0, "sequence": 0},
        )
        client.post(
            "/robotics/flights/test-flight-1/telemetry",
            headers=headers,
            json={"battery_percent": 85.0, "sequence": 1},
        )

        resp = client.get("/robotics/flights", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1
        our_flight = next(f for f in body["flights"] if f["flight_id"] == "test-flight-1")
        assert our_flight["telemetry_count"] == 2
        assert 0.0 < our_flight["flight_health"]["health_score"] <= 1.0

    def test_telemetry_limit_is_respected(self, client):
        _, headers = _register(client)
        for i in range(30):
            client.post(
                "/robotics/flights/limit-flight/telemetry",
                headers=headers,
                json={"battery_percent": 80.0 - i, "sequence": i},
            )

        full = client.get("/robotics/flights/limit-flight/telemetry", headers=headers)
        assert full.status_code == 200
        assert len(full.json()) == 30

        capped = client.get("/robotics/flights/limit-flight/telemetry?limit=5", headers=headers)
        assert capped.status_code == 200
        frames = capped.json()
        assert len(frames) == 5
        # Most-recent kept (arrival order preserved), so the sequence numbers
        # are the last five.
        sequences = [f["sequence"] for f in frames]
        assert sequences == list(range(25, 30))
        for frame in frames:
            assert frame["is_simulated"] is False

    def test_simulate_spawn_is_honestly_labelled(self, client):
        _, headers = _register(client)
        sim = client.post(
            "/robotics/simulate",
            headers=headers,
            json={"latitude": 31.23, "longitude": 121.47, "radius_km": 10.0, "num_frames": 10},
        )
        assert sim.status_code == 201, sim.text
        body = sim.json()
        assert body["flight_id"].startswith("sim-")
        assert body["telemetry_count"] == 10
        assert 0.0 < body["flight_health"]["health_score"] <= 1.0

        frames = client.get(
            f"/robotics/flights/{body['flight_id']}/telemetry",
            headers=headers,
        ).json()
        assert len(frames) == 10
        assert all(f["is_simulated"] for f in frames)
        # Battery drains over the survey path.
        assert frames[0]["battery_percent"] > frames[-1]["battery_percent"]

    def test_unverified_account_cannot_spawn_simulated_flight(self, client):
        _, headers = _register(client, verified=False)
        sim = client.post(
            "/robotics/simulate",
            headers=headers,
            json={"latitude": 31.23, "longitude": 121.47, "radius_km": 10.0, "num_frames": 8},
        )
        assert sim.status_code == 403
        assert sim.json()["code"] == "email_unverified"

    def test_unknown_flight_telemetry_is_404(self, client):
        _, headers = _register(client)
        resp = client.get("/robotics/flights/no-such-id/telemetry", headers=headers)
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Flight not found"

    def test_simulate_default_frames(self, client):
        _, headers = _register(client)
        sim = client.post(
            "/robotics/simulate",
            headers=headers,
            json={"latitude": 0, "longitude": 0, "radius_km": 1.0},
        )
        assert sim.status_code == 201
        assert sim.json()["telemetry_count"] == 20
