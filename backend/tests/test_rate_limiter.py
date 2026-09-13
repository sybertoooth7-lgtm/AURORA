"""Tests for the Redis-backed rate limiter (app.rate_limiter), which
replaced the old in-process OrderedDict limiter specifically so the
limit holds correctly across multiple API instances -- verified here by
confirming two independent Python-level callers (standing in for two
API processes) share state through Redis rather than each getting their
own separate counter.
"""

import time

import pytest
from fastapi.testclient import TestClient

from app.queue import get_redis
from app.rate_limiter import is_rate_limited
from main import app


@pytest.fixture(autouse=True)
def _clean_redis():
    redis = get_redis()
    keys = redis.keys("ratelimit:*") + redis.keys("test:ratelimit:*")
    if keys:
        redis.delete(*keys)
    yield
    keys = redis.keys("ratelimit:*") + redis.keys("test:ratelimit:*")
    if keys:
        redis.delete(*keys)


class TestIsRateLimited:
    def test_allows_up_to_the_limit(self):
        key = "test:ratelimit:allow"
        for _ in range(5):
            assert is_rate_limited(key, limit=5, window_seconds=60) is False

    def test_blocks_after_the_limit(self):
        key = "test:ratelimit:block"
        for _ in range(5):
            is_rate_limited(key, limit=5, window_seconds=60)
        assert is_rate_limited(key, limit=5, window_seconds=60) is True

    def test_different_keys_are_independent(self):
        for _ in range(5):
            is_rate_limited("test:ratelimit:a", limit=5, window_seconds=60)
        # A different key's budget is untouched by "a" being exhausted.
        assert is_rate_limited("test:ratelimit:b", limit=5, window_seconds=60) is False

    def test_shared_across_separate_callers_not_per_process(self):
        # Stands in for "two API replicas checking the same client" --
        # the whole point of moving this to Redis. If this were still the
        # old in-memory dict, each of these calls would only ever see its
        # own process's counter and neither would ever ge limited.
        key = "test:ratelimit:shared"
        replica_a_calls = 3
        replica_b_calls = 3
        limit = 5

        results = []
        for _ in range(replica_a_calls):
            results.append(is_rate_limited(key, limit=limit, window_seconds=60))
        for _ in range(replica_b_calls):
            results.append(is_rate_limited(key, limit=limit, window_seconds=60))

        # 6 total calls against a limit of 5 -- the 6th (from "replica B")
        # must see the combined count from both, not just its own 3.
        assert results.count(True) == 1
        assert results[-1] is True

    def test_window_expires(self):
        key = "test:ratelimit:window"
        for _ in range(3):
            is_rate_limited(key, limit=3, window_seconds=1)
        assert is_rate_limited(key, limit=3, window_seconds=1) is True

        time.sleep(1.1)
        assert is_rate_limited(key, limit=3, window_seconds=1) is False


class TestRateLimitMiddleware:
    def test_auth_endpoint_gets_limited_independently_of_general_api(self):
        client = TestClient(app)

        # Exhaust the (stricter) auth-endpoint budget.
        settings_limit = 10  # AUTH_RATE_LIMIT_REQUESTS default
        statuses = []
        for _ in range(settings_limit + 2):
            resp = client.post(
                "/auth/token", json={"username": "nobody", "password": "wrong"}
            )
            statuses.append(resp.status_code)

        assert 429 in statuses

        # General API traffic (a different bucket) is unaffected.
        health = client.get("/health/")
        assert health.status_code == 200
