"""Per-user daily quotas on expensive operations.

Each analysis costs a real Sentinel Hub Statistical API request against
the Copernicus Data Space Ecosystem's free-tier processing-unit quota --
without a per-user cap, one user (or a buggy client stuck in a retry
loop) can burn through the whole account's quota and take real satellite
data down for every other user.

Backed by Redis with a key that expires at the next UTC midnight, so
quotas reset predictably with no separate cleanup job.
"""

from datetime import UTC, datetime, timedelta

from app.exceptions import RateLimitedError
from app.queue import get_redis


def _quota_key(user_id: int, scope: str) -> str:
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    return f"quota:{scope}:{user_id}:{day}"


def _seconds_until_next_utc_midnight() -> int:
    now = datetime.now(UTC)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(int((tomorrow - now).total_seconds()), 1)


def check_and_increment_daily_quota(user_id: int, scope: str, limit: int) -> None:
    """Raise RateLimitedError if `user_id` has already used `scope` `limit`
    times today; otherwise record this use and return normally."""
    redis = get_redis()
    key = _quota_key(user_id, scope)
    count = redis.incr(key)
    if count == 1:
        redis.expire(key, _seconds_until_next_utc_midnight())
    if count > limit:
        raise RateLimitedError(
            f"Daily limit of {limit} {scope} reached. Resets at midnight UTC.",
            details={"scope": scope, "limit": limit},
        )


def reserve_daily_quota(user_id: int, scope: str, limit: int, amount: int) -> None:
    """Charge `amount` uses against today's quota in one atomic step.

    Bulk endpoints need the whole batch accounted for before any of it runs:
    charging one at a time lets a request that exceeds the cap start work it
    has no budget for. Raises before recording anything when the batch would
    not fit, so a refused request costs the user nothing.
    """
    redis = get_redis()
    key = _quota_key(user_id, scope)
    used = current_daily_quota_usage(user_id, scope)
    if used + amount > limit:
        raise RateLimitedError(
            f"Requesting {amount} {scope} would exceed the daily limit of {limit} "
            f"({used} already used). Resets at midnight UTC.",
            details={
                "scope": scope,
                "limit": limit,
                "used": used,
                "requested": amount,
                "remaining": max(limit - used, 0),
            },
        )
    count = redis.incr(key, amount)
    if count == amount:
        redis.expire(key, _seconds_until_next_utc_midnight())


def current_daily_quota_usage(user_id: int, scope: str) -> int:
    """Return how many of today's `scope` uses are already spent (no charge)."""
    value = get_redis().get(_quota_key(user_id, scope))
    if value is None:
        return 0
    if isinstance(value, bytes):
        value = value.decode()
    return int(value)

