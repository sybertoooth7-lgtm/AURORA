"""Platform-wide system endpoints: capabilities index and job operations.

Kept separate from /health because a capability snapshot is a product-level
answer ("what can this platform do?") whereas health is an operations-level
answer ("is this instance up?").
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.capabilities import build_capabilities
from app.config import get_settings
from app.database import get_db
from app.job_metrics import snapshot
from app.models.analysis import Analysis
from app.queue import get_analysis_queue
from app.security import require_admin

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/capabilities")
def platform_capabilities():
    """Public index of every subsystem, AI pipeline and satellite source.

    No auth: it is product metadata (like OpenAPI), not operational state.
    Subsystems are listed statically from the registry; AI pipelines and
    satellite sources are resolved lazily and degrade gracefully if their
    backing packages cannot load.
    """
    return build_capabilities(version=get_settings().APP_VERSION)


@router.get("/jobs", dependencies=[Depends(require_admin)])
def job_pipeline_status(db: Session = Depends(get_db)):
    """Operational view of the background analysis pipeline (operators only).

    Queue counters alone are not enough: a job lost to a worker crash leaves
    its analysis stuck in ``pending`` forever, which looks like an idle system
    rather than a broken one. Both are reported here -- Redis-side throughput
    and the DB rows that never came back out.
    """
    settings = get_settings()
    queue = get_analysis_queue()
    depth = queue.count

    stale_before = datetime.now(UTC) - timedelta(
        seconds=max(settings.ANALYSIS_JOB_TIMEOUT_SECONDS * 3, 900)
    )
    stale = (
        db.query(Analysis)
        .filter(
            Analysis.status.in_(("pending", "processing")),
            or_(
                Analysis.created_at.is_(None),
                Analysis.created_at < stale_before.replace(tzinfo=None),
            ),
        )
        .order_by(Analysis.created_at.asc())
        .limit(50)
        .all()
    )

    return {
        "queue": {
            "name": getattr(queue, "name", None),
            "inline_execution": getattr(queue, "is_inline", False),
            "depth": depth,
        },
        "job_policy": {
            "timeout_seconds": settings.ANALYSIS_JOB_TIMEOUT_SECONDS,
            "max_retries": settings.ANALYSIS_JOB_MAX_RETRIES,
            "retry_backoff_seconds": settings.ANALYSIS_JOB_RETRY_BACKOFF_SECONDS,
            "result_ttl_seconds": settings.ANALYSIS_JOB_RESULT_TTL_SECONDS,
        },
        "observation_cache": {
            "ttl_seconds": settings.OBSERVATION_CACHE_TTL_SECONDS,
            "enabled": settings.OBSERVATION_CACHE_TTL_SECONDS > 0,
        },
        "monitoring": {
            "tick_seconds": settings.MONITOR_SCHEDULER_TICK_SECONDS,
            "min_interval_minutes": settings.MONITOR_MIN_INTERVAL_MINUTES,
            "monitored_areas": db.query(Analysis)
            .filter(Analysis.monitor_interval_minutes.is_not(None))
            .count(),
        },
        "today": snapshot(queue_depth=depth),
        "stuck_analyses": [
            {
                "id": row.id,
                "user_id": row.user_id,
                "status": row.status,
                "analysis_type": row.analysis_type.value,
                "created_at": row.created_at,
            }
            for row in stale
        ],
    }

