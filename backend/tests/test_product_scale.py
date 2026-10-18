"""Tests for the Earth-revenue product surface added in the 0.3 scaling round.

Covers the paged/filtered analysis list, the account roll-up, the monitoring
time series, and bulk field-boundary import. The queue is pinned to inline
execution below so these completion assertions hold in CI as well as in local
demo runs; the deterministic simulated provider is what the provenance
assertions are about -- honest labelling, not real imagery.
"""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.models.user import User
from app.queue import _InlineQueue, get_redis
from app.schemas.crop import MAX_BULK_FIELDS
from main import app

_ACCOUNT_SEQ = 0

AREA = {"latitude": -1.2921, "longitude": 36.8219, "radius_km": 2.0}


def _square(lon, lat, span=0.01):
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [lon - span, lat - span],
                [lon + span, lat - span],
                [lon + span, lat + span],
                [lon - span, lat + span],
                [lon - span, lat - span],
            ]
        ],
    }


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _inline_analysis_queue(monkeypatch):
    """Run analysis jobs synchronously, the same way demo mode does.

    These tests read back completed rows, status filters and per-pass history
    right after creating an area. CI runs against a real Redis whose RQ queue
    has no worker, so those jobs would stay queued and every completion
    assertion below would fail for reasons that have nothing to do with the
    product surface under test.
    """
    queue = _InlineQueue()
    monkeypatch.setattr("app.queue.get_analysis_queue", lambda: queue)


@pytest.fixture(autouse=True)
def _clean_redis():
    redis = get_redis()
    prefixes = ("auth:*", "quota:*", "ratelimit:*")

    def _wipe():
        for prefix in prefixes:
            for key in redis.keys(prefix):
                redis.delete(key)

    _wipe()
    yield
    _wipe()


