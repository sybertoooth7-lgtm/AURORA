"""Regression tests for the production-hardening pass:
- the AuroraError handler actually returns its intended status code
  (it previously crashed into a 500 on every single AuroraError, because
  logger.log() was called with a string like "WARNING" instead of the
  integer level constant it requires -- caught here by actually
  exercising an error path, which none of the existing tests did)
- health/readiness checks
- the per-user daily analysis quota
- docs lockdown follows ENVIRONMENT by default
"""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.queue import get_redis
from main import app


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
    return resp.json()["access_token"]


class TestAuroraErrorHandler:
    def test_an_actual_aurora_error_returns_its_own_status_code_not_500(self):
        # Exercise main.aurora_error_handler directly rather than hunting
        # for a business-logic path that happens to raise one: this is a
        # regression test for the handler itself (logger.log() previously
        # crashed on every single call because it received the string
        # "WARNING" where it needs the integer level constant), and a
        # direct test of the handler can't be defeated by an unrelated
        # refactor of whichever route used to trigger it.
        import asyncio

        from starlette.requests import Request

        import main
        from app.exceptions import NotFoundError

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/whatever",
            "headers": [],
            "query_string": b"",
        }
        request = Request(scope)
        exc = NotFoundError("thing not found")

        response = asyncio.run(main.aurora_error_handler(request, exc))

        assert response.status_code == 404


class TestHealthChecks:
    def test_liveness_is_always_ok(self, client):
        response = client.get("/health/")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_readiness_reports_db_and_redis(self, client):
        response = client.get("/health/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["ready"] is True
        assert body["checks"]["database"] == "ok"
        assert body["checks"]["redis"] == "ok"


class TestAnalysisQuota:
    def test_quota_blocks_after_limit_and_reports_429(self, client, monkeypatch):
        from app.config import get_settings

        monkeypatch.setattr(get_settings(), "MAX_ANALYSES_PER_USER_PER_DAY", 2)

        token = _register_and_login(client, "quotatestuser")
        headers = {"Authorization": f"Bearer {token}"}
        body = {
            "analysis_type": "vegetation_stress",
            "latitude": -1.28,
            "longitude": 36.82,
            "radius_km": 5,
        }

        r1 = client.post("/analysis/", headers=headers, json=body)
        r2 = client.post("/analysis/", headers=headers, json=body)
        r3 = client.post("/analysis/", headers=headers, json=body)

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r3.status_code == 429
        assert r3.json()["code"] == "rate_limited"


class TestDocsLockdown:
    def test_docs_follow_environment_by_default(self):
        dev_settings = Settings(ENVIRONMENT="development")
        assert dev_settings.api_docs_enabled is True

        prod_settings = Settings(ENVIRONMENT="production", SECRET_KEY="x" * 32)
        assert prod_settings.api_docs_enabled is False

    def test_explicit_override_wins_either_way(self):
        forced_on = Settings(ENVIRONMENT="production", SECRET_KEY="x" * 32, ENABLE_API_DOCS=True)
        assert forced_on.api_docs_enabled is True

        forced_off = Settings(ENVIRONMENT="development", ENABLE_API_DOCS=False)
        assert forced_off.api_docs_enabled is False
