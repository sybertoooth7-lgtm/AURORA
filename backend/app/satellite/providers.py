"""Provider boundary for satellite observations."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
from typing import List, Optional

from app.config import get_settings

# Sentinel-2 L2A source identifier produced by the live provider. Anything
# else (e.g. the "demo" provider) is simulated and must always be reported
# as such downstream -- simulated results are never presented as real.
REAL_SOURCE_IDS = {"sentinel-2-l2a", "landsat-8", "landsat-9", "sentinel-1"}


@dataclass(frozen=True)
class SatelliteObservation:
    """An observation of one area from one satellite pass.

    `ndvi`/`change_score` are the two core metrics also available when only
    an area-level NDVI statistic is available; the higher-order indices
    (ndwi, evi, bsi) are optional and only filled when the provider can
    compute them. `provided_bands` carries the raw area-mean band values
    (band name -> mean reflectance) whenever the provider exposes them.
    """

    source: str
    image_id: str
    acquired_at: datetime
    cloud_coverage: float
    resolution_m: float
    ndvi: float
    change_score: float
    ndwi: Optional[float] = None
    evi: Optional[float] = None
    bsi: Optional[float] = None
    provided_bands: dict = field(default_factory=dict)

    @property
    def is_simulated(self) -> bool:
        """True when this observation did not come from a real sensor."""
        return self.source not in REAL_SOURCE_IDS

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "image_id": self.image_id,
            "acquired_at": self.acquired_at.isoformat(),
            "cloud_coverage": self.cloud_coverage,
            "resolution_m": self.resolution_m,
            "ndvi": self.ndvi,
            "change_score": self.change_score,
            "ndwi": self.ndwi,
            "evi": self.evi,
            "bsi": self.bsi,
            "provided_bands": self.provided_bands,
            "simulated": self.is_simulated,
        }


class SatelliteProvider:
    """Interface implemented by Sentinel, Landsat, and demo providers."""

    def fetch_latest(self, latitude: float, longitude: float, radius_km: float) -> SatelliteObservation:
        raise NotImplementedError

    def fetch_history(
        self, latitude: float, longitude: float, radius_km: float, limit: int = 10
    ) -> List[SatelliteObservation]:
        """Chronological recent observations for a fixed area.

        Optional; pipelines that look for deviations against a baseline
        (anomaly detection, change detection) use this. Providers that
        cannot reconstruct a history return an empty list.
        """
        return []


class DemoSatelliteProvider(SatelliteProvider):
    """Deterministic local provider used until a live provider is configured.

    The values are synthetic (always marked source="demo" -> simulated
    downstream) but deterministic per area/radius, which keeps local dev
    and CI reproducible without any real credentials.
    """

    @staticmethod
    def _seed(latitude: float, longitude: float, radius_km: float) -> bytes:
        return f"{latitude:.4f}:{longitude:.4f}:{radius_km:.2f}".encode("utf-8")

    def _deterministic_observations(
        self, latitude: float, longitude: float, radius_km: float, count: int
    ) -> List[SatelliteObservation]:
        seed = self._seed(latitude, longitude, radius_km)
        digest = hashlib.sha256(seed).digest()
        ndvi = 0.25 + (digest[0] / 255) * 0.55
        change_score = (digest[1] / 255) * 0.65
        ndwi = -0.3 + (digest[2] / 255) * 0.4
        evi = 0.1 + (digest[3] / 255) * 0.5
        bsi = (digest[4] / 255) * 0.6

        # Make the "history" deterministic but not a flat line: offset each
        # observation by a function of the digest so time-series pipelines
        # (anomaly / change) see realistic variation between passes.
        observations: List[SatelliteObservation] = []
        now = datetime.now(timezone.utc)
        for i in range(count):
            wobble = (digest[(5 + i) % len(digest)] / 255 - 0.5) * 0.1
            acquired = now - timedelta(days=count - i) if count - i > 0 else now
            observations.append(
                SatelliteObservation(
                    source="demo",
                    image_id=f"demo-{digest.hex()[:16]}-{i}",
                    acquired_at=acquired,
                    cloud_coverage=round((digest[2] / 255) * 0.25, 4),
                    resolution_m=10.0,
                    ndvi=round(min(max(ndvi + wobble, 0.0), 1.0), 4),
                    change_score=round(min(max(change_score + wobble * 0.5, 0.0), 1.0), 4),
                    ndwi=round(max(-1.0, min(1.0, ndwi + wobble * 0.3)), 4),
                    evi=round(max(0.0, min(1.0, evi + wobble * 0.3)), 4),
                    bsi=round(max(0.0, min(1.0, bsi)), 4),
                )
            )
        return observations

    def fetch_latest(self, latitude: float, longitude: float, radius_km: float) -> SatelliteObservation:
        seed = self._seed(latitude, longitude, radius_km)
        digest = hashlib.sha256(seed).digest()
        ndvi = 0.25 + (digest[0] / 255) * 0.55
        change_score = (digest[1] / 255) * 0.65
        ndwi = -0.3 + (digest[2] / 255) * 0.4
        evi = 0.1 + (digest[3] / 255) * 0.5
        bsi = (digest[4] / 255) * 0.6
        return SatelliteObservation(
            source="demo",
            image_id=f"demo-{digest.hex()[:16]}",
            acquired_at=datetime.now(timezone.utc),
            cloud_coverage=round((digest[2] / 255) * 0.25, 4),
            resolution_m=10.0,
            ndvi=round(ndvi, 4),
            change_score=round(change_score, 4),
            ndwi=round(ndwi, 4),
            evi=round(evi, 4),
            bsi=round(bsi, 4),
        )

    def fetch_history(
        self, latitude: float, longitude: float, radius_km: float, limit: int = 10
    ) -> List[SatelliteObservation]:
        return self._deterministic_observations(latitude, longitude, radius_km, count=max(1, limit))


def get_satellite_provider() -> SatelliteProvider:
    """Return the configured provider boundary for the current deployment.

    Uses the real Copernicus Data Space Ecosystem (Sentinel Hub) provider
    when SENTINEL_CLIENT_ID / SENTINEL_CLIENT_SECRET are configured, and
    falls back to the deterministic demo provider otherwise (local dev,
    tests, or before credentials are provisioned).
    """
    settings = get_settings()
    if settings.SENTINEL_CLIENT_ID and settings.SENTINEL_CLIENT_SECRET:
        from app.satellite.sentinel_hub import SentinelHubProvider

        return SentinelHubProvider(
            client_id=settings.SENTINEL_CLIENT_ID,
            client_secret=settings.SENTINEL_CLIENT_SECRET,
            token_url=settings.SENTINEL_TOKEN_URL,
            stats_url=settings.SENTINEL_STATS_URL,
            lookback_days=settings.SENTINEL_LOOKBACK_DAYS,
        )
    return DemoSatelliteProvider()
