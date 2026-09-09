"""Copernicus Data Space Ecosystem (Sentinel Hub) satellite provider.

Uses the free CDSE deployment of the Sentinel Hub Statistical API, which
computes NDVI server-side over an area of interest and hands back aggregate
stats (mean/min/max/stddev/sampleCount) as JSON -- no raster download or
image processing needed on our end.

Credentials are an OAuth client_id/client_secret pair, not a single API key.
Create one at https://shapps.dataspace.copernicus.eu/dashboard/ under
User Settings -> OAuth clients. Registration and the Sentinel-2 archive are
free; see https://dataspace.copernicus.eu/ for the current terms.

Reference docs:
  https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Statistical.html
  https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Authentication.html
"""

from __future__ import annotations

import math
import statistics
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.satellite.providers import SatelliteObservation, SatelliteProvider

DEFAULT_TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
)
DEFAULT_STATS_URL = "https://sh.dataspace.copernicus.eu/api/v1/statistics"

# NDVI = (B08 - B04) / (B08 + B04). SCL classes 3, 8, 9, 10 are cloud
# shadow / cloud (medium+high probability) / thin cirrus -- masked out so
# cloudy pixels don't pollute the area-mean NDVI.
_NDVI_EVALSCRIPT = """
//VERSION=3
function setup() {
  return {
    input: [{ bands: ["B04", "B08", "SCL", "dataMask"] }],
    output: [
      { id: "ndvi", bands: 1, sampleType: "FLOAT32" },
      { id: "dataMask", bands: 1 }
    ]
  };
}
function evaluatePixel(sample) {
  var cloudy = [3, 8, 9, 10].indexOf(sample.SCL) !== -1;
  var mask = (sample.dataMask === 1 && !cloudy) ? 1 : 0;
  var denom = sample.B08 + sample.B04;
  var ndvi = denom === 0 ? 0 : (sample.B08 - sample.B04) / denom;
  return { ndvi: [ndvi], dataMask: [mask] };
}
"""


class SentinelHubAuthError(RuntimeError):
    """Raised when the Copernicus Data Space Ecosystem rejects our credentials."""


class SentinelHubRequestError(RuntimeError):
    """Raised when a Statistical API request fails or returns no usable data."""


class SentinelHubProvider(SatelliteProvider):
    """Real NDVI observations sourced from Sentinel-2 L2A via CDSE."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        token_url: str = DEFAULT_TOKEN_URL,
        stats_url: str = DEFAULT_STATS_URL,
        lookback_days: int = 30,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = token_url
        self._stats_url = stats_url
        self._lookback_days = lookback_days
        self._http = http_client or httpx.Client(timeout=30.0)
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0

    def _get_token(self) -> str:
        """Fetch (and cache) an OAuth access token via client_credentials."""
        if self._token and time.monotonic() < self._token_expires_at:
            return self._token
        response = self._http.post(
            self._token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
        )
        if response.status_code != 200:
            raise SentinelHubAuthError(
                "Copernicus Data Space Ecosystem token request failed: "
                f"{response.status_code} {response.text}"
            )
        payload = response.json()
        self._token = payload["access_token"]
        # Refresh a little early so we never race the real expiry.
        self._token_expires_at = time.monotonic() + max(payload.get("expires_in", 300) - 30, 30)
        return self._token

    @staticmethod
    def _bbox(latitude: float, longitude: float, radius_km: float) -> List[float]:
        """Approximate degree-space bounding box, matching the polygon math
        already used elsewhere in the backend for the stored analysis area."""
        lat_delta = radius_km / 111.32
        lon_delta = radius_km / (111.32 * max(math.cos(math.radians(latitude)), 0.01))
        return [
            longitude - lon_delta,
            latitude - lat_delta,
            longitude + lon_delta,
            latitude + lat_delta,
        ]

    def _stats_request_body(self, latitude: float, longitude: float, radius_km: float) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=self._lookback_days)
        return {
            "input": {
                "bounds": {
                    "bbox": self._bbox(latitude, longitude, radius_km),
                    "properties": {"crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"},
                },
                "data": [
                    {
                        "type": "sentinel-2-l2a",
                        "dataFilter": {"maxCloudCoverage": 60},
                    }
                ],
            },
            "aggregation": {
                "timeRange": {
                    "from": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "to": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
                "aggregationInterval": {"of": "P1D"},
                "evalscript": _NDVI_EVALSCRIPT,
                "resx": 10,
                "resy": 10,
            },
        }

    @staticmethod
    def _interval_ndvi_mean(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        stats = (
            entry.get("outputs", {})
            .get("ndvi", {})
            .get("bands", {})
            .get("B0", {})
            .get("stats", {})
        )
        if not stats or stats.get("sampleCount", 0) <= 0:
            return None
        return stats

    def fetch_latest(self, latitude: float, longitude: float, radius_km: float) -> SatelliteObservation:
        token = self._get_token()
        body = self._stats_request_body(latitude, longitude, radius_km)
        response = self._http.post(
            self._stats_url,
            json=body,
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code != 200:
            raise SentinelHubRequestError(
                "Copernicus Data Space Ecosystem statistics request failed: "
                f"{response.status_code} {response.text}"
            )
        payload = response.json()

        usable: List[Dict[str, Any]] = []
        for entry in payload.get("data", []):
            stats = self._interval_ndvi_mean(entry)
            if stats is not None:
                usable.append({"interval": entry["interval"], "stats": stats})

        if not usable:
            raise SentinelHubRequestError(
                "No cloud-free Sentinel-2 observations found for this area in the "
                f"last {self._lookback_days} days; try a larger radius or a longer lookback."
            )

        latest = usable[-1]
        ndvi = float(latest["stats"]["mean"])

        history = [float(item["stats"]["mean"]) for item in usable[:-1]]
        if history:
            baseline = statistics.fmean(history)
            change_score = min(abs(ndvi - baseline) / 0.4, 1.0)
        else:
            change_score = 0.0

        acquired_at = datetime.fromisoformat(latest["interval"]["to"].replace("Z", "+00:00"))
        return SatelliteObservation(
            source="sentinel-2-l2a",
            image_id=f"cdse-{acquired_at.strftime('%Y%m%dT%H%M%S')}-{round(latitude, 4)}-{round(longitude, 4)}",
            acquired_at=acquired_at,
            cloud_coverage=0.0,  # cloudy pixels are already excluded from the NDVI mean
            resolution_m=10.0,
            ndvi=round(ndvi, 4),
            change_score=round(change_score, 4),
        )
