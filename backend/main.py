"""
AURORA Backend - Main Application Entry Point
Multi-planetary space technology company
AI + Robotics + Space infrastructure
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from collections import OrderedDict, deque
import time
import traceback

from app.config import get_settings
from app import routes
from app.exceptions import AuroraError
from app.logging_conf import get_logger, setup_logging

settings = get_settings()
setup_logging()
logger = get_logger(__name__)


# Startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    # Startup
    # Schema is owned by Alembic now (see alembic/ and README) -- run
    # `alembic upgrade head` before starting the app (the Dockerfile does
    # this automatically). We deliberately don't run migrations here: with
    # multiple API replicas, every instance hitting create_all/upgrade on
    # startup races the others.
    logger.info("AURORA Backend starting (environment=%s)", settings.ENVIRONMENT)
    # Register AI pipelines eagerly so a misconfiguration is loud at startup,
    # not on the first analysis request.
    from app.ai.registry import build_workspace_pipelines, list_pipeline_descriptions

    build_workspace_pipelines()
    logger.info(
        "AI pipelines registered",
        extra_keys={"pipelines": [p["name"] for p in list_pipeline_descriptions()]},
    )

    yield

    # Shutdown
    logger.info("AURORA Backend shutting down")


# Create FastAPI app
app = FastAPI(
    title="AURORA Backend",
    description="Space Intelligence Platform - AI + Satellite Data + Geospatial Analytics",
    version="0.2.0",
    lifespan=lifespan
)

rate_limit_state: "OrderedDict[tuple, deque]" = OrderedDict()
MAX_TRACKED_RATE_LIMIT_KEYS = 50_000


@app.middleware("http")
async def request_logging(request: Request, call_next):
    """Log every request with method, path, status, and duration.

    Do this first (outermost) so even rate-limited/errored requests are
    accounted for in the same structured log stream.
    """
    started = time.monotonic()
    response = await call_next(request)
    elapsed_ms = (time.monotonic() - started) * 1000
    logger.info(
        "request",
        extra_keys={
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round(elapsed_ms, 1),
        },
    )
    return response


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    """Apply a small process-local limit until Redis-backed limiting is added.

    Auth endpoints (/auth/token, /auth/register) get their own, much
    stricter budget than general API traffic -- 120 req/min is reasonable
    for normal API use but far too generous for a login endpoint. This is
    still just a per-IP throttle on top of the per-account lockout in
    app.security; it doesn't replace it.
    """
    now = time.monotonic()
    is_auth_endpoint = request.url.path in ("/auth/token", "/auth/register")
    limit = settings.AUTH_RATE_LIMIT_REQUESTS if is_auth_endpoint else settings.RATE_LIMIT_REQUESTS
    window = (
        settings.AUTH_RATE_LIMIT_WINDOW_SECONDS if is_auth_endpoint else settings.RATE_LIMIT_WINDOW_SECONDS
    )

    client_host = request.client.host if request.client else "unknown"
    key = (client_host, is_auth_endpoint)

    bucket = rate_limit_state.get(key)
    if bucket is None:
        bucket = deque()

    cutoff = now - window
    while bucket and bucket[0] <= cutoff:
        bucket.popleft()

    if len(bucket) >= limit:
        rate_limit_state[key] = bucket
        rate_limit_state.move_to_end(key)
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})

    bucket.append(now)
    rate_limit_state[key] = bucket
    rate_limit_state.move_to_end(key)

    # Bound total memory: this is a per-process in-memory limiter, so
    # without a cap it accumulates one entry per distinct client IP it has
    # ever seen, forever. Evicting the least-recently-active client keeps
    # this bounded regardless of traffic volume; an evicted client just
    # gets a fresh bucket on its next request, which is a fine trade-off
    # for a stopgap limiter.
    while len(rate_limit_state) > MAX_TRACKED_RATE_LIMIT_KEYS:
        rate_limit_state.popitem(last=False)

    return await call_next(request)


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Error handling ---------------------------------------------------------
# Expected application errors (app.exceptions) map to consistent JSON with a
# `code`; validation errors keep FastAPI's default 422 shape but cleaned;
# anything else returns a generic 500 without leaking internals to clients
# while logging the full traceback server-side.

@app.exception_handler(AuroraError)
async def aurora_error_handler(request: Request, exc: AuroraError):
    logger.log(
        getattr(exc, "log_level", "warning").upper(),
        "aurora_error",
        extra_keys={"code": exc.code, "path": request.url.path},
        exc_info=exc if isinstance(exc, (KeyError,)) or settings.DEBUG else None,
    )
    return JSONResponse(status_code=exc.status_code, content=exc.to_response())


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    logger.warning("validation_error", extra_keys={"path": request.url.path, "errors": exc.errors()})
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Request validation failed",
            "code": "validation_failed",
            "errors": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.error(
        "unhandled_exception",
        exc_info=(type(exc), exc, exc.__traceback__),
        extra_keys={"path": request.url.path},
    )
    if settings.DEBUG:
        detail = "".join(traceback.format_exception_only(type(exc), exc)).strip()
    else:
        detail = "Internal server error"
    return JSONResponse(status_code=500, content={"detail": detail, "code": "internal_error"})


# Include routers
app.include_router(routes.health_router)
app.include_router(routes.analysis_router)
app.include_router(routes.satellite_router)
app.include_router(routes.auth_router)
app.include_router(routes.alerts_router)
app.include_router(routes.reports_router)
app.include_router(routes.ai_router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "AURORA",
        "description": "Space Intelligence Platform",
        "status": "operational",
        "version": "0.2.0",
        "docs": "/docs",
        "ai": "/ai/pipelines",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_RELOAD
    )