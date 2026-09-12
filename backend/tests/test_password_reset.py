"""End-to-end tests for the password reset / change flow.

Runs against the real ASGI app with Postgres+Redis (same expectation as
test_ai_api.py and the app's own auth hardening tests) rather than mocking
the DB/Redis layer, since the whole point is verifying the pieces actually
fit together: reset token -> Redis -> password update -> token_version bump
-> old JWTs rejected.
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
    # This file makes several /auth/register + /auth/token calls in quick
    # succession across its tests, which is exactly what the auth-endpoint
    # rate limit (10/min, see main.py) exists to catch -- clear it between
    # tests so the tests are isolated from each other rather than from the
    # feature actually being tested.
    import main

    main.rate_limit_state.clear()
    yield
    main.rate_limit_state.clear()


def _register_and_login(client, username, password="correcthorsebatterystaple"):
    email = f"{username}@test.com"
    client.post(
        "/auth/register",
        json={"email": email, "username": username, "password": password},
    )
    resp = client.post("/auth/token", json={"username": username, "password": password})
    return email, resp.json()["access_token"]


def _extract_reset_token(caplog) -> str:
    # SMTP isn't configured in tests, so app.email logs the message body
    # (which contains the reset URL) instead of sending it.
    for record in caplog.records:
        match = re.search(r"[?&]token=([\w-]+)", record.getMessage())
        if match:
            return match.group(1)
    raise AssertionError("No password reset link found in logs")


class TestPasswordResetRequest:
    def test_unknown_email_gets_same_response_as_known(self, client):
        known_email, _ = _register_and_login(client, "resetuser1")

        known_resp = client.post("/auth/password-reset/request", json={"email": known_email})
        unknown_resp = client.post(
            "/auth/password-reset/request", json={"email": "nobody@nowhere.com"}
        )

        assert known_resp.status_code == unknown_resp.status_code == 202
        assert known_resp.json() == unknown_resp.json()


class TestPasswordResetConfirm:
    def test_full_reset_flow(self, client, caplog):
        email, old_token = _register_and_login(client, "resetuser2")

        with caplog.at_level("INFO"):
            client.post("/auth/password-reset/request", json={"email": email})
        reset_token = _extract_reset_token(caplog)

        confirm = client.post(
            "/auth/password-reset/confirm",
            json={"token": reset_token, "new_password": "brandnewpassword123"},
        )
        assert confirm.status_code == 204

        # Old token is now rejected -- password reset invalidated it even
        # though it hadn't expired.
        me_check = client.get("/analysis/", headers={"Authorization": f"Bearer {old_token}"})
        assert me_check.status_code == 401

        # Old password no longer works.
        old_login = client.post(
            "/auth/token", json={"username": "resetuser2", "password": "correcthorsebatterystaple"}
        )
        assert old_login.status_code == 401

        # New password works.
        new_login = client.post(
            "/auth/token", json={"username": "resetuser2", "password": "brandnewpassword123"}
        )
        assert new_login.status_code == 200

    def test_token_is_single_use(self, client, caplog):
        email, _ = _register_and_login(client, "resetuser3")

        with caplog.at_level("INFO"):
            client.post("/auth/password-reset/request", json={"email": email})
        reset_token = _extract_reset_token(caplog)

        first = client.post(
            "/auth/password-reset/confirm",
            json={"token": reset_token, "new_password": "firstnewpassword123"},
        )
        assert first.status_code == 204

        second = client.post(
            "/auth/password-reset/confirm",
            json={"token": reset_token, "new_password": "secondnewpassword123"},
        )
        assert second.status_code == 400

    def test_garbage_token_is_rejected(self, client):
        response = client.post(
            "/auth/password-reset/confirm",
            json={"token": "not-a-real-token", "new_password": "whatever123"},
        )
        assert response.status_code == 400


class TestPasswordChange:
    def test_change_password_while_logged_in(self, client):
        _, old_access_token = _register_and_login(client, "changeuser1")

        response = client.post(
            "/auth/password/change",
            headers={"Authorization": f"Bearer {old_access_token}"},
            json={
                "current_password": "correcthorsebatterystaple",
                "new_password": "differentpassword456",
            },
        )
        assert response.status_code == 204

        # The token used to make the change is itself now stale (tv bumped).
        me_check = client.get(
            "/analysis/", headers={"Authorization": f"Bearer {old_access_token}"}
        )
        assert me_check.status_code == 401

        new_login = client.post(
            "/auth/token",
            json={"username": "changeuser1", "password": "differentpassword456"},
        )
        assert new_login.status_code == 200

    def test_wrong_current_password_is_rejected(self, client):
        _, access_token = _register_and_login(client, "changeuser2")

        response = client.post(
            "/auth/password/change",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"current_password": "totallywrong", "new_password": "differentpassword456"},
        )
        assert response.status_code == 401
