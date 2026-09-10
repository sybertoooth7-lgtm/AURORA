"""Redis-backed request rate limiting."""

from functools import lru_cache
import time

from redis.asyncio import Redis
from redis import Redis as SyncRedis

from app.config import get_settings

_INCREMENT_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return {count, redis.call('TTL', KEYS[1])}
"""


@lru_cache()
def get_rate_limit_redis() -> Redis:
    """Return the shared async Redis connection used by API instances."""
    return Redis.from_url(get_settings().REDIS_URL, decode_responses=True)


@lru_cache()
def get_auth_redis() -> SyncRedis:
    """Return a synchronous Redis connection for auth dependencies."""
    return SyncRedis.from_url(get_settings().REDIS_URL, decode_responses=True)


async def record_request(client_key: str) -> tuple[int, int]:
    """Atomically record a request and return its count and remaining seconds."""
    result = await get_rate_limit_redis().eval(
        _INCREMENT_SCRIPT,
        1,
        f"aurora:rate-limit:{client_key}",
        get_settings().RATE_LIMIT_WINDOW_SECONDS,
    )
    return int(result[0]), max(int(result[1]), 0)


async def record_login_attempt(client_key: str) -> tuple[int, int]:
    """Record a login attempt using the stricter auth-specific window."""
    result = await get_rate_limit_redis().eval(
        _INCREMENT_SCRIPT,
        1,
        f"aurora:login-rate-limit:{client_key}",
        get_settings().LOGIN_RATE_LIMIT_WINDOW_SECONDS,
    )
    return int(result[0]), max(int(result[1]), 0)


def revoke_token(jti: str, expires_at: int) -> None:
    """Blacklist a token until its original expiration time."""
    ttl = max(expires_at - int(time.time()), 1)
    get_auth_redis().setex(f"aurora:revoked-token:{jti}", ttl, "1")


def is_token_revoked(jti: str) -> bool:
    """Check whether a token has been explicitly logged out."""
    return bool(get_auth_redis().exists(f"aurora:revoked-token:{jti}"))