def _verified_headers(client, password="correcthorsebatterystaple"):
    global _ACCOUNT_SEQ
    _ACCOUNT_SEQ += 1
    username = f"scale_user_{_ACCOUNT_SEQ}"
    client.post(
        "/auth/register",
        json={"email": f"{username}@test.com", "username": username, "password": password},
    )
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        assert user is not None
        user.email_verified_at = datetime.now(UTC)
        db.commit()
    finally:
        db.close()
    token = client.post(
        "/auth/token", json={"username": username, "password": password}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create(client, auth, **overrides):
    payload = {"analysis_type": "vegetation_stress", "description": "plot", **AREA, **overrides}
    response = client.post("/analysis/", headers=auth, json=payload)
    assert response.status_code == 200, response.text
    return response.json()


class TestPagedAnalysisList:
    def test_requires_auth(self, client):
        assert client.get("/analysis/").status_code == 401

    def test_returns_envelope_with_total_and_page(self, client):
        auth = _verified_headers(client)
        for index in range(3):
            _create(client, auth, description=f"plot {index}")

        body = client.get("/analysis/?limit=2", headers=auth).json()
        assert body["total"] == 3
        assert body["limit"] == 2
        assert body["skip"] == 0
        assert len(body["items"]) == 2

    def test_pages_do_not_overlap(self, client):
        auth = _verified_headers(client)
        for index in range(4):
            _create(client, auth, description=f"plot {index}")

        first = client.get("/analysis/?limit=2&skip=0", headers=auth).json()
        second = client.get("/analysis/?limit=2&skip=2", headers=auth).json()
        ids = {item["id"] for item in first["items"]} | {item["id"] for item in second["items"]}
        assert len(ids) == 4

    def test_newest_first_and_oldest_reverses(self, client):
        auth = _verified_headers(client)
        created = [_create(client, auth, description=f"plot {index}")["id"] for index in range(3)]

        newest = [item["id"] for item in client.get("/analysis/", headers=auth).json()["items"]]
        oldest = [
            item["id"] for item in client.get("/analysis/?order=oldest", headers=auth).json()["items"]
        ]
        assert newest == sorted(created, reverse=True)
        assert oldest == list(reversed(newest))

    def test_status_filter(self, client):
        auth = _verified_headers(client)
        _create(client, auth)

        completed = client.get("/analysis/?status=completed", headers=auth).json()
        assert completed["total"] == 1
        assert client.get("/analysis/?status=failed", headers=auth).json()["total"] == 0

    def test_type_filter_excludes_other_types(self, client):
        auth = _verified_headers(client)
        _create(client, auth)
        _create(client, auth, analysis_type="flood_monitoring")

        body = client.get("/analysis/?analysis_type=flood_monitoring", headers=auth).json()
        assert body["total"] == 1
        assert body["items"][0]["analysis_type"] == "flood_monitoring"

    def test_monitored_only_filter(self, client):
        auth = _verified_headers(client)
        plain = _create(client, auth)
        monitored = _create(client, auth, description="watched")
        client.patch(
            f"/analysis/{monitored['id']}/monitor",
            headers=auth,
            json={"monitor_interval_minutes": 30},
        )

        body = client.get("/analysis/?monitored_only=true", headers=auth).json()
        assert body["total"] == 1
        assert body["items"][0]["id"] != plain["id"]

    def test_rejects_invalid_page_and_order(self, client):
        auth = _verified_headers(client)
        assert client.get("/analysis/?limit=0", headers=auth).status_code == 422
        assert client.get("/analysis/?limit=500", headers=auth).status_code == 422
        assert client.get("/analysis/?order=random", headers=auth).status_code == 422


class TestAnalysisSummary:
    def test_requires_auth(self, client):
        assert client.get("/analysis/summary").status_code == 401

    def test_empty_account_reports_zeroes_not_errors(self, client):
        auth = _verified_headers(client)
        body = client.get("/analysis/summary", headers=auth).json()
        assert body["total_analyses"] == 0
        assert body["by_status"] == {}
        assert body["mean_severity"] is None
        assert body["monitored_areas"] == 0
        assert body["quota_remaining_today"] == body["quota_limit_per_day"]

    def test_counts_match_created_areas(self, client):
        auth = _verified_headers(client)
        _create(client, auth)
        second = _create(client, auth, analysis_type="flood_monitoring")
        client.patch(
            f"/analysis/{second['id']}/monitor",
            headers=auth,
            json={"monitor_interval_minutes": 60},
        )

        body = client.get("/analysis/summary", headers=auth).json()
        assert body["total_analyses"] == 2
        assert body["by_status"]["completed"] == 2
        assert body["by_analysis_type"]["vegetation_stress"] == 1
        assert body["by_analysis_type"]["flood_monitoring"] == 1
        assert body["monitored_areas"] == 1

    def test_summary_is_scoped_to_the_caller(self, client):
        auth = _verified_headers(client)
        _create(client, auth)
        other = _verified_headers(client)
        assert client.get("/analysis/summary", headers=other).json()["total_analyses"] == 0

    def test_provenance_counts_simulated_separately(self, client):
        auth = _verified_headers(client)
        _create(client, auth)

        body = client.get("/analysis/summary", headers=auth).json()
        assert body["provenance"] == {"simulated": 1}
        assert body["completed_with_findings"] >= 1

    def test_quota_headroom_drops_as_areas_are_created(self, client):
        auth = _verified_headers(client)
        before = client.get("/analysis/summary", headers=auth).json()
        _create(client, auth)
        _create(client, auth)
        after = client.get("/analysis/summary", headers=auth).json()

        assert before["quota_used_today"] == 0
        assert after["quota_used_today"] == 2
        assert after["quota_remaining_today"] == before["quota_limit_per_day"] - 2

    def test_severity_average_is_reported_when_present(self, client):
        auth = _verified_headers(client)
        _create(client, auth)
        body = client.get("/analysis/summary", headers=auth).json()
        if body["completed_with_findings"]:
            assert body["mean_severity"] is None or 0.0 <= body["mean_severity"] <= 1.0


class TestAnalysisHistory:
    def test_requires_auth(self, client):
        assert client.get("/analysis/1/history").status_code == 401

    def test_unknown_or_foreign_area_is_404(self, client):
        auth = _verified_headers(client)
        assert client.get("/analysis/999999/history", headers=auth).status_code == 404

    def test_single_pass_reports_single_pass_direction(self, client):
        auth = _verified_headers(client)
        created = _create(client, auth)

        body = client.get(f"/analysis/{created['id']}/history", headers=auth).json()
        assert body["passes"] == len(body["points"])
        assert body["direction"] in ("single_pass", "stable", "no_data")

    def test_rerun_appends_a_pass(self, client):
        auth = _verified_headers(client)
        created = _create(client, auth)
        client.post(f"/analysis/{created['id']}/re-run", headers=auth)

        body = client.get(f"/analysis/{created['id']}/history", headers=auth).json()
        assert body["passes"] >= 2
        assert body["first_checked_at"] <= body["latest_checked_at"]

    def test_repeated_pass_on_same_area_is_stable(self, client):
        """The demo provider is seeded by area, so re-running one area must
        read as stable rather than inventing a trend."""
        auth = _verified_headers(client)
        created = _create(client, auth)
        client.post(f"/analysis/{created['id']}/re-run", headers=auth)
        client.post(f"/analysis/{created['id']}/re-run", headers=auth)

        body = client.get(f"/analysis/{created['id']}/history", headers=auth).json()
        assert body["direction"] == "stable"
        assert body["severity_change"] == pytest.approx(0.0, abs=1e-9)

    def test_points_carry_provenance(self, client):
        auth = _verified_headers(client)
        created = _create(client, auth)

        body = client.get(f"/analysis/{created['id']}/history", headers=auth).json()
        for point in body["points"]:
            assert point["provenance"] in (None, "real", "simulated")


class TestBulkCropAnalysis:
    def test_requires_auth(self, client):
        response = client.post("/crop/analyze/bulk", json={"fields": []})
        assert response.status_code == 401

    def test_requires_verified_email(self, client):
        client.post(
            "/auth/register",
            json={
                "email": "bulk_unverified@test.com",
                "username": "bulk_unverified",
                "password": "correcthorsebatterystaple",
            },
        )
        token = client.post(
            "/auth/token",
            json={"username": "bulk_unverified", "password": "correcthorsebatterystaple"},
        ).json()["access_token"]
        response = client.post(
            "/crop/analyze/bulk",
            headers={"Authorization": f"Bearer {token}"},
            json={"fields": [{"label": "a", "field_boundary": _square(36.82, -1.29)}]},
        )
        assert response.status_code == 403
        assert response.json()["code"] == "email_unverified"

    def test_analyzes_every_field(self, client):
        auth = _verified_headers(client)
        fields = [
            {"label": f"field {index}", "field_boundary": _square(36.82 + index / 100, -1.29)}
            for index in range(3)
        ]
        response = client.post("/crop/analyze/bulk", headers=auth, json={"fields": fields})
        assert response.status_code == 201, response.text

        body = response.json()
        assert body["requested"] == 3
        assert body["succeeded"] == 3
        assert body["failed"] == 0
        assert [item["label"] for item in body["items"]] == ["field 0", "field 1", "field 2"]
        assert body["real"] + body["simulated"] == 3

    def test_labels_and_analysis_ids_round_trip(self, client):
        auth = _verified_headers(client)
        response = client.post(
            "/crop/analyze/bulk",
            headers=auth,
            json={"fields": [{"label": "north", "field_boundary": _square(36.82, -1.29)}]},
        )
        item = response.json()["items"][0]
        assert item["label"] == "north"
        assert item["analysis"]["analysis_id"] > 0
        assert item["analysis"]["boundary"]["coordinates"] == _square(36.82, -1.29)["coordinates"]

    def test_simulated_batch_never_claims_real(self, client):
        auth = _verified_headers(client)
        response = client.post(
            "/crop/analyze/bulk",
            headers=auth,
            json={
                "fields": [
                    {"label": "a", "field_boundary": _square(36.82, -1.29)},
                    {"label": "b", "field_boundary": _square(36.85, -1.31)},
                ]
            },
        )
        body = response.json()
        assert body["simulated"] == 2
        assert body["real"] == 0
        assert all(item["analysis"]["provenance"] == "simulated" for item in body["items"])

    def test_one_bad_boundary_does_not_lose_the_good_ones(self, client):
        auth = _verified_headers(client)
        degenerate = {
            "type": "Polygon",
            "coordinates": [[[0.0, 0.0], [1.0, 0.0], [2.0, 0.0], [0.0, 0.0]]],
        }
        response = client.post(
            "/crop/analyze/bulk",
            headers=auth,
            json={
                "fields": [
                    {"label": "good", "field_boundary": _square(36.82, -1.29)},
                    {"label": "flat", "field_boundary": degenerate},
                ]
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["succeeded"] == 1
        assert body["failed"] == 1
        failed = next(item for item in body["items"] if item["status"] == "failed")
        assert failed["label"] == "flat"
        assert "zero area" in failed["error"]

    def test_empty_batch_rejected(self, client):
        auth = _verified_headers(client)
        response = client.post("/crop/analyze/bulk", headers=auth, json={"fields": []})
        assert response.status_code == 422

    def test_oversized_batch_rejected(self, client):
        auth = _verified_headers(client)
        fields = [
            {"label": f"f{index}", "field_boundary": _square(36.8 + index / 100, -1.29)}
            for index in range(MAX_BULK_FIELDS + 1)
        ]
        response = client.post("/crop/analyze/bulk", headers=auth, json={"fields": fields})
        assert response.status_code == 422

    def test_batch_larger_than_remaining_quota_is_refused_before_work(self, monkeypatch, client):
        """A refused batch must not spend any quota -- charging part of a
        rejected request is how a retry loop eats a whole daily budget."""
        from app.config import get_settings

        auth = _verified_headers(client)
        # The default daily cap is far above the bulk batch limit, so shrink it
        # to make "batch does not fit" reachable at all.
        monkeypatch.setattr(get_settings(), "MAX_ANALYSES_PER_USER_PER_DAY", 3)
        _create(client, auth)

        fields = [
            {"label": f"f{index}", "field_boundary": _square(36.8 + index / 1000, -1.29)}
            for index in range(4)
        ]
        response = client.post("/crop/analyze/bulk", headers=auth, json={"fields": fields})
        assert response.status_code == 429
        assert response.json()["code"] == "rate_limited"
        assert response.json()["details"]["remaining"] == 2

        summary = client.get("/analysis/summary", headers=auth).json()
        assert summary["quota_used_today"] == 1

    def test_bulk_charges_quota_for_the_whole_batch(self, client):
        auth = _verified_headers(client)
        client.post(
            "/crop/analyze/bulk",
            headers=auth,
            json={
                "fields": [
                    {"label": "a", "field_boundary": _square(36.82, -1.29)},
                    {"label": "b", "field_boundary": _square(36.85, -1.31)},
                ]
            },
        )
        assert client.get("/analysis/summary", headers=auth).json()["quota_used_today"] == 2

    def test_bulk_results_appear_in_the_analysis_list(self, client):
        auth = _verified_headers(client)
        response = client.post(
            "/crop/analyze/bulk",
            headers=auth,
            json={"fields": [{"label": "a", "field_boundary": _square(36.82, -1.29)}]},
        )
        analysis_id = response.json()["items"][0]["analysis"]["analysis_id"]

        listed = client.get("/analysis/?analysis_type=vegetation_stress", headers=auth).json()
        assert analysis_id in {item["id"] for item in listed["items"]}
