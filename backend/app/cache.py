"""Shared, TTL-bounded cache for satellite observations.

A live Sentinel-2 request is paid for out the Copernicus Data Space free-tier
processing-unit budget, and the same area gets read repeatedly: a dashboard
polling an area, a re-run, a bulk import whose fields overlap. Each of those
was an independent upstream fetch.

Caching is deliberately conservative:

* The key includes the provider *class*, so a simulated demo observation can
  never be served to a caller that would have hit the live provider.
* Coordinates are kept at full precision (6 dp is ~11 cm), so two neighbouring
  fields are never treated as the same area. Rounding to anything coarser
  would silently report one field's NDVI as another's.
* The TTL is short. A stale crop reading is worse than a duplicated request.
* Every failure to read or write the cache falls back to a live fetch -- the
  cache is an optimisation and must never become a dependency.

"""

import hashlib
import json

from app.config import get_settings
from app.job_metrics import record
from app.logging_conf import get_logger
from app.queue import get_redis
from app.satellite.providers import SatelliteObservation, SatelliteProvider

logger = get_logger(__name__)

KEY_PREFIX = "obs:latest"


def _key(provider: SatelliteProvider, latitude: float, longitude: float, radius_km: float) -> str:
    area = f"{latitude:.6f}:{longitude:.6f}:{radius_km:.6f}"
    digest = hashlib.sha256(area.encode()).hexdigest()[:24]
    return f"{KEY_PREFIX}:{type(provider).__name__}:{digest}"


def cached_fetch_latest(
    provider: SatelliteProvider, latitude: float, longitude: float, radius_km: float
) -> SatelliteObservation:
    """Return the latest observation for an area, reusing a recent fetch if one exists."""
    ttl = get_settings().OBSERVATION_CACHE_TTL_SECONDS
    if ttl <= 0:
        return provider.fetch_latest(latitude, longitude, radius_km)

    key = _key(provider, latitude, longitude, radius_km)
    redis = get_redis()
    try:
        raw = redis.get(key)
    except Exception:  # noqa: BLE001 - cache must never be load-bearing
        logger.warning("observation cache read failed", exc_info=True)
        raw = None

    if raw:
        observation = _decode(raw)
        if observation is not None:
            record("cache_hit")
            return observation

    record("cache_miss")
    observation = provider.fetch_latest(latitude, longitude, radius_km)
    try:
        redis.set(key, json.dumps(observation.to_dict()), ex=ttl)
    except Exception:  # noqa: BLE001 - a write failure only costs the optimisation
        logger.warning("observation cache write failed", exc_info=True)
    return observation


def _decode(raw) -> SatelliteObservation | None:
    """Rebuild a cached observation, or None if the entry cannot be trusted."""
    try:
        payload = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
        if not isinstance(payload, dict):
            return None
        return SatelliteObservation.from_dict(payload)
    except (KeyError, TypeError, ValueError):
        logger.warning("discarding unreadable cached observation", exc_info=True)
        return None


def clear_area_cache() -> int:
    """Drop every cached observation. Returns how many were removed.

    Used when the provider identity changes (credentials added mid-deploy), so
    an area cannot keep serving entries fetched under the other provider.
    """
    redis = get_redis()
    keys = redis.keys(f"{KEY_PREFIX}:*")
    if keys:
        redis.delete(*keys)
    return len(keys)
