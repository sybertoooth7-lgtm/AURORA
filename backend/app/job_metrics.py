"""Counters and a recent-failure trail for background analysis jobs.

The platform already had a queue (``app.queue``) and a scheduler
(``app.monitoring``), but no way to answer the operational question they
create: *is work actually getting through, and what is failing?* Without this,
a worker that silently loses every job looks identical to an idle one.

Everything lives in Redis next to the queue itself rather than in a table:
these are high-frequency, low-value-per-row counters, and a DB table written on
every job completion would add a row per analysis to the same database the
analyses already stress. Keys are grouped under ``jobs:`` and expire, so the
footprint does not grow with traffic.

Demo mode reuses the in-memory Redis substitute, so the same code path is
exercised locally and in production.
"""

import json
from datetime import UTC, datetime

from app.logging_conf import get_logger
from app.queue import get_redis

logger = get_logger(__name__)

COUNTER_TTL_SECONDS = 60 * 60 * 24 * 35
RECENT_FAILURES_KEY = "jobs:recent_failures"
RECENT_FAILURES_LIMIT = 25

COUNTER_NAMES = ("enqueued", "completed", "failed", "retried", "cache_hit", "cache_miss")


def _counter_key(name: str, day: str) -> str:
    return f"jobs:counter:{name}:{day}"


def _today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _as_int(raw) -> int:
    if raw is None:
        return 0
    return int(raw.decode() if isinstance(raw, bytes) else raw)


def record(name: str, amount: int = 1) -> None:
    """Bump today's counter for `name`.

    Deliberately cannot raise: this is called from the worker's job boundary,
    and a metrics hiccup must not turn a successful analysis into a failure.
    """
    day = _today()
    key = _counter_key(name, day)
    try:
        redis = get_redis()
        total = redis.incr(key, amount)
        if total == amount:
            redis.expire(key, COUNTER_TTL_SECONDS)
    except Exception:  # noqa: BLE001 - observability is not on the critical path
        logger.warning("job counter failed", extra_keys={"counter": name})


def counter(name: str, day: str | None = None) -> int:
    """Read today's (or one specific day's) counter; 0 when unset."""
    return _as_int(get_redis().get(_counter_key(name, day or _today())))


def _read_recent() -> list[dict]:
    raw = get_redis().get(RECENT_FAILURES_KEY)
    if not raw:
        return []
    try:
        payload = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
    except (TypeError, ValueError):
        return []
    return payload if isinstance(payload, list) else []


def record_failure(analysis_id: int, error: str, attempt: int) -> None:
    """Keep a short, newest-first trail of job failures for the ops endpoint.

    Stored as one JSON value rather than a Redis list so the in-memory
    substitute only needs ``get``/``set`` -- the operational need is "what
    broke recently", not an unbounded log.
    """
    entry = {
        "analysis_id": analysis_id,
        "error": error[:500],
        "attempt": attempt,
        "at": datetime.now(UTC).isoformat(),
    }
    try:
        trimmed = [entry, *_read_recent()][:RECENT_FAILURES_LIMIT]
        get_redis().set(
            RECENT_FAILURES_KEY, json.dumps(trimmed), ex=COUNTER_TTL_SECONDS
        )
    except Exception:  # noqa: BLE001 - observability is not on the critical path
        logger.warning(
            "job failure trail write failed", extra_keys={"analysis_id": analysis_id}
        )


def recent_failures(limit: int = RECENT_FAILURES_LIMIT) -> list[dict]:
    return _read_recent()[:limit]


def snapshot(queue_depth: int | None = None) -> dict:
    """Operational view of the job pipeline for the current day."""
    counters = {name: counter(name) for name in COUNTER_NAMES}
    failures = counters["failed"]
    completions = counters["completed"]
    attempted = completions + failures
    return {
        "day": _today(),
        "counters": counters,
        "queue_depth": queue_depth,
        "success_rate": round(completions / attempted, 4) if attempted else None,
        "recent_failures": recent_failures(),
    }
