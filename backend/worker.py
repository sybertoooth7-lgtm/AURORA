"""RQ worker entrypoint for AURORA background jobs.

Runs as its own process, separate from the API (see the `worker` service in
docker-compose.yml). Listens on the "analysis" queue and executes
app.services.analysis_runner.run_analysis jobs enqueued by POST /analysis/.

Run locally with:
    python worker.py
"""

from rq import Worker

from app.queue import ANALYSIS_QUEUE_NAME, get_redis

if __name__ == "__main__":
    worker = Worker([ANALYSIS_QUEUE_NAME], connection=get_redis())
    worker.work()
