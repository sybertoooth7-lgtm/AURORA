"""Tests for the platform/infrastructure scaling round.

Covers the observation cache, job retry policy, job metrics, the shared
enqueue path, and the operator job endpoint. Local runs are demo mode, so the
queue is the synchronous inline one and Redis is the in-memory substitute.
"""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from rq import Retry

from app.cache import KEY_PREFIX, _key, cached_fetch_latest, clear_area_cache
from app.config import get_settings
from app.database import SessionLocal, demo_mode, engine
from app.job_metrics import (
    COUNTER_NAMES,
    RECENT_FAILURES_KEY,
    counter,
    recent_failures,
    record,
    record_failure,
    snapshot,
)
from app.models.user import User
from app.queue import (
    RQ_ENQUEUE_OPTIONS,
    _InlineQueue,
    analysis_retry_policy,
    enqueue_analysis,
    get_redis,
)
from app.satellite.providers import DemoSatelliteProvider, SatelliteObservation, SatelliteProvider
from app.services.analysis_runner import is_retryable
from main import app

_ACCOUNT_SEQ = 0


class _CountingProvider(SatelliteProvider):
    """Provider that records how often it is actually hit."""

    def __init__(self) -> None:
        self.calls = 0

    def fetch_latest(self, latitude, longitude, radius_km) -> SatelliteObservation:
        self.calls += 1
        return SatelliteObservation(
            source="demo",
            image_id=f"counting-{self.calls}",
            acquired_at=datetime.now(UTC),
            cloud_coverage=0.0,
            resolution_m=10.0,
            ndvi=0.5,
            change_score=0.1,
        )


class _FailingProvider(SatelliteProvider):
    def fetch_latest(self, latitude, longitude, radius_km):
        raise RuntimeError("provider is down")


AREA = (-1.2921, 36.8219, 2.0)


def _explode(*args, **kwargs):
    raise RuntimeError("redis is down")


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean_state():
    redis = get_redis()
    prefixes = ("auth:*", "quota:*", "ratelimit:*", f"{KEY_PREFIX}:*", "jobs:*")

    def _wipe():
        for prefix in prefixes:
            for key in redis.keys(prefix):
                redis.delete(key)

    _wipe()
    yield
    _wipe()


