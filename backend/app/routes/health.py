"""Health check endpoints"""

from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "AURORA Backend",
        "version": get_settings().APP_VERSION,
    }


@router.get("/ready")
async def readiness_check():
    """Readiness check endpoint"""
    return {
        "ready": True,
        "message": "AURORA backend is ready to serve requests"
    }
