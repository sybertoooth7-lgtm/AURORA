"""Tests for the (soft) email verification flow: a new account works
immediately without verifying, but the verification link/resend/confirm
mechanism itself needs to actually work end to end.
"""

import re

import pytest
from fastapi.testclient import TestClient

from app.queue import get_redis
from main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean_redis():
    redis = get_redis()
    for key in redis.keys("auth:*"):
        redis.delete(key)
    yield
    for key in redis.keys("auth:*"):
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


def _extract_verification_token(caplog) -> str:
    for record in caplog.records:
        match = re.search(r"verify-email\?token=([\w-]+)", record.getMessage())
        if match:
            return match.group(1)
    raise AssertionError("No verification link found in logs")


def test_new_account_is_unverified_but_fully_usable(client, caplog):
    with caplog.at_level("INFO"):
        register_resp = client.post(
            "/auth/register",
            json={"email": "unverified@test.com", "username": "unverifieduser", "password": "testpassword123"},
        )
    assert register_resp.json()["email_verified"] is False

    # A verification email was sent automatically on registration.
    _extract_verification_token(caplog)

    # And the account works fully without verifying -- this is soft.
    login = client.post(
        "/auth/token", json={"username": "unverifieduser", "password": "testpassword123"}
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    assert client.get("/analysis/", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_confirm_marks_the_account_verified(client, caplog):
    with caplog.at_level("INFO"):
        client.post(
            "/auth/register",
            json={"email": "verifyme@test.com", "username": "verifyuser", "password": "testpassword123"},
        )
    verify_token = _extract_verification_token(caplog)

    confirm = client.post("/auth/verify-email/confirm", json={"token": verify_token})
    assert confirm.status_code == 204

    # No /auth/me endpoint exists yet to check this through the API, so
    # check the actual side effect directly.
    from app.database import SessionLocal
    from app.models.user import User

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
    token = client.post(
        "/auth/token", json={"username": "resenduser", "password": "testpassword123"}
    ).json()["access_token"]

    caplog.clear()
    with caplog.at_level("INFO"):
        resend = client.post(
            "/auth/verify-email/resend", headers={"Authorization": f"Bearer {token}"}
        )
    assert resend.status_code == 202
    new_verify_token = _extract_verification_token(caplog)

    confirm = client.post("/auth/verify-email/confirm", json={"token": new_verify_token})
    assert confirm.status_code == 204


def test_resend_is_a_no_op_once_already_verified(client, caplog):
    with caplog.at_level("INFO"):
        client.post(
            "/auth/register",
            json={"email": "already@test.com", "username": "alreadyuser", "password": "testpassword123"},
        )
    verify_token = _extract_verification_token(caplog)
    client.post("/auth/verify-email/confirm", json={"token": verify_token})

    token = client.post(
        "/auth/token", json={"username": "alreadyuser", "password": "testpassword123"}
    ).json()["access_token"]

    resend = client.post("/auth/verify-email/resend", headers={"Authorization": f"Bearer {token}"})
    assert resend.status_code == 202
    assert "already verified" in resend.json()["detail"]
