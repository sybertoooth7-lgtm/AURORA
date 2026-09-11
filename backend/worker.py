"""RQ worker entrypoint for AURORA background jobs.

Runs as its own process, separate from the API (see the `worker` service in
docker-compose.yml). Listens on the "analysis" queue and executes
app.services.analysis_runner.run_analysis jobs enqueued by POST /analysis/.

Run locally with:
    python worker.py
"""

from rq import Worker

from app.ai.registry import build_workspace_pipelines
from app.logging_conf import get_logger, setup_logging
from app.queue import ANALYSIS_QUEUE_NAME, get_redis

setup_logging()
logger = get_logger(__name__)


def _prepare() -> None:
    """Import pipeline modules eagerly so jobs don't pay cold-import cost."""
    build_workspace_pipelines()
    logger.info("Worker ready; pipelines registered")


if __name__ == "__main__":
    _prepare()
    worker = Worker([ANALYSIS_QUEUE_NAME], connection=get_redis())
    logger.info("RQ worker starting", extra_keys={"queues": [ANALYSIS_QUEUE_NAME]})
    worker.work()