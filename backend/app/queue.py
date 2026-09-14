"""Redis-backed job queue for slow/long-running work (analysis runs).

Replaces FastAPI's BackgroundTasks for this purpose: BackgroundTasks run
in-process after the response is sent, so a slow satellite-provider call
blocks that worker process's event loop, and any job still running when the
process restarts (deploy, crash, OOM) is silently lost. RQ jobs live in
Redis, run in a separate `worker.py` process, and survive an API restart.

Demo mode (``ENABLE_DEMO_MODE=true``) swaps in an in-memory substitute for
both halves: a dict-backed fake Redis for the tiny lockout/revocation
surface, and a synchronous inline queue so analysis jobs complete within the
request without any external process.
"""

import time
from functools import lru_cache

from redis import Redis
from rq import Queue

from app.config import get_settings

ANALYSIS_QUEUE_NAME = "analysis"


class _DemoRedis:
    """In-memory stand-in for the tiny Redis surface AURORA actually uses
    (auth lockout counters + token-revocation flags). Not a general redis-py
    replacement -- the run path never needs more than these methods."""

    def __init__(self) -> None:
        self._data: dict[bytes, tuple[bytes, float | None]] = {}

    def _encode(self, value) -> bytes:
        return value if isinstance(value, bytes) else str(value).encode()

    def _prune(self) -> None:
        now = time.monotonic()
        self._data = {k: v for k, v in self._data.items() if v[1] is None or v[1] > now}

    def exists(self, *keys) -> int:
        self._prune()
        return sum(1 for k in keys if self._encode(k) in self._data)

    def get(self, key):
        self._prune()
        entry = self._data.get(self._encode(key))
        return entry[0] if entry else None

    def set(self, key, value, ex=None) -> bool:
        self._data[self._encode(key)] = (
            self._encode(value),
            time.monotonic() + ex if ex else None,
        )
        return True

    def setex(self, key, time_, value) -> bool:
        return self.set(key, value, ex=time_)

    def incr(self, key, amount: int = 1) -> int:
        self._prune()
        encoded = self._encode(key)
        entry = self._data.get(encoded)
        current = int(entry[0]) if entry else 0
        self._data[encoded] = (str(current + amount).encode(), entry[1] if entry else None)
        return current + amount

    def expire(self, key, time_) -> bool:
        encoded = self._encode(key)
        if encoded not in self._data:
            return False
        self._data[encoded] = (self._data[encoded][0], time.monotonic() + time_)
        return True

    def delete(self, *keys) -> int:
        return sum(1 for k in keys if self._data.pop(self._encode(k), None) is not None)

    def keys(self, pattern: str = "*") -> list[bytes]:
        self._prune()
        if pattern.endswith("*"):
            prefix = pattern[:-1].encode()
            return [k for k in self._data if k.startswith(prefix)]
        return []

    def flushdb(self) -> bool:
        self._data.clear()
        return True

    def ping(self) -> bool:
        return True


class _InlineQueue:
    """Executes enqueued jobs synchronously in the caller's process."""

    def __init__(self) -> None:
        self.name = ANALYSIS_QUEUE_NAME

    def enqueue(self, func, *args, **kwargs):
        job_timeout = kwargs.pop("job_timeout", None)
        del job_timeout
        return func(*args, **kwargs)


@lru_cache
def get_redis() -> Redis:
    """Return a cached Redis connection built from settings.REDIS_URL."""
    if get_settings().ENABLE_DEMO_MODE:
        return _DemoRedis()
    return Redis.from_url(get_settings().REDIS_URL)


@lru_cache
def get_analysis_queue() -> Queue:
    """Return the (cached) queue that analysis jobs are enqueued onto."""
    if get_settings().ENABLE_DEMO_MODE:
        return _InlineQueue()
    return Queue(ANALYSIS_QUEUE_NAME, connection=get_redis())
