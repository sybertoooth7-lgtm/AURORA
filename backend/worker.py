"""RQ worker entrypoint for AURORA background jobs.

Runs as its own process, separate from the API (see the `worker` service in
docker-compose.yml). Listens on the "analysis" queue and executes
app.services.analysis_runner.run_analysis jobs enqueued by POST /analysis/,
the re-run endpoint, and the monitoring scheduler.

Run locally with:
    python worker.py

Operators can bound the process without editing code:
    python worker.py --burst              # drain the queue, then exit
    python worker.py --max-jobs 500       # exit after 500 jobs (recycles a
                                          # long-lived process's memory)
    python worker.py --queue other        # consume a different queue name
"""

import argparse
import os
import sys

from rq import Queue, Worker

from app.ai.registry import build_workspace_pipelines
from app.config import get_settings
from app.job_metrics import record
from app.logging_conf import get_logger, setup_logging
from app.queue import ANALYSIS_QUEUE_NAME, get_redis

setup_logging()
logger = get_logger(__name__)


def _prepare() -> None:
    """Import pipeline modules eagerly so jobs don't pay cold-import cost."""
    build_workspace_pipelines()
    logger.info("Worker ready; pipelines registered")


def _on_job_failure(job, *args, **kwargs) -> None:
    """Count executions that ended abnormally at the worker boundary.

    ``run_analysis`` records its own outcome, but a job killed by timeout, or
    one whose worker died mid-run, never reaches that code path. Registered in
    the worker's exception handlers so throughput accounting does not silently
    lose them.
    """
    record("failed")
    logger.error(
        "job failed in worker",
        extra_keys={"job_id": job.id, "origin": getattr(job, "origin", None)},
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AURORA background job worker")
    parser.add_argument("--queue", default=ANALYSIS_QUEUE_NAME, help="queue name to consume")
    parser.add_argument("--burst", action="store_true", help="drain the queue and exit")
    parser.add_argument(
        "--max-jobs",
        type=int,
        default=0,
        help="exit after this many jobs (0 = run until signalled)",
    )
    parser.add_argument(
        "--max-idle-time",
        type=int,
        default=0,
        help="exit after this many seconds idle (0 = never)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _prepare()

    settings = get_settings()
    connection = get_redis()
    queue = Queue(args.queue, connection=connection)
    # RQ installs its own SIGTERM/SIGINT handlers inside work(), which is what
    # puts an in-flight job back on the queue during a container stop -- so the
    # worker is not given a competing handler of its own.
    worker = Worker(
        [queue],
        connection=connection,
        default_result_ttl=settings.ANALYSIS_JOB_RESULT_TTL_SECONDS,
        exception_handlers=[_on_job_failure],
    )

    logger.info(
        "RQ worker starting",
        extra_keys={
            "queues": [args.queue],
            "burst": args.burst,
            "max_jobs": args.max_jobs,
            "result_ttl": settings.ANALYSIS_JOB_RESULT_TTL_SECONDS,
            "pid": os.getpid(),
        },
    )

    worker.work(
        burst=args.burst,
        max_jobs=args.max_jobs or None,
        max_idle_time=args.max_idle_time or None,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
