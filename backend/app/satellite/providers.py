"""Provider boundary for satellite observations."""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib


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
    """Return the configured provider boundary for the current deployment."""
    return DemoSatelliteProvider()