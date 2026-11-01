"""Tests for the grounded console assistant.

The point of these tests is the grounding contract, not prose: every reply
must be built from the caller's own rows, must not leak another account, must
not claim to have performed an action, and must stay honest when a backing
store is unavailable. The assistant is deterministic, so intents are asserted
exactly rather than by keyword soup.
"""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.models.alert import Alert
from app.models.analysis import AnalysisResult
from app.models.user import User
from app.queue import _InlineQueue, get_redis
from main import app

_ACCOUNT_SEQ = 0
AREA = {"latitude": -1.2921, "longitude": 36.8219, "radius_km": 2.0}


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _inline_analysis_queue(monkeypatch):
    """Create areas synchronously: CI's real Redis queue has no worker, so
    completion-dependent assertions would otherwise be about the queue, not
    the assistant."""
    queue = _InlineQueue()
    monkeypatch.setattr("app.queue.get_analysis_queue", lambda: queue)


@pytest.fixture(autouse=True)
def _clean_redis():
    redis = get_redis()
    prefixes = ("auth:*", "quota:*", "ratelimit:*", "assistant:*")

    def _wipe():
        for prefix in prefixes:
            for key in redis.keys(prefix):
                redis.delete(key)

    _wipe()
    yield
    _wipe()


def _account(client, password="correcthorsebatterystaple"):
    global _ACCOUNT_SEQ
    _ACCOUNT_SEQ += 1
    username = f"friday_user_{_ACCOUNT_SEQ}"
    response = client.post(
        "/auth/register",
        json={"email": f"{username}@test.com", "username": username, "password": password},
    )
    assert response.status_code in (200, 201), response.text
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        user.email_verified_at = datetime.now(UTC)
        db.commit()
    finally:
        db.close()
    token = client.post(
        "/auth/token", json={"username": username, "password": password}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, username


def _ask(client, auth, message):
    response = client.post("/assistant/ask", headers=auth, json={"message": message})
    assert response.status_code == 200, response.text
    return response.json()


def _create(client, auth, **overrides):
    payload = {
        "analysis_type": "vegetation_stress",
        "description": "plot",
        **AREA,
        **overrides,
    }
    response = client.post("/analysis/", headers=auth, json=payload)
    assert response.status_code == 200, response.text
    return response.json()


class TestAssistantContract:
    def test_requires_auth(self, client):
        response = client.post("/assistant/ask", json={"message": "overview"})
        assert response.status_code == 401

    def test_rejects_empty_message(self, client):
        auth, _ = _account(client)
        assert client.post("/assistant/ask", headers=auth, json={"message": ""}).status_code == 422

    def test_rate_limit_is_per_account(self, client, monkeypatch):
        auth, _ = _account(client)
        monkeypatch.setattr(
            "app.routes.assistant.get_settings",
            lambda: SimpleNamespace(ASSISTANT_RATE_LIMIT_PER_MINUTE=2),
        )
        assert client.post("/assistant/ask", headers=auth, json={"message": "hi"}).status_code == 200
        assert client.post("/assistant/ask", headers=auth, json={"message": "hi"}).status_code == 200
        limited = client.post("/assistant/ask", headers=auth, json={"message": "hi"})
        assert limited.status_code == 429
        assert limited.json()["code"] == "rate_limited"


class TestGroundedAnswers:
    def test_greeting_names_the_assistant_and_reads_the_account(self, client):
        auth, _ = _account(client)
        body = _ask(client, auth, "hey friday")
        assert body["intent"] == "greeting"
        assert "FRIDAY" in body["answer"]
        assert {fact["label"]: fact["value"] for fact in body["facts"]}["Areas"] == "0"
        assert body["suggestions"]
        assert body["generated_at"]

    def test_overview_counts_areas_and_labels_simulated_data(self, client):
        auth, _ = _account(client)
        _create(client, auth)
        _create(client, auth, analysis_type="flood_monitoring", description="delta")

        body = _ask(client, auth, "give me an overview")
        facts = {fact["label"]: fact["value"] for fact in body["facts"]}
        assert body["intent"] == "overview"
        assert facts["Areas"] == "2"
        assert facts["Simulated results"] == "2"
        assert facts["Real results"] == "0"
        assert "simulated" in body["answer"].lower()

    def test_quota_answer_matches_the_summary_endpoint(self, client):
        auth, _ = _account(client)
        _create(client, auth)
        _create(client, auth)

        summary = client.get("/analysis/summary", headers=auth).json()
        body = _ask(client, auth, "how many analyses do i have left today?")
        facts = {fact["label"]: fact["value"] for fact in body["facts"]}
        assert body["intent"] == "quota"
        assert facts["Used today"] == str(summary["quota_used_today"])
        assert facts["Remaining"] == str(summary["quota_remaining_today"])

    def test_provenance_answer_separates_real_from_simulated(self, client):
        auth, _ = _account(client)
        _create(client, auth)
        body = _ask(client, auth, "is my data real or simulated?")
        facts = {fact["label"]: fact["value"] for fact in body["facts"]}
        assert body["intent"] == "provenance"
        assert facts["Simulated"] == "1"
        assert "labelled" in body["answer"].lower()

    def test_areas_lists_the_caller_areas(self, client):
        auth, _ = _account(client)
        _create(client, auth, description="north paddock")
        body = _ask(client, auth, "list my areas")
        assert body["intent"] == "areas"
        assert "north paddock" in body["answer"]
        assert any(link["href"].startswith("/app/areas/") for link in body["links"])

    def test_named_area_detail_is_read_from_the_row(self, client):
        auth, _ = _account(client)
        area = _create(client, auth, description="north paddock")
        current = client.get(f"/analysis/{area['id']}", headers=auth).json()
        body = _ask(client, auth, "tell me about north paddock")
        facts = {fact["label"]: fact["value"] for fact in body["facts"]}
        assert body["intent"] == "area_detail"
        assert facts["Status"] == current["status"]
        assert facts["Radius"] == "2.00 km"
        assert any(link["href"] == f"/app/areas/{area['id']}" for link in body["links"])

    def test_area_detail_by_number(self, client):
        auth, _ = _account(client)
        area = _create(client, auth, description="delta")
        body = _ask(client, auth, f"area {area['id']}")
        assert body["intent"] == "area_detail"
        assert f"#{area['id']}" in body["answer"]

    def test_alerts_cite_unread_rows_only(self, client):
        auth, username = _account(client)
        area = _create(client, auth, description="river plot")
        baseline = client.get("/analysis/summary", headers=auth).json()["unread_alerts"]
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == username).first()
            result = (
                db.query(AnalysisResult)
                .filter(AnalysisResult.analysis_id == area["id"])
                .order_by(AnalysisResult.id.desc())
                .first()
            )
            db.add(
                Alert(
                    user_id=user.id,
                    analysis_result_id=result.id,
                    alert_type="critical",
                    title="River level rising",
                    description="test",
                    is_read=False,
                )
            )
            db.commit()
        finally:
            db.close()

        body = _ask(client, auth, "show my unread alerts")
        facts = {fact["label"]: fact["value"] for fact in body["facts"]}
        assert body["intent"] == "alerts"
        assert facts["Unread alerts"] == str(baseline + 1)
        assert body["answer"].startswith(f"{baseline + 1} unread")
        assert "River level rising" in body["answer"]
        assert "river plot" in body["answer"]
        assert int(facts["Critical"]) >= 1

    def test_flights_report_the_live_store(self, client):
        auth, _ = _account(client)
        flight_id = "friday-test-flight"
        ingest = client.post(
            f"/robotics/flights/{flight_id}/telemetry",
            headers=auth,
            json={"battery_percent": 64.0, "gps_accuracy_m": 1.2},
        )
        assert ingest.status_code == 200, ingest.text

        body = _ask(client, auth, "how is the fleet?")
        facts = {fact["label"]: fact["value"] for fact in body["facts"]}
        assert body["intent"] == "flights"
        assert flight_id in facts["Flights"]
        assert any(link["href"] == "/app/fleet" for link in body["links"])

    def test_flights_outage_is_reported_not_guessed(self, client, monkeypatch):
        auth, _ = _account(client)

        class _DownStore:
            def list_flights(self):
                raise RuntimeError("redis is down")

        monkeypatch.setattr("app.assistant.flight_store", _DownStore())
        body = _ask(client, auth, "how is the fleet?")
        assert body["intent"] == "flights"
        assert "couldn't reach" in body["answer"]
        assert {fact["label"]: fact["value"] for fact in body["facts"]}["Telemetry store"] == "unreachable"

    def test_insurance_is_described_as_estimates(self, client):
        auth, _ = _account(client)
        body = _ask(client, auth, "how do insurance payouts work?")
        assert body["intent"] == "insurance"
        assert "never settlements" in body["answer"]


class TestGroundingBoundaries:
    def test_another_accounts_area_is_not_described(self, client):
        owner, _ = _account(client)
        area = _create(client, owner, description="private north plot")
        intruder, _ = _account(client)

        body = _ask(client, intruder, f"area {area['id']}")
        assert body["intent"] == "area_detail"
        assert "couldn't find" in body["answer"]
        assert "private north plot" not in body["answer"]

    def test_another_accounts_counts_do_not_leak(self, client):
        owner, _ = _account(client)
        _create(client, owner)
        _create(client, owner)
        intruder, _ = _account(client)

        facts = {fact["label"]: fact["value"] for fact in _ask(client, intruder, "overview")["facts"]}
        assert facts["Areas"] == "0"
        assert facts["Simulated results"] == "0"

    def test_action_requests_are_refused_honestly(self, client):
        auth, _ = _account(client)
        body = _ask(client, auth, "delete all my areas and start a new scan")
        assert body["intent"] == "fallback"
        assert "read-only" in body["answer"]

    def test_unknown_questions_get_an_honest_scope(self, client):
        auth, _ = _account(client)
        body = _ask(client, auth, "what is the weather in paris tomorrow?")
        assert body["intent"] == "fallback"
        assert "can't read that" in body["answer"]
