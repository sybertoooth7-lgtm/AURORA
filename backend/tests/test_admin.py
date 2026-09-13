"""Tests for the admin API (app/routes/admin.py): listing users,
disabling/enabling accounts, and the require_admin gate itself.

There's no API to grant is_admin (by design -- see admin.py's module
docstring), so these tests promote a user to admin directly via the DB,
the same way a real operator would.
"""

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.models.user import User
from app.queue import get_redis
from main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean_redis():
    redis = get_redis()
    keys = redis.keys("auth:*") + redis.keys("ratelimit:*")
    if keys:
        redis.delete(*keys)
    yield
    keys = redis.keys("auth:*") + redis.keys("ratelimit:*")
    if keys:
        redis.delete(*keys)


def _register_and_login(client, username, password="correcthorsebatterystaple"):
    email = f"{username}@test.com"
    client.post(
        "/auth/register",
        json={"email": email, "username": username, "password": password},
    )
    token = client.post(
        "/auth/token", json={"username": username, "password": password}
    ).json()["access_token"]
    return token


def _promote_to_admin(username: str) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        user.is_admin = True
        db.commit()
    finally:
        db.close()


class TestRequireAdminGate:
    def test_non_admin_gets_403(self, client):
        token = _register_and_login(client, "plainuser1")
        response = client.get("/admin/users", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403

    def test_unauthenticated_gets_401(self, client):
        response = client.get("/admin/users")
        assert response.status_code == 401

    def test_admin_can_access(self, client):
        token = _register_and_login(client, "adminuser1")
        _promote_to_admin("adminuser1")
        response = client.get("/admin/users", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200


class TestListUsers:
    def test_lists_all_users_with_total(self, client):
        _register_and_login(client, "listeduser1")
        _register_and_login(client, "listeduser2")
        admin_token = _register_and_login(client, "listadmin")
        _promote_to_admin("listadmin")

        response = client.get("/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
        assert response.status_code == 200
        body = response.json()
        assert body["total"] >= 3
        usernames = {u["username"] for u in body["users"]}
        assert {"listeduser1", "listeduser2", "listadmin"}.issubset(usernames)

    def test_pagination_limit_is_capped(self, client):
        admin_token = _register_and_login(client, "paginateadmin")
        _promote_to_admin("paginateadmin")

        response = client.get(
            "/admin/users?limit=99999", headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        assert response.json()["limit"] == 200


class TestGetUser:
    def test_get_single_user(self, client):
        _register_and_login(client, "detailuser1")
        admin_token = _register_and_login(client, "detailadmin")
        _promote_to_admin("detailadmin")

        db = SessionLocal()
        try:
            target = db.query(User).filter(User.username == "detailuser1").first()
            target_id = target.id
        finally:
            db.close()

        response = client.get(
            f"/admin/users/{target_id}", headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        assert response.json()["username"] == "detailuser1"

    def test_unknown_user_is_404(self, client):
        admin_token = _register_and_login(client, "notfoundadmin")
        _promote_to_admin("notfoundadmin")

        response = client.get(
            "/admin/users/999999", headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 404


class TestDisableAndEnableUser:
    def test_disable_blocks_login_and_kills_existing_session(self, client):
        target_token = _register_and_login(client, "disableuser1")
        admin_token = _register_and_login(client, "disableadmin1")
        _promote_to_admin("disableadmin1")

        db = SessionLocal()
        try:
            target_id = db.query(User).filter(User.username == "disableuser1").first().id
        finally:
            db.close()

        # The session obtained before being disabled should die immediately.
        pre_check = client.get("/analysis/", headers={"Authorization": f"Bearer {target_token}"})
        assert pre_check.status_code == 200

        disable_resp = client.post(
            f"/admin/users/{target_id}/disable",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert disable_resp.status_code == 200
        assert disable_resp.json()["is_active"] is False

        post_check = client.get("/analysis/", headers={"Authorization": f"Bearer {target_token}"})
        assert post_check.status_code == 401

        login_attempt = client.post(
            "/auth/token",
            json={"username": "disableuser1", "password": "correcthorsebatterystaple"},
        )
        assert login_attempt.status_code == 401

    def test_admin_cannot_disable_self(self, client):
        admin_token = _register_and_login(client, "selfdisableadmin")
        _promote_to_admin("selfdisableadmin")

        db = SessionLocal()
        try:
            admin_id = db.query(User).filter(User.username == "selfdisableadmin").first().id
        finally:
            db.close()

        response = client.post(
            f"/admin/users/{admin_id}/disable", headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 409

    def test_enable_restores_login(self, client):
        _register_and_login(client, "enableuser1")
        admin_token = _register_and_login(client, "enableadmin1")
        _promote_to_admin("enableadmin1")

        db = SessionLocal()
        try:
            target_id = db.query(User).filter(User.username == "enableuser1").first().id
        finally:
            db.close()

        client.post(
            f"/admin/users/{target_id}/disable", headers={"Authorization": f"Bearer {admin_token}"}
        )
        login_while_disabled = client.post(
            "/auth/token",
            json={"username": "enableuser1", "password": "correcthorsebatterystaple"},
        )
        assert login_while_disabled.status_code == 401

        enable_resp = client.post(
            f"/admin/users/{target_id}/enable", headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert enable_resp.status_code == 200
        assert enable_resp.json()["is_active"] is True

        login_after_enable = client.post(
            "/auth/token",
            json={"username": "enableuser1", "password": "correcthorsebatterystaple"},
        )
        assert login_after_enable.status_code == 200
