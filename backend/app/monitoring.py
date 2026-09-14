"""Scheduled re-checks for monitored areas (continuous monitoring).

Every ``MONITOR_SCHEDULER_TICK_SECONDS`` a daemon thread started by the API
lifespan finds analyses that have a cadence set (``monitor_interval_minutes``
non-null), are idle (not pending/processing), belong to an active account,
and whose ``next_check_at`` has passed. Each due area is re-enqueued onto the
same RQ queue the normal worker consumes, so the actual observation + pipeline
work runs in ``worker.py`` exactly like a manual run -- the scheduler only
decides *when*, never how.

Multiple API replicas are safe: every due area is claimed with a short-lived
Redis ``SET NX`` lock keyed by analysis id, so only one process launches each
pass and a crashed claim holder (TTL shorter than a stuck worker) doesn't
permanently wedge the area.
"""

import threading
from datetime import UTC, datetime, timedelta

from app.config import get_settings
from app.database import SessionLocal
from app.logging_conf import get_logger
from app.models.analysis import Analysis
from app.models.user import User
from app.queue import get_analysis_queue, get_redis
from app.services.analysis_runner import run_analysis

logger = get_logger(__name__)


class MonitoringScheduler:
    """Background loop that enqueues due re-checks of monitored areas."""

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="monitoring-scheduler", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Ask the loop to exit; it wakes up at the next tick."""
        self._stop.set()

    def _loop(self) -> None:
        settings = get_settings()
        while not self._stop.wait(timeout=settings.MONITOR_SCHEDULER_TICK_SECONDS):
            try:
                self._tick()
            except Exception:  # noqa: BLE001 - daemon boundary: keep running
                logger.error("monitoring scheduler tick failed", exc_info=True)

    def _tick(self) -> None:
        settings = get_settings()
        now = datetime.now(UTC)
        db = SessionLocal()
        try:
            due = (
                db.query(Analysis)
                .join(User, Analysis.user_id == User.id)
                .filter(
                    User.is_active.is_(True),
                    Analysis.monitor_interval_minutes.isnot(None),
                    Analysis.next_check_at.isnot(None),
                    Analysis.next_check_at <= now,
                    Analysis.status.notin_(("pending", "processing")),
                )
                .all()
            )
            redis = get_redis()
            for analysis in due:
                lock_key = f"monitor:{analysis.id}"
                if not redis.set(
                    lock_key,
                    "1",
                    ex=settings.MONITOR_LOCK_TTL_SECONDS,
                    nx=True,
                ):
                    continue
                cadence = timedelta(minutes=analysis.monitor_interval_minutes)
                try:
                    analysis.status = "pending"
                    analysis.next_check_at = now + cadence
                    db.commit()
                    get_analysis_queue().enqueue(
                        run_analysis,
                        analysis.id,
                        job_timeout=settings.ANALYSIS_JOB_TIMEOUT_SECONDS,
                    )
                    logger.info(
                        "monitoring check scheduled",
                        extra_keys={"analysis_id": analysis.id},
                    )
                except Exception:  # noqa: BLE001 - claim one area, not the tick
                    db.rollback()
                    logger.error(
                        "monitoring check scheduling failed",
                        extra_keys={"analysis_id": analysis.id},
                        exc_info=True,
                    )
        finally:
            db.close()


scheduler = MonitoringScheduler()
