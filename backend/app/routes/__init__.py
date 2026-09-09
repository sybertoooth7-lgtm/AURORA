"""API routes for AURORA"""

from .health import router as health_router
from .analysis import router as analysis_router
from .satellite import router as satellite_router

__all__ = [
    "health_router",
    "analysis_router",
    "satellite_router",
]
