"""Tests for continuous monitoring (AURORA scale milestone).

Covers the two new endpoints -- PATCH /analysis/{id}/monitor (set/clear a
re-check cadence) and POST /analysis/{id}/re-run (manual re-check) -- plus the
monitoring scheduler itself (app.monitoring): due areas are launched once,
active runs are not re-launched, and the Redis lock prevents a second replica
from double-firing the same check.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.models.analysis import Analysis, AnalysisResult
from app.monitoring import MonitoringScheduler
from app.queue import get_redis
from main import app

_ACCOUNT_SEQ = 0


def _register_and_login(client, password="correcthorsebatterystaple"):
    global _ACCOUNT_SEQ
    _ACCOUNT_SEQ += 1
    username = f"monitor_user_{_ACCOUNT_SEQ}"
    email = f"{username}@test.com"
    client.post(
        "/auth/register",
        json={"email": email, "username": username, "password": password},
    )
    token = client.post(
        "/auth/token", json={"username": username, "password": password}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_area(client, headers, description="field plot"):
    response = client.post(
        "/analysis/",
        headers=headers,
        json={
            "analysis_type": "vegetation_stress",
            "description": description,
            "latitude": -1.2921,
            "longitude": 36.8219,
            "radius_km": 5.0,
        },
    )
    assert response.status_code == 200, response.text
    created_id = response.json()["id"]
    # Re-fetch so we see the post-enqueue status (the response body is built
    # before the inline queue runs in demo mode).
    fetched = client.get(f"/analysis/{created_id}", headers=headers)
    assert fetched.status_code == 200
    return fetched.json()


def _result_count(analysis_id: int) -> int:
    db = SessionLocal()
    try:
        return (
            db.query(AnalysisResult)
            .filter(AnalysisResult.analysis_id == analysis_id)
            .count()
        )
    finally:
        db.close()


def _set_next_check(analysis_id: int, minutes_ago: int) -> None:
    db = SessionLocal()
    try:
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        analysis.next_check_at = datetime.now(UTC) - timedelta(minutes=minutes_ago)
        db.commit()
    finally:
        db.close()


def _set_status(analysis_id: int, status: str) -> None:
    db = SessionLocal()
    try:
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        analysis.status = status
        db.commit()
    finally:
        db.close()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean_state():
    redis = get_redis()
    keys = redis.keys("auth:*") + redis.keys("quota:*") + redis.keys("ratelimit:*") + redis.keys("monitor:*")
    if keys:
        redis.delete(*keys)
    yield
    keys = redis.keys("auth:*") + redis.keys("quota:*") + redis.keys("ratelimit:*") + redis.keys("monitor:*")
    if keys:
        redis.delete(*keys)


class TestSetMonitoring:
    def test_enabling_schedules_first_check(self, client):
        headers = _register_and_login(client)
        area = _create_area(client, headers)
        assert area["monitor_interval_minutes"] is None
        assert area["next_check_at"] is None

        updated = client.patch(
            f"/analysis/{area['id']}/monitor",
            headers=headers,
            json={"monitor_interval_minutes": 1440},
        )
        assert updated.status_code == 200, updated.text
        body = updated.json()
        assert body["monitor_interval_minutes"] == 1440
        assert body["next_check_at"] is not None

        # The persisted area reports the same schedule.
        fetched = client.get(f"/analysis/{area['id']}", headers=headers).json()
        assert fetched["monitor_interval_minutes"] == 1440
        assert fetched["next_check_at"] is not None

    def test_clearing_monitoring_stops_scheduling(self, client):
        headers = _register_and_login(client)
        area = _create_area(client, headers)
        client.patch(
            f"/analysis/{area['id']}/monitor",
            headers=headers,
            json={"monitor_interval_minutes": 60},
        )
        cleared = client.patch(
            f"/analysis/{area['id']}/monitor",
            headers=headers,
            json={"monitor_interval_minutes": None},
        )
        assert cleared.status_code == 200, cleared.text
        assert cleared.json()["monitor_interval_minutes"] is None
        assert cleared.json()["next_check_at"] is None
        db = SessionLocal()
        try:
            persisted = db.query(Analysis).filter(Analysis.id == area["id"]).first()
            assert persisted.monitor_interval_minutes is None
            assert persisted.next_check_at is None
        finally:
            db.close()

    def test_interval_below_the_floor_is_rejected(self, client):
        headers = _register_and_login(client)
        area = _create_area(client, headers)
        response = client.patch(
            f"/analysis/{area['id']}/monitor",
            headers=headers,
            json={"monitor_interval_minutes": 5},
        )
        assert response.status_code == 422

    def test_monitor_patch_is_scoped_to_the_owner(self, client):
        owner = _register_and_login(client)
        intruder = _register_and_login(client)
        area = _create_area(client, owner)
        response = client.patch(
            f"/analysis/{area['id']}/monitor",
            headers=intruder,
            json={"monitor_interval_minutes": 60},
        )
        assert response.status_code == 404


class TestRerun:
    def test_rerun_completes_a_new_result(self, client):
        headers = _register_and_login(client)
        area = _create_area(client, headers)
        assert area["status"] == "completed"
        assert _result_count(area["id"]) == 1

        rerun = client.post(f"/analysis/{area['id']}/re-run", headers=headers)
        assert rerun.status_code == 200, rerun.text
        assert rerun.json()["status"] == "completed"
        assert _result_count(area["id"]) == 2

    def test_rerun_refuses_while_a_run_is_active(self, client):
        headers = _register_and_login(client)
        area = _create_area(client, headers)
        _set_status(area["id"], "pending")
        response = client.post(f"/analysis/{area['id']}/re-run", headers=headers)
        assert response.status_code == 409

    def test_rerun_is_scoped_to_the_owner(self, client):
        owner = _register_and_login(client)
        intruder = _register_and_login(client)
        area = _create_area(client, owner)
        response = client.post(f"/analysis/{area['id']}/re-run", headers=intruder)
        assert response.status_code == 404


class TestMonitoringScheduler:
    def _scheduler(self) -> MonitoringScheduler:
        return MonitoringScheduler()

    def test_tick_fires_due_checks_once_and_advances_the_schedule(self, client):
        headers = _register_and_login(client)
        area = _create_area(client, headers)
        client.patch(
            f"/analysis/{area['id']}/monitor",
            headers=headers,
            json={"monitor_interval_minutes": 60},
        )
        _set_next_check(area["id"], minutes_ago=1)

        scheduler = self._scheduler()
        scheduler._tick()
        scheduler._tick()  # second tick: lock held, nothing due anyway

        assert _result_count(area["id"]) == 2
        db = SessionLocal()
        try:
            analysis = db.query(Analysis).filter(Analysis.id == area["id"]).first()
            assert analysis.status == "completed"
            assert analysis.next_check_at is not None
            assert analysis.next_check_at > datetime.now(UTC).replace(tzinfo=None)
        finally:
            db.close()

    def test_tick_never_launches_a_pending_or_locked_check(self, client):
        headers = _register_and_login(client)
        area = _create_area(client, headers)
        client.patch(
            f"/analysis/{area['id']}/monitor",
            headers=headers,
            json={"monitor_interval_minutes": 60},
        )

        # A pending run (e.g. another process already started it) must not be
        # re-fired even if its next_check_at has passed.
        _set_next_check(area["id"], minutes_ago=1)
        _set_status(area["id"], "pending")
        redis = get_redis()
        redis.delete(f"monitor:{area['id']}")
        self._scheduler()._tick()
        assert _result_count(area["id"]) == 1

        # A completed run whose check came due again but whose lock is still
        # held (already claimed by another replica) must not double-fire.
        redis.set(f"monitor:{area['id']}", "1", ex=300)
        _set_status(area["id"], "completed")
        _set_next_check(area["id"], minutes_ago=1)
        self._scheduler()._tick()
        assert _result_count(area["id"]) == 1

        # Once the lock expires (simulated by clearing it), the same area is
        # checked again.
        redis.delete(f"monitor:{area['id']}")
        self._scheduler()._tick()
        assert _result_count(area["id"]) == 2
