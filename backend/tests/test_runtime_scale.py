"""Runtime scaling round: shared state, bounded reads and deployment knobs.

Covers the behaviour that makes more than one API process safe:

* the alert inbox is paged/scoped and the roll-up counts provenance in SQL,
* the production flight store is shared through Redis (exercised here against
  the in-memory Redis substitute, so the same code runs locally and in CI),
* rate limiting fails open when Redis is down instead of 500ing every request,
* large responses are compressed.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import SessionLocal, area_geometry
from app.models.alert import Alert
from app.models.analysis import Analysis, AnalysisResult, AnalysisType
from app.queue import _DemoRedis, get_redis
from app.robotics.flight import RedisFlightStore
from main import app

_SEQ = 0


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean_redis():
    redis = get_redis()
    prefixes = ("auth:*", "quota:*", "ratelimit:*")
    for prefix in prefixes:
        for key in redis.keys(prefix):
            redis.delete(key)
    yield
    for prefix in prefixes:
        for key in redis.keys(prefix):
            redis.delete(key)


def _headers(client) -> dict[str, str]:
    global _SEQ
    _SEQ += 1
    username = f"runtime_user_{_SEQ}"
    client.post(
        "/auth/register",
        json={
            "email": f"{username}@test.com",
            "username": username,
            "password": "correcthorsebatterystaple",
        },
    )
    token = client.post(
        "/auth/token",
        json={"username": username, "password": "correcthorsebatterystaple"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _user_id(headers: dict[str, str]) -> int:
    token = headers["Authorization"].split(" ", 1)[1]
    import jwt

    payload = jwt.decode(token, options={"verify_signature": False})
    return int(payload["sub"])


def _seed_analysis(db, user_id: int) -> Analysis:
    analysis = Analysis(
        user_id=user_id,
        analysis_type=AnalysisType.VEGETATION_STRESS,
        geometry=area_geometry("POLYGON((36 0, 37 0, 37 1, 36 0))"),
        latitude=0.0,
        longitude=36.0,
        radius_km=1.0,
        status="completed",
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


def _seed_result(db, analysis_id: int, metadata: str | None) -> AnalysisResult:
    result = AnalysisResult(
        analysis_id=analysis_id,
        severity_score=0.5,
        confidence=0.9,
        finding="seed",
        metadata_json=metadata,
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return result


def _seed_alert(
    db,
    user_id: int,
    result_id: int,
    *,
    is_read: bool = False,
    created_at: datetime | None = None,
    title: str = "alert",
) -> Alert:
    alert = Alert(
        user_id=user_id,
        analysis_result_id=result_id,
        alert_type="warning",
        title=title,
        description="seeded",
        is_read=is_read,
        created_at=created_at or datetime.now(UTC),
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


class TestPagedAlertInbox:
    def test_requires_auth(self, client):
        assert client.get("/alerts").status_code == 401

    def test_pages_newest_first_with_a_real_total(self, client):
        headers = _headers(client)
        user_id = _user_id(headers)
        db = SessionLocal()
        try:
            analysis = _seed_analysis(db, user_id)
            result = _seed_result(db, analysis.id, '{"provenance": "real"}')
            now = datetime.now(UTC)
            for index in range(3):
                _seed_alert(
                    db,
                    user_id,
                    result.id,
                    title=f"alert-{index}",
                    created_at=now - timedelta(minutes=index),
                )
        finally:
            db.close()

        first = client.get("/alerts?limit=2", headers=headers).json()
        assert first["total"] == 3
        assert first["skip"] == 0
        assert first["limit"] == 2
        assert [item["title"] for item in first["items"]] == ["alert-0", "alert-1"]

        second = client.get("/alerts?skip=2&limit=2", headers=headers).json()
        assert second["total"] == 3
        assert [item["title"] for item in second["items"]] == ["alert-2"]

    def test_scopes_to_one_analysis(self, client):
        headers = _headers(client)
        user_id = _user_id(headers)
        db = SessionLocal()
        try:
            first = _seed_analysis(db, user_id)
            second = _seed_analysis(db, user_id)
            first_result = _seed_result(db, first.id, None)
            second_result = _seed_result(db, second.id, None)
            _seed_alert(db, user_id, first_result.id, title="first")
            _seed_alert(db, user_id, second_result.id, title="second")
            # Capture ids before close(): commit expires attributes, so
            # reading them afterwards requires a live session.
            first_id = first.id
        finally:
            db.close()

        body = client.get(f"/alerts?analysis_id={first_id}&limit=200", headers=headers).json()
        assert body["total"] == 1
        assert [item["title"] for item in body["items"]] == ["first"]

    def test_unread_filter_and_acknowledge(self, client):
        headers = _headers(client)
        user_id = _user_id(headers)
        db = SessionLocal()
        try:
            analysis = _seed_analysis(db, user_id)
            result = _seed_result(db, analysis.id, None)
            _seed_alert(db, user_id, result.id, title="unread")
            read = _seed_alert(db, user_id, result.id, title="read", is_read=True)
        finally:
            db.close()

        unread = client.get("/alerts?unread_only=true", headers=headers).json()
        assert unread["total"] == 1
        assert unread["items"][0]["title"] == "unread"

        ack = client.post(f"/alerts/{read.id}/acknowledge", headers=headers)
        assert ack.status_code == 200
        assert ack.json()["is_read"] is True
        assert ack.json()["acknowledged_at"] is not None


class TestProvenanceRollUp:
    def test_counts_real_simulated_and_unknown_in_one_query(self, client):
        headers = _headers(client)
        user_id = _user_id(headers)
        db = SessionLocal()
        try:
            analysis = _seed_analysis(db, user_id)
            _seed_result(db, analysis.id, '{"provenance": "real", "simulated": false}')
            _seed_result(db, analysis.id, '{"provenance": "simulated", "simulated": true}')
            _seed_result(db, analysis.id, '{"provenance": "simulated", "simulated": true}')
            _seed_result(db, analysis.id, '{"simulated": false}')
            _seed_result(db, analysis.id, '{"simulated": true}')
            _seed_result(db, analysis.id, '{"provenance": ""}')
            _seed_result(db, analysis.id, "not-json")
            _seed_result(db, analysis.id, None)
        finally:
            db.close()

        body = client.get("/analysis/summary", headers=headers).json()
        assert body["provenance"] == {
            "real": 2,
            "simulated": 3,
            "unknown": 3,
        }
        assert body["completed_with_findings"] == 8


class TestSharedFlightStore:
    def test_parity_with_the_in_memory_store(self, monkeypatch):
        monkeypatch.setattr(get_settings(), "ROBOTICS_FLIGHT_RETENTION_FRAMES", 3)
        store = RedisFlightStore(redis=_DemoRedis())

        for index in range(5):
            store.ingest(
                "flight-a",
                {"battery_percent": 90.0 - index, "sequence": index},
            )

        summary = store.summary("flight-a")
        assert summary is not None
        assert summary["flight_id"] == "flight-a"
        assert summary["telemetry_count"] == 3
        assert summary["flight_health"]["samples"] == 3
        assert summary["flight_health"]["status"] in {"healthy", "caution", "critical"}

        frames = store.get_telemetry("flight-a", limit=2)
        assert [frame["sequence"] for frame in frames] == [3, 4]
        assert all(frame["level"] == "info" for frame in frames)

        assert [f["flight_id"] for f in store.list_flights()] == ["flight-a"]
        assert store.health("missing") is None
        assert store.get_telemetry("missing") == []

        store.clear()
        assert store.get("flight-a") is None
        assert store.list_flights() == []

    def test_started_but_empty_flight_reports_no_telemetry(self):
        store = RedisFlightStore(redis=_DemoRedis())
        store.start("empty-flight")

        summary = store.summary("empty-flight")
        assert summary is not None
        assert summary["telemetry_count"] == 0
        assert summary["flight_health"]["status"] == "no_telemetry"

    def test_fault_frames_lower_health(self):
        store = RedisFlightStore(redis=_DemoRedis())
        store.ingest("faulty", {"battery_percent": 80.0})
        store.ingest("faulty", {"battery_percent": 10.0, "faults": ["motor"]})

        health = store.health("faulty")
        assert health is not None
        assert health["fault_count"] == 1
        assert health["health_score"] < 1.0
        assert health["status"] in {"caution", "critical"}


class TestRuntimeResilience:
    def test_rate_limiter_fails_open_when_redis_is_down(self, monkeypatch):
        class _DownRedis:
            def pipeline(self, transaction=True):
                raise RuntimeError("redis is down")

        from app.rate_limiter import is_rate_limited

        monkeypatch.setattr("app.rate_limiter.get_redis", lambda: _DownRedis())
        assert is_rate_limited("ratelimit:down", limit=1, window_seconds=60) is False

    def test_large_responses_are_gzipped(self, client):
        response = client.get(
            "/system/capabilities", headers={"Accept-Encoding": "gzip"}
        )
        assert response.status_code == 200
        assert response.headers.get("content-encoding") == "gzip"

    def test_preflight_allows_both_loopback_spellings(self, client):
        # localhost and 127.0.0.1 are different origins to a browser, and the
        # dev server is reachable on both -- a preflight from either must pass.
        for origin in ("http://localhost:5173", "http://127.0.0.1:5173"):
            response = client.options(
                "/auth/token",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "POST",
                },
            )
            assert response.status_code == 200
            assert response.headers["access-control-allow-origin"] == origin
