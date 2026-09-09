"""Tests for the Copernicus Data Space Ecosystem (Sentinel Hub) provider.

Uses httpx.MockTransport so these run offline -- no real CDSE credentials
or network access required.
"""

import httpx
import pytest

from app.satellite.sentinel_hub import (
    SentinelHubAuthError,
    SentinelHubProvider,
    SentinelHubRequestError,
)


def _stats_payload(means):
    """Build a Statistical API response with one P1D interval per NDVI mean."""
    data = []
    for day, mean in enumerate(means):
        data.append({
            "interval": {
                "from": f"2026-08-{10 + day:02d}T00:00:00Z",
                "to": f"2026-08-{11 + day:02d}T00:00:00Z",
            },
            "outputs": {
                "ndvi": {
                    "bands": {
                        "B0": {
                            "stats": {
                                "min": mean - 0.05,
                                "max": mean + 0.05,
                                "mean": mean,
                                "stDev": 0.02,
                                "sampleCount": 900,
                                "noDataCount": 12,
                            }
                        }
                    }
                }
            },
        })
    return {"data": data, "status": "OK"}


def _provider(handler):
    return SentinelHubProvider(
        client_id="test-client",
        client_secret="test-secret",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_fetch_latest_returns_most_recent_ndvi_and_change_score():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/protocol/openid-connect/token"):
            return httpx.Response(200, json={"access_token": "tok-123", "expires_in": 300})
        assert request.headers["authorization"] == "Bearer tok-123"
        return httpx.Response(200, json=_stats_payload([0.30, 0.32, 0.55]))

    observation = _provider(handler).fetch_latest(-1.28, 36.82, 5.0)

    assert observation.source == "sentinel-2-l2a"
    assert observation.ndvi == 0.55
    # baseline mean of [0.30, 0.32] is 0.31; |0.55 - 0.31| / 0.4 = 0.6
    assert observation.change_score == pytest.approx(0.6, abs=1e-6)
    assert observation.resolution_m == 10.0


def test_token_is_cached_across_requests():
    calls = {"token": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/protocol/openid-connect/token"):
            calls["token"] += 1
            return httpx.Response(200, json={"access_token": "tok-abc", "expires_in": 300})
        return httpx.Response(200, json=_stats_payload([0.4]))

    provider = _provider(handler)
    provider.fetch_latest(-1.28, 36.82, 5.0)
    provider.fetch_latest(-1.28, 36.82, 5.0)

    assert calls["token"] == 1


def test_auth_failure_raises_sentinel_hub_auth_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid_client"})

    with pytest.raises(SentinelHubAuthError):
        _provider(handler).fetch_latest(-1.28, 36.82, 5.0)


def test_no_cloud_free_observations_raises_request_error():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/protocol/openid-connect/token"):
            return httpx.Response(200, json={"access_token": "tok-123", "expires_in": 300})
        return httpx.Response(200, json={"data": [], "status": "OK"})

    with pytest.raises(SentinelHubRequestError):
        _provider(handler).fetch_latest(-1.28, 36.82, 5.0)
