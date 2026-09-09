"""API routes for AURORA"""

from .health import router as health_router
from .analysis import router as analysis_router
from .satellite import router as satellite_router
from .auth import router as auth_router
from .alerts import router as alerts_router
from .reports import router as reports_router

__all__ = [
    "health_router",
    "analysis_router",
    "satellite_router",
    "auth_router",
    "alerts_router",
    "reports_router",
]
