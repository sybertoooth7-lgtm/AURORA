"""Tests for email-verification enforcement.

A new account is created unverified, and until it confirms its email it may
browse read-only surfaces and finish the verification flow, but every
capability-gated endpoint (analyses, AI inference, insurance trigger checks,
robotics inspections, guided first analysis) returns 403 ``email_unverified``.
The verification link/resend/confirm mechanism is exercised end to end.
"""

import re

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.models.user import User
from app.queue import get_redis
from main import app

_AREA = {"latitude": -1.2921, "longitude": 36.8219, "radius_km": 5.0}


@pytest.fixture
def client():
    return TestClient(app)


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


def _register_and_login(client, username, email=None, password="testpassword123"):
    email = email or f"{username}@test.com"
    # Fresh caplog-based registrations can't capture the token, so tests that
    # need the token call this helper; verification state is set by the
    # create_all grants helper where required.
    client.post(
        "/auth/register",
        json={"email": email, "username": username, "password": password},
    )
    token = client.post(
        "/auth/token", json={"username": username, "password": password}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _extract_verification_token(caplog) -> str:
    for record in caplog.records:
        match = re.search(r"verify-email\?token=([\w-]+)", record.getMessage())
        if match:
            return match.group(1)
    raise AssertionError("No verification link found in logs")


def _mark_verified(username: str) -> None:
    from datetime import UTC, datetime

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        assert user is not None
        user.email_verified_at = datetime.now(UTC)
        db.commit()
    finally:
        db.close()


_GATED_ENDPOINTS = [
    ("/analysis/", {"analysis_type": "vegetation_stress", "description": "x", **_AREA}),
    ("/ai/infer", {"analysis_type": "vegetation_stress", "use_history": False, **_AREA}),
    ("/insurance/trigger-check", {"sum_insured_usd": 100000, "use_history": False, **_AREA}),
    ("/robotics/inspect", {"use_history": False, **_AREA}),
    ("/onboarding/first-analysis", {"analysis_type": "vegetation_stress", "use_history": False, **_AREA}),
]


def test_new_account_is_unverified_but_can_browse(client, caplog):
    with caplog.at_level("INFO"):
        register_resp = client.post(
            "/auth/register",
            json={"email": "unverified@test.com", "username": "unverifieduser", "password": "testpassword123"},
        )
    assert register_resp.json()["email_verified"] is False

    # A verification email was sent automatically on registration.
    _extract_verification_token(caplog)

    auth = _register_and_login(client, "unverifieduser", email="unverified@test.com")

    # Verification is enforced: identity is confirmed, reads stay open...
    me = client.get("/auth/me", headers=auth)
    assert me.status_code == 200
    assert me.json()["email_verified"] is False
    assert client.get("/analysis/", headers=auth).status_code == 200

    # ...but every capability-gated endpoint refuses with the documented code.
    for path, payload in _GATED_ENDPOINTS:
        response = client.post(path, headers=auth, json=payload)
        assert response.status_code == 403, path
        assert response.json()["code"] == "email_unverified", path


def test_confirm_unlocks_gated_endpoints(client, caplog):
    with caplog.at_level("INFO"):
        client.post(
            "/auth/register",
            json={"email": "verifyme@test.com", "username": "verifyuser", "password": "testpassword123"},
        )
    verify_token = _extract_verification_token(caplog)

    confirm = client.post("/auth/verify-email/confirm", json={"token": verify_token})
    assert confirm.status_code == 204

    auth = client.post(
        "/auth/token", json={"username": "verifyuser", "password": "testpassword123"}
    )
    token = auth.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # /auth/me now reports verified.
    assert client.get("/auth/me", headers=headers).json()["email_verified"] is True

    # A gated write goes through.
    response = client.post(
        "/analysis/",
        headers=headers,
        json={"analysis_type": "vegetation_stress", "description": "now allowed", **_AREA},
    )
    assert response.status_code == 200, response.text

    # And the direct side effect is present too.
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "verifyuser").first()
        assert user.email_verified_at is not None
    finally:
        db.close()


def test_verification_token_is_single_use(client, caplog):
    with caplog.at_level("INFO"):
        client.post(
            "/auth/register",
            json={"email": "singleuse@test.com", "username": "singleuseuser", "password": "testpassword123"},
        )
    verify_token = _extract_verification_token(caplog)

    first = client.post("/auth/verify-email/confirm", json={"token": verify_token})
    assert first.status_code == 204

    second = client.post("/auth/verify-email/confirm", json={"token": verify_token})
    assert second.status_code == 400


def test_garbage_token_is_rejected(client):
    response = client.post("/auth/verify-email/confirm", json={"token": "not-a-real-token"})
    assert response.status_code == 400


def test_resend_requires_auth(client):
    response = client.post("/auth/verify-email/resend")
    assert response.status_code == 401


def test_resend_sends_a_new_working_token(client, caplog):
    email = "resenduser@test.com"
    with caplog.at_level("INFO"):
        client.post(
            "/auth/register",
            json={"email": email, "username": "resenduser", "password": "testpassword123"},
        )
    auth = _register_and_login(client, "resenduser", email=email)

    caplog.clear()
    with caplog.at_level("INFO"):
        resend = client.post("/auth/verify-email/resend", headers=auth)
    assert resend.status_code == 202
    new_verify_token = _extract_verification_token(caplog)

    confirm = client.post("/auth/verify-email/confirm", json={"token": new_verify_token})
    assert confirm.status_code == 204


def test_verified_account_resend_is_a_no_op(client, caplog):
    with caplog.at_level("INFO"):
        client.post(
            "/auth/register",
            json={"email": "already@test.com", "username": "alreadyuser", "password": "testpassword123"},
        )
    auth = client.post(
        "/auth/token", json={"username": "alreadyuser", "password": "testpassword123"}
    )
    token = auth.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    _mark_verified("alreadyuser")

    resend = client.post("/auth/verify-email/resend", headers=headers)
    assert resend.status_code == 202
    assert "already verified" in resend.json()["detail"]
