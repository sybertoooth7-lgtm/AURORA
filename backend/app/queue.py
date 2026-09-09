"""Redis-backed job queue for slow/long-running work (analysis runs).

Replaces FastAPI's BackgroundTasks for this purpose: BackgroundTasks run
in-process after the response is sent, so a slow satellite-provider call
blocks that worker process's event loop, and any job still running when the
process restarts (deploy, crash, OOM) is silently lost. RQ jobs live in
Redis, run in a separate `worker.py` process, and survive an API restart.
"""

from functools import lru_cache

from redis import Redis
from rq import Queue

from app.config import get_settings

ANALYSIS_QUEUE_NAME = "analysis"


@lru_cache()
def get_redis() -> Redis:
    """Return a cached Redis connection built from settings.REDIS_URL."""
    return Redis.from_url(get_settings().REDIS_URL)


@lru_cache()
def get_analysis_queue() -> Queue:
    """Return the (cached) queue that analysis jobs are enqueued onto."""
    return Queue(ANALYSIS_QUEUE_NAME, connection=get_redis())
