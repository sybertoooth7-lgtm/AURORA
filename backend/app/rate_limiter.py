"""Redis-backed rate limiting.

Replaces the old in-process OrderedDict limiter, which tracked counters
per API process -- correct for one instance, but silently N times looser
than configured the moment you run N replicas (each process had its own
separate counters, with no shared view of how many requests a client had
actually made). This uses a sliding-window log (a Redis sorted set per
key, scored by request time) so the limit holds regardless of how many
API instances are running, since they all share the same Redis.

The per-account login lockout (app.security) was already Redis-backed
and is unaffected by any of this -- this module only replaces the
general/auth-endpoint per-IP request throttle in main.py.
"""

import time
import uuid

from app.queue import get_redis


def is_rate_limited(key: str, limit: int, window_seconds: int) -> bool:
    """True if `key` has already made `limit` requests within the
    trailing `window_seconds`; otherwise records this request and
    returns False.

    Atomic via a Redis transaction (MULTI/EXEC), so concurrent requests
    from the same key across different API processes can't race past
    the limit.
    """
    redis = get_redis()
    now_ms = time.time() * 1000
    window_start_ms = now_ms - (window_seconds * 1000)
    # Unique member per request -- two requests landing in the same
    # millisecond must still both count, so the score alone can't be the
    # member (sorted set members are deduplicated by value).
    member = f"{now_ms}:{uuid.uuid4().hex}"

    pipe = redis.pipeline(transaction=True)
    pipe.zremrangebyscore(key, 0, window_start_ms)  # drop entries outside the window
    pipe.zadd(key, {member: now_ms})
    pipe.zcard(key)
    pipe.expire(key, window_seconds + 1)  # self-cleans if this key goes quiet
    _, _, count, _ = pipe.execute()

    return count > limit
