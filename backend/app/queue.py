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

RQ_ENQUEUE_OPTIONS = ("job_timeout", "retry", "result_ttl", "ttl", "on_success", "on_failure")


class _DemoRedis:
    """In-memory stand-in for the tiny Redis surface AURORA actually uses
    (auth lockout counters + token-revocation flags). Not a general redis-py
    replacement -- the run path never needs more than these methods."""

    def __init__(self) -> None:
        self._data: dict[bytes, tuple[bytes, float | None]] = {}
        self._zsets: dict[bytes, dict[bytes, float]] = {}

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

    def set(self, key, value, ex=None, nx=False) -> bool:
        encoded = self._encode(key)
        if nx and encoded in self._data:
            return False
        self._data[encoded] = (
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
        removed = 0
        for k in keys:
            encoded = self._encode(k)
            removed += self._data.pop(encoded, None) is not None
            removed += self._zsets.pop(encoded, None) is not None
        return removed

    def getdel(self, key):
        encoded = self._encode(key)
        entry = self._data.pop(encoded, None)
        return entry[0] if entry else None

    def keys(self, pattern: str = "*") -> list[bytes]:
        self._prune()
        if pattern.endswith("*"):
            prefix = pattern[:-1].encode()
            matched = [k for k in self._data if k.startswith(prefix)]
            matched += [k for k in self._zsets if k.startswith(prefix)]
            return matched
        return []

    def flushdb(self) -> bool:
        self._data.clear()
        self._zsets.clear()
        return True

    def ping(self) -> bool:
        return True

    # Sorted-set surface used by the Redis-backed rate limiter
    # (app.rate_limiter) via a single pipeline.
    def zadd(self, key, mapping) -> int:
        store = self._zsets.setdefault(self._encode(key), {})
        added = 0
        for member, score in mapping.items():
            encoded_member = self._encode(member)
            if encoded_member not in store:
                added += 1
            store[encoded_member] = float(score)
        return added

    def zremrangebyscore(self, key, min_, max_) -> int:
        store = self._zsets.get(self._encode(key))
        if not store:
            return 0
        kept = {m: s for m, s in store.items() if not (s >= min_ and s <= max_)}
        removed = len(store) - len(kept)
        if kept:
            self._zsets[self._encode(key)] = kept
        else:
            self._zsets.pop(self._encode(key), None)
        return removed

    def zcard(self, key) -> int:
        return len(self._zsets.get(self._encode(key), {}))

    def pipeline(self, transaction=True):
        return _DemoPipeline(self)


class _DemoPipeline:
    """Buffers ops and replays them on ``_DemoRedis`` on execute()."""

    def __init__(self, redis: "_DemoRedis") -> None:
        self._redis = redis
        self._ops: list[tuple] = []

    def zremrangebyscore(self, key, min_, max_):
        self._ops.append(("zremrangebyscore", key, min_, max_))
        return self

    def zadd(self, key, mapping):
        self._ops.append(("zadd", key, mapping))
        return self

    def zcard(self, key):
        self._ops.append(("zcard", key))
        return self

    def expire(self, key, time_):
        self._ops.append(("expire", key, time_))
        return self

    def execute(self) -> list:
        results = []
        for op in self._ops:
            method = getattr(self._redis, op[0])
            if op[0] == "expire":
                results.append(method(op[1], op[2]))
            elif op[0] in ("zadd",):
                results.append(method(op[1], op[2]))
            elif op[0] == "zremrangebyscore":
                results.append(method(op[1], op[2], op[3]))
            elif op[0] == "zcard":
                results.append(method(op[1]))
        return results


class _InlineQueue:
    """Executes enqueued jobs synchronously in the caller's process."""

    def __init__(self) -> None:
        self.name = ANALYSIS_QUEUE_NAME

    def enqueue(self, func, *args, **kwargs):
        # RQ-only enqueue options (timeout, retry policy, result TTL, job
        # callbacks) have no meaning when the job runs right here, so they are
        # dropped rather than passed into the function as stray kwargs.
        for option in RQ_ENQUEUE_OPTIONS:
            kwargs.pop(option, None)
        return func(*args, **kwargs)

    @property
    def count(self) -> int:
        """Nothing is ever queued ahead of the caller in the inline queue."""
        return 0

    @property
    def is_inline(self) -> bool:
        return True


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


def analysis_retry_policy():
    """RQ retry policy for a queued analysis pass.

    A transient provider/network failure should be retried without operator
    involvement, but a permanent one (unknown pipeline, malformed area) must
    fail immediately: retrying it just burns the same quota on the same bad
    input. The caller-side check lives in
    ``app.services.analysis_runner.is_retryable``; this only decides *how* the
    retries are spaced.

    Backoff is linear-per-attempt from the configured base so a rate-limited
    provider gets breathing room rather than an immediate second hit.
    """
    from rq import Retry

    settings = get_settings()
    if settings.ANALYSIS_JOB_MAX_RETRIES <= 0:
        return None
    intervals = [
        settings.ANALYSIS_JOB_RETRY_BACKOFF_SECONDS * (attempt + 1)
        for attempt in range(settings.ANALYSIS_JOB_MAX_RETRIES)
    ]
    return Retry(max=settings.ANALYSIS_JOB_MAX_RETRIES, interval=intervals)


def enqueue_analysis(func, analysis_id: int) -> object:
    """Enqueue one analysis pass with the platform's shared job policy.

    Every call site (manual create, re-run, monitoring tick, bulk import) gets
    the identical timeout, retry and result-retention behaviour from one place,
    so a new entry point cannot accidentally skip the retry policy.
    """
    settings = get_settings()
    kwargs = {
        "job_timeout": settings.ANALYSIS_JOB_TIMEOUT_SECONDS,
        "result_ttl": settings.ANALYSIS_JOB_RESULT_TTL_SECONDS,
    }
    retry = analysis_retry_policy()
    if retry is not None:
        kwargs["retry"] = retry
    job = get_analysis_queue().enqueue(func, analysis_id, **kwargs)
    from app.job_metrics import record

    record("enqueued")
    return job

