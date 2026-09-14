"""Health check endpoints.

/health/ is a liveness probe: "is the process up." It deliberately checks
nothing external -- if it depended on the DB, a brief DB blip would make
an orchestrator kill and restart otherwise-fine API processes, potentially
in a crash loop.

/health/ready is a readiness probe: "can this instance actually serve
traffic right now." It checks the two things every real request depends
on -- Postgres and Redis -- and returns 503 if either is unreachable, so
a load balancer / orchestrator can route around this instance instead of
sending it requests that would fail anyway.
"""

from fastapi import APIRouter, Response
from sqlalchemy import text

from app.config import get_settings
from app.database import SessionLocal
from app.queue import get_redis

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/")
async def health_check():
    """Liveness check -- no external dependencies."""
    return {
        "status": "healthy",
        "service": "AURORA Backend",
        "version": get_settings().APP_VERSION,
    }


@router.get("/ready")
async def readiness_check(response: Response):
    """Readiness check -- verifies Postgres and Redis are actually reachable."""
    checks: dict[str, str] = {}
    ready = True

    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 - report any failure, not just specific ones
        checks["database"] = f"error: {exc}"
        ready = False
    finally:
        db.close()

    try:
        get_redis().ping()
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"error: {exc}"
        ready = False

    if not ready:
        response.status_code = 503

    return {"ready": ready, "checks": checks}
