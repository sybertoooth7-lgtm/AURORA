"""API routes for AURORA"""

from .ai import router as ai_router
from .alerts import router as alerts_router
from .analysis import router as analysis_router
from .auth import router as auth_router
from .health import router as health_router
from .insurance import router as insurance_router
from .onboarding import router as onboarding_router
from .reports import router as reports_router
from .robotics import router as robotics_router
from .satellite import router as satellite_router
from .system import router as system_router

__all__ = [
    "health_router",
    "analysis_router",
    "satellite_router",
    "auth_router",
    "alerts_router",
    "reports_router",
    "ai_router",
    "system_router",
    "insurance_router",
    "robotics_router",
    "onboarding_router",
]
