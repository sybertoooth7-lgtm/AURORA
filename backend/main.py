"""
AURORA Backend - Main Application Entry Point
Multi-planetary space technology company
AI + Robotics + Space infrastructure
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import get_settings
from app.database import engine, Base
from app import routes

settings = get_settings()


# Startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    # Startup
    print("🚀 AURORA Backend starting...")
    Base.metadata.create_all(bind=engine)
    print("✅ Database initialized")
    
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

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(routes.health_router)
app.include_router(routes.analysis_router)
app.include_router(routes.satellite_router)


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