def _auth_headers(client, *, admin=False, password="correcthorsebatterystaple"):
    global _ACCOUNT_SEQ
    _ACCOUNT_SEQ += 1
    username = f"platform_user_{_ACCOUNT_SEQ}"
    client.post(
        "/auth/register",
        json={"email": f"{username}@test.com", "username": username, "password": password},
    )
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        assert user is not None
        user.email_verified_at = datetime.now(UTC)
        if admin:
            user.is_admin = True
        db.commit()
    finally:
        db.close()
    token = client.post(
        "/auth/token", json={"username": username, "password": password}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestObservationCache:
    def test_second_fetch_for_the_same_area_is_a_hit(self):
        provider = _CountingProvider()
        first = cached_fetch_latest(provider, *AREA)
        second = cached_fetch_latest(provider, *AREA)

        assert provider.calls == 1
        assert first.image_id == "counting-1"
        # The cached entry is a rebuilt observation, not the same object.
        assert second.image_id == first.image_id
        assert counter("cache_miss") == 1
        assert counter("cache_hit") == 1

    def test_a_different_area_never_reuses_another_areas_observation(self):
        provider = _CountingProvider()
        cached_fetch_latest(provider, *AREA)
        cached_fetch_latest(provider, -1.2922, 36.8219, 2.0)

        assert provider.calls == 2

    def test_a_different_radius_is_a_different_key(self):
        provider = _CountingProvider()
        cached_fetch_latest(provider, AREA[0], AREA[1], 2.0)
        cached_fetch_latest(provider, AREA[0], AREA[1], 3.0)

        assert provider.calls == 2

    def test_provider_class_is_part_of_the_key(self):
        """A demo entry must never be served where the live provider was asked."""
        demo = DemoSatelliteProvider()
        cached_fetch_latest(demo, *AREA)
        other = _CountingProvider()
        cached_fetch_latest(other, *AREA)

        assert other.calls == 1

    def test_ttl_of_zero_disables_caching(self, monkeypatch):
        monkeypatch.setattr(get_settings(), "OBSERVATION_CACHE_TTL_SECONDS", 0)
        provider = _CountingProvider()
        cached_fetch_latest(provider, *AREA)
        cached_fetch_latest(provider, *AREA)

        assert provider.calls == 2
        assert counter("cache_miss") == 0

    def test_a_cached_simulated_observation_stays_simulated(self):
        provider = _CountingProvider()
        cached_fetch_latest(provider, *AREA)
        served = cached_fetch_latest(provider, *AREA)

        assert served.source == "demo"
        assert served.is_simulated is True

    def test_a_payload_cannot_claim_a_provenance_its_source_does_not_support(self):
        """``simulated`` is derived, so a forged cache entry cannot relabel demo data."""
        payload = {
            "source": "demo",
            "image_id": "forged",
            "acquired_at": datetime.now(UTC).isoformat(),
            "cloud_coverage": 0.0,
            "resolution_m": 10.0,
            "ndvi": 0.5,
            "change_score": 0.1,
            "simulated": False,
        }

        assert SatelliteObservation.from_dict(payload).is_simulated is True

    def test_unreadable_cache_entry_falls_back_to_a_live_fetch(self):
        provider = _CountingProvider()
        cached_fetch_latest(provider, *AREA)
        # A hand-written entry the codec cannot decode must cost a fetch, not
        # the request.
        get_redis().set(_key(provider, *AREA), b"[1, 2, 3]", ex=60)

        rebuilt = cached_fetch_latest(provider, *AREA)
        assert rebuilt.image_id == "counting-2"
        assert provider.calls == 2

    def test_provider_failure_is_not_swallowed_by_the_cache(self):
        with pytest.raises(RuntimeError, match="provider is down"):
            cached_fetch_latest(_FailingProvider(), *AREA)

    def test_cache_write_failure_still_returns_the_observation(self, monkeypatch):
        provider = _CountingProvider()
        monkeypatch.setattr(get_redis(), "set", _explode)
        observation = cached_fetch_latest(provider, *AREA)
        assert observation.image_id == "counting-1"
        assert provider.calls == 1


class TestClearAreaCache:
    def test_clearing_drops_every_cached_observation(self):
        provider = _CountingProvider()
        cached_fetch_latest(provider, *AREA)
        removed = clear_area_cache()

        assert removed >= 1
        # Wiped, so the next read has to go back to the provider.
        cached_fetch_latest(provider, *AREA)
        assert provider.calls == 2


class TestRetryClassification:
    def test_provider_failures_are_worth_another_attempt(self):
        assert is_retryable(RuntimeError("connection reset")) is True
        assert is_retryable(TimeoutError("stats endpoint timed out")) is True

    def test_known_permanent_failures_are_not_retried(self):
        from app.ai.registry import UnknownPipelineError

        # Each retry spends real Sentinel Hub processing units on the same bad
        # input, so these must fail on the first pass.
        assert is_retryable(UnknownPipelineError("no such pipeline")) is False
        assert is_retryable(ValueError("radius must be positive")) is False
        assert is_retryable(KeyError("ndvi")) is False


class TestRetryPolicy:
    def test_policy_matches_the_configured_retry_count(self, monkeypatch):
        monkeypatch.setattr(get_settings(), "ANALYSIS_JOB_MAX_RETRIES", 3)
        monkeypatch.setattr(get_settings(), "ANALYSIS_JOB_RETRY_BACKOFF_SECONDS", 30)
        policy = analysis_retry_policy()

        assert isinstance(policy, Retry)
        assert policy.max == 3
        # Linear-increasing: a rate-limited provider gets growing breathing room.
        assert policy.intervals == [30, 60, 90]

    def test_zero_retries_disables_the_policy(self, monkeypatch):
        monkeypatch.setattr(get_settings(), "ANALYSIS_JOB_MAX_RETRIES", 0)
        assert analysis_retry_policy() is None


class TestEnqueueAnalysis:
    def test_inline_queue_drops_rq_only_kwargs(self):
        seen = {}

        def job(analysis_id):
            seen["analysis_id"] = analysis_id
            return analysis_id

        assert _InlineQueue().enqueue(job, 7, **{option: 1 for option in RQ_ENQUEUE_OPTIONS}) == 7
        assert seen == {"analysis_id": 7}

    def test_enqueue_uses_the_shared_policy_and_counts_the_pass(self, monkeypatch):
        queue = _InlineQueue()
        monkeypatch.setattr("app.queue.get_analysis_queue", lambda: queue)
        captured = {}

        def job(analysis_id):
            captured["analysis_id"] = analysis_id

        enqueue_analysis(job, 42)

        assert captured == {"analysis_id": 42}
        assert counter("enqueued") == 1

    def test_enqueue_passes_retry_when_configured(self, monkeypatch):
        monkeypatch.setattr(get_settings(), "ANALYSIS_JOB_MAX_RETRIES", 2)
        kwargs = {}

        class Recording(_InlineQueue):
            def enqueue(self, func, *args, **options):
                kwargs.update(options)
                return None

        monkeypatch.setattr("app.queue.get_analysis_queue", lambda: Recording())
        enqueue_analysis(lambda analysis_id: None, 1)

        assert "retry" in kwargs
        assert kwargs["result_ttl"] == get_settings().ANALYSIS_JOB_RESULT_TTL_SECONDS


class TestJobMetrics:
    def test_counters_round_trip(self):
        record("completed", 3)
        record("completed")

        assert counter("completed") == 4
        assert counter("failed") == 0

    def test_unknown_counter_reads_as_zero(self):
        assert counter("not_a_counter") == 0

    def test_recording_never_raises_when_redis_is_broken(self, monkeypatch):
        monkeypatch.setattr(get_redis(), "incr", _explode)
        record("completed")

    def test_failure_trail_is_newest_first_and_bounded(self):
        for attempt in range(30):
            record_failure(1000 + attempt, f"boom {attempt}", 1)

        failures = recent_failures()
        assert len(failures) == 25
        assert failures[0]["analysis_id"] == 1029
        assert failures[0]["error"] == "boom 29"

    def test_a_corrupt_failure_trail_reads_empty(self):
        get_redis().set(RECENT_FAILURES_KEY, b"{oops", ex=60)
        assert recent_failures() == []

    def test_snapshot_reports_success_rate_and_every_counter(self):
        record("completed", 3)
        record("failed", 1)
        view = snapshot(queue_depth=2)

        assert view["day"] == datetime.now(UTC).strftime("%Y-%m-%d")
        assert set(view["counters"]) == set(COUNTER_NAMES)
        assert view["success_rate"] == 0.75
        assert view["queue_depth"] == 2

    def test_snapshot_success_rate_is_undefined_before_any_job_runs(self):
        assert snapshot()["success_rate"] is None


class TestSchemaIndexes:
    def test_hot_query_paths_declare_composite_indexes(self):
        from app.models.alert import Alert
        from app.models.analysis import Analysis, AnalysisResult

        def names(model):
            return {index.name for index in model.__table__.indexes}

        assert {
            "ix_analyses_user_created",
            "ix_analyses_user_status",
            "ix_analyses_next_check_at",
        } <= names(Analysis)
        assert "ix_analysis_results_analysis_created" in names(AnalysisResult)
        assert {"ix_alerts_user_created", "ix_alerts_user_read"} <= names(Alert)

    @pytest.mark.skipif(not demo_mode(), reason="schema is migrated by CI, not create_all")
    def test_indexes_are_physically_created(self):
        from sqlalchemy import inspect

        found = {index["name"] for index in inspect(engine).get_indexes("analyses")}
        assert "ix_analyses_user_created" in found


class TestJobsEndpoint:
    def test_the_endpoint_is_admin_only(self, client):
        response = client.get("/system/jobs", headers=_auth_headers(client))
        assert response.status_code == 403

    def test_admins_get_pipeline_state(self, client):
        headers = _auth_headers(client, admin=True)
        record("enqueued", 5)
        record("completed", 4)
        record("failed", 1)
        record_failure(9, "provider timeout", 2)

        body = client.get("/system/jobs", headers=headers).json()

        assert body["queue"]["name"] == "analysis"
        assert body["queue"]["depth"] == 0
        assert body["today"]["counters"]["enqueued"] == 5
        assert body["today"]["success_rate"] == 0.8
        assert body["today"]["recent_failures"][0]["analysis_id"] == 9
        assert body["job_policy"]["max_retries"] == get_settings().ANALYSIS_JOB_MAX_RETRIES
        assert body["observation_cache"]["ttl_seconds"] == get_settings().OBSERVATION_CACHE_TTL_SECONDS
        assert "monitored_areas" in body["monitoring"]
        assert isinstance(body["stuck_analyses"], list)

    def test_unauthenticated_requests_are_rejected(self, client):
        assert client.get("/system/jobs").status_code == 401
