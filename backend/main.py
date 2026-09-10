"""
AURORA Backend - Main Application Entry Point
Multi-planetary space technology company
AI + Robotics + Space infrastructure
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from redis.exceptions import RedisError
from app.config import get_settings
from app import routes
from app.rate_limit import record_request

settings = get_settings()


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
    print("🚀 AURORA Backend starting...")

    yield

    # Shutdown
    print("🛑 AURORA Backend shutting down...")


# Create FastAPI app
app = FastAPI(
    title="AURORA Backend",
    description="Space Intelligence Platform - AI + Satellite Data + Geospatial Analytics",
    version="0.1.0",
    lifespan=lifespan
)

@app.middleware("http")
async def rate_limit(request: Request, call_next):
    """Apply one shared atomic limit across all API instances."""
    client_key = request.client.host if request.client else "unknown"
    try:
        request_count, retry_after = await record_request(client_key)
    except RedisError:
        return JSONResponse(
            status_code=503,
            content={"detail": "Rate limiter unavailable"},
        )
    if request_count > settings.RATE_LIMIT_REQUESTS:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded"},
            headers={"Retry-After": str(retry_after)},
        )
    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(settings.RATE_LIMIT_REQUESTS)
    response.headers["X-RateLimit-Remaining"] = str(
        max(settings.RATE_LIMIT_REQUESTS - request_count, 0)
    )
    return response

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(routes.health_router)
app.include_router(routes.analysis_router)
app.include_router(routes.satellite_router)
app.include_router(routes.auth_router)
app.include_router(routes.alerts_router)
app.include_router(routes.reports_router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "AURORA",
        "description": "Space Intelligence Platform",
        "status": "operational",
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_RELOAD
    )
