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
# NDWI (McFeeters) = (B03 - B08) / (B03 + B08) -- green/NIR water index.
# EVI = 2.5 * (B08 - B04) / (B08 + 6*B04 - 7.5*B02 + 1) -- resists soil
# noise, useful where NDVI saturates.
_NDVI_EVALSCRIPT = """
//VERSION=3
function setup() {
  return {
    input: [{ bands: ["B02", "B03", "B04", "B08", "SCL", "dataMask"] }],
    output: [
      { id: "ndvi", bands: 1, sampleType: "FLOAT32" },
      { id: "ndwi", bands: 1, sampleType: "FLOAT32" },
      { id: "evi", bands: 1, sampleType: "FLOAT32" },
      { id: "dataMask", bands: 1 }
    ]
  };
}
function evaluatePixel(sample) {
  var cloudy = [3, 8, 9, 10].indexOf(sample.SCL) !== -1;
  var mask = (sample.dataMask === 1 && !cloudy) ? 1 : 0;
  var denom = sample.B08 + sample.B04;
  var ndvi = denom === 0 ? 0 : (sample.B08 - sample.B04) / denom;
  var ndwiDenom = sample.B03 + sample.B08;
  var ndwi = ndwiDenom === 0 ? 0 : (sample.B03 - sample.B08) / ndwiDenom;
  var eviDenom = sample.B08 + 6 * sample.B04 - 7.5 * sample.B02 + 1;
  var evi = eviDenom === 0 ? 0 : 2.5 * (sample.B08 - sample.B04) / eviDenom;
  return { ndvi: [ndvi], ndwi: [ndwi], evi: [evi], dataMask: [mask] };
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
    def _interval_stats(entry: Dict[str, Any], output: str = "ndvi") -> Optional[Dict[str, Any]]:
        """Pull the area statistics for one evalscript output of one day.

        Older/other deployments may not emit every requested output (or the
        Statistical API may omit an output for a day with no usable pixels),
        so a missing output returns None rather than raising.
        """
        stats = (
            entry.get("outputs", {})
            .get(output, {})
            .get("bands", {})
            .get("B0", {})
            .get("stats", {})
        )
        if not stats or stats.get("sampleCount", 0) <= 0:
            return None
        return stats

    def _fetch_intervals(
        self, latitude: float, longitude: float, radius_km: float
    ) -> List[Dict[str, Any]]:
        """Fetch and parse usable daily intervals for an area of interest.

        Raises SentinelHubRequestError when the API call itself fails or no
        cloud-free interval is available in the lookback window.
        """
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
            stats = self._interval_stats(entry)
            if stats is not None:
                usable.append({"entry": entry, "stats": stats})

        if not usable:
            raise SentinelHubRequestError(
                "No cloud-free Sentinel-2 observations found for this area in the "
                f"last {self._lookback_days} days; try a larger radius or a longer lookback."
            )
        return usable

    def _observation_from_interval(self, entry: Dict[str, Any]) -> SatelliteObservation:
        """Build a SatelliteObservation for one Statistical API interval."""
        ndvi_stats = self._interval_stats(entry)
        acquired_at = datetime.fromisoformat(entry["interval"]["to"].replace("Z", "+00:00"))
        ndwi_stats = self._interval_stats(entry, output="ndwi")
        evi_stats = self._interval_stats(entry, output="evi")
        return SatelliteObservation(
            source="sentinel-2-l2a",
            image_id=(
                f"cdse-{acquired_at.strftime('%Y%m%dT%H%M%S')}"
                f"-{entry['interval']['from']}"
            ),
            acquired_at=acquired_at,
            cloud_coverage=0.0,  # cloudy pixels are already excluded from the area means
            resolution_m=10.0,
            ndvi=round(float(ndvi_stats["mean"]), 4) if ndvi_stats else 0.0,
            change_score=0.0,
            ndwi=round(float(ndwi_stats["mean"]), 4) if ndwi_stats else None,
            evi=round(float(evi_stats["mean"]), 4) if evi_stats else None,
        )

    def fetch_latest(self, latitude: float, longitude: float, radius_km: float) -> SatelliteObservation:
        intervals = self._fetch_intervals(latitude, longitude, radius_km)
        latest = intervals[-1]["entry"]
        observation = self._observation_from_interval(latest)

        history = [float(item["stats"]["mean"]) for item in intervals[:-1]]
        if history:
            baseline = statistics.fmean(history)
            change_score = min(abs(observation.ndvi - baseline) / 0.4, 1.0)
        else:
            change_score = 0.0

        observation = SatelliteObservation(
            source=observation.source,
            image_id=observation.image_id,
            acquired_at=observation.acquired_at,
            cloud_coverage=observation.cloud_coverage,
            resolution_m=observation.resolution_m,
            ndvi=observation.ndvi,
            change_score=round(change_score, 4),
            ndwi=observation.ndwi,
            evi=observation.evi,
        )
        return observation

    def fetch_history(
        self, latitude: float, longitude: float, radius_km: float, limit: int = 10
    ) -> List[SatelliteObservation]:
        intervals = self._fetch_intervals(latitude, longitude, radius_km)
        observations = [self._observation_from_interval(item["entry"]) for item in intervals]

        # change_score per interval vs the *earlier* baseline, mirroring the
        # semantics used by fetch_latest, so history consumers see comparable
        # numbers rather than a flat zero.
        if len(observations) > 1:
            baseline = statistics.fmean(obs.ndvi for obs in observations[:-1])
            observations[-1] = SatelliteObservation(
                source=observations[-1].source,
                image_id=observations[-1].image_id,
                acquired_at=observations[-1].acquired_at,
                cloud_coverage=observations[-1].cloud_coverage,
                resolution_m=observations[-1].resolution_m,
                ndvi=observations[-1].ndvi,
                change_score=round(min(abs(observations[-1].ndvi - baseline) / 0.4, 1.0), 4),
                ndwi=observations[-1].ndwi,
                evi=observations[-1].evi,
            )
        return observations[-limit:]
