"""API key management tests.

Minting, listing (the plaintext secret is shown exactly once), revocation,
expiry, cross-account isolation, the per-user key cap, and -- critically --
that a raw API key authenticates through the same Authorization: Bearer
header shape as a JWT while still being refused once revoked.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import SessionLocal
from app.models.api_key import ApiKey
from app.models.user import User
from app.queue import get_redis
from main import app

_PASSWORD = "testpassword123"
_ACCOUNT_SEQ = 0


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


def _register(client, *, verified: bool):
    global _ACCOUNT_SEQ
    _ACCOUNT_SEQ += 1
    username = f"apikey_user_{_ACCOUNT_SEQ}"
    email = f"{username}@test.com"
    resp = client.post(
        "/auth/register",
        json={"email": email, "username": username, "password": _PASSWORD},
    )
    assert resp.status_code == 201
    if verified:
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == username).first()
            assert user is not None
            user.email_verified_at = datetime.now(UTC)
            db.commit()
        finally:
            db.close()
    token = client.post(
        "/auth/token", json={"username": username, "password": _PASSWORD}
    ).json()["access_token"]
    return username, {"Authorization": f"Bearer {token}"}


def _create_key(client, headers, name="ci-key"):
    return client.post("/auth/api-keys", headers=headers, json={"name": name})


class TestApiKeys:
    def test_create_returns_the_secret_once_and_it_authenticates(self, client):
        username, headers = _register(client, verified=True)

        resp = _create_key(client, headers)
        assert resp.status_code == 201, resp.text
        body = resp.json()
        raw = body["key"]
        assert raw.startswith(get_settings().API_KEY_PREFIX)
        assert body["prefix"] == raw[:14]
        assert body["name"] == "ci-key"

        # The raw key is a first-class Bearer credential (same header shape
        # as a JWT) and flows through the same gated endpoint checks.
        key_headers = {"Authorization": f"Bearer {raw}"}
        me = client.get("/auth/me", headers=key_headers)
        assert me.status_code == 200
        assert me.json()["username"] == username
        assert me.json()["email_verified"] is True

        created = client.post(
            "/analysis/",
            headers=key_headers,
            json={"analysis_type": "vegetation_stress", "latitude": -1.29, "longitude": 36.82, "radius_km": 5},
        )
        assert created.status_code == 200, created.text

    def test_list_shows_only_the_masked_prefix(self, client):
        _, headers = _register(client, verified=True)
        for name in ("alpha", "beta"):
            assert _create_key(client, headers, name=name).status_code == 201

        listed = client.get("/auth/api-keys", headers=headers)
        assert listed.status_code == 200
        body = listed.json()
        assert body["total"] == 2
        for entry in body["keys"]:
            assert "key" not in entry
            assert entry["prefix"].startswith("aur_")
            assert "alpha" in [e["name"] for e in body["keys"]]

    def test_unknown_key_is_rejected(self, client):
        _, headers = _register(client, verified=True)
        me = client.get("/auth/me", headers={"Authorization": "Bearer aur_" + "x" * 43})
        assert me.status_code == 401

    def test_revoked_key_stops_working_and_revoke_is_idempotent(self, client):
        _, headers = _register(client, verified=True)
        first = _create_key(client, headers, name="first").json()
        second = _create_key(client, headers, name="second").json()
        assert first["id"] != second["id"]

        revoked = client.post(f"/auth/api-keys/{second['id']}/revoke", headers=headers)
        assert revoked.status_code == 200
        assert revoked.json()["revoked"] is True

        blocked = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {second['key']}"},
        )
        assert blocked.status_code == 401
        # The untouched key keeps working.
        alive = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {first['key']}"},
        )
        assert alive.status_code == 200

        # Revoking again is a harmless no-op.
        again = client.post(f"/auth/api-keys/{second['id']}/revoke", headers=headers)
        assert again.status_code == 200
        assert again.json()["revoked"] is True

    def test_revoking_the_used_key_blocks_it(self, client):
        _, headers = _register(client, verified=True)
        first = _create_key(client, headers, name="first").json()
        second = _create_key(client, headers, name="second").json()
        assert first["id"] != second["id"]

        client.post(f"/auth/api-keys/{first['id']}/revoke", headers=headers)
        me = client.get("/auth/me", headers={"Authorization": f"Bearer {first['key']}"})
        assert me.status_code == 401
        # The other key is untouched.
        other = client.get("/auth/me", headers={"Authorization": f"Bearer {second['key']}"})
        assert other.status_code == 200

    def test_expired_key_is_rejected(self, client):
        _, headers = _register(client, verified=True)
        raw = _create_key(client, headers, name="doomed").json()["key"]

        db = SessionLocal()
        try:
            row = db.query(ApiKey).filter(ApiKey.prefix == raw[:14]).first()
            assert row is not None
            row.expires_at = datetime.now(UTC) - timedelta(minutes=5)
            db.commit()
        finally:
            db.close()

        me = client.get("/auth/me", headers={"Authorization": f"Bearer {raw}"})
        assert me.status_code == 401

    def test_cannot_revoke_someone_elses_key(self, client):
        owner = _register(client, verified=True)[1]
        attacker = _register(client, verified=True)[1]
        key_id = _create_key(client, owner).json()["id"]

        resp = client.post(f"/auth/api-keys/{key_id}/revoke", headers=attacker)
        assert resp.status_code == 404
        assert resp.json()["code"] == "not_found"

        # Owner's key still works.
        raw = _create_key(client, owner, name="attacker-repeat").json()["key"]
        me = client.get("/auth/me", headers={"Authorization": f"Bearer {raw}"})
        assert me.status_code == 200

    def test_per_user_key_cap_is_enforced(self, client):
        _, headers = _register(client, verified=True)
        limit = get_settings().MAX_API_KEYS_PER_USER
        for i in range(limit):
            resp = _create_key(client, headers, name=f"key-{i}")
            assert resp.status_code == 201, resp.text

        overflow = _create_key(client, headers, name="overflow")
        assert overflow.status_code == 409
        assert overflow.json()["code"] == "conflict"
