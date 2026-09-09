"""Provider boundary for satellite observations."""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib

from app.config import get_settings


@dataclass(frozen=True)
class SatelliteObservation:
    source: str
    image_id: str
    acquired_at: datetime
    cloud_coverage: float
    resolution_m: float
    ndvi: float
    change_score: float


class SatelliteProvider:
    """Interface implemented by Sentinel, Landsat, and demo providers."""

    def fetch_latest(self, latitude: float, longitude: float, radius_km: float) -> SatelliteObservation:
        raise NotImplementedError


class DemoSatelliteProvider(SatelliteProvider):
    """Deterministic local provider used until a live provider is configured."""

    def fetch_latest(self, latitude: float, longitude: float, radius_km: float) -> SatelliteObservation:
        seed = f"{latitude:.4f}:{longitude:.4f}:{radius_km:.2f}".encode("utf-8")
        digest = hashlib.sha256(seed).digest()
        ndvi = 0.25 + (digest[0] / 255) * 0.55
        change_score = (digest[1] / 255) * 0.65
        return SatelliteObservation(
            source="demo",
            image_id=f"demo-{digest.hex()[:16]}",
            acquired_at=datetime.now(timezone.utc),
            cloud_coverage=round((digest[2] / 255) * 0.25, 4),
            resolution_m=10.0,
            ndvi=round(ndvi, 4),
            change_score=round(change_score, 4),
        )


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
