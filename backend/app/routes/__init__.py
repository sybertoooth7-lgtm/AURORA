"""API routes for AURORA"""

from .admin import router as admin_router
from .ai import router as ai_router
from .alerts import router as alerts_router
from .analysis import router as analysis_router
from .api_keys import router as api_keys_router
from .auth import router as auth_router
from .crop import router as crop_router
from .health import router as health_router
from .insurance import router as insurance_router
from .mission_planning import router as mission_planning_router
from .multiplanetary import router as multiplanetary_router
from .onboarding import router as onboarding_router
from .reports import router as reports_router
from .robotics import router as robotics_router
from .satellite import router as satellite_router
from .space_division import router as space_division_router
from .space_resources import router as space_resources_router
from .spacecraft import router as spacecraft_router
from .system import router as system_router

__all__ = [
    "health_router",
    "analysis_router",
    "satellite_router",
    "auth_router",
    "api_keys_router",
    "alerts_router",
    "reports_router",
    "ai_router",
    "crop_router",
    "system_router",
    "insurance_router",
    "robotics_router",
    "onboarding_router",
    "admin_router",
    "spacecraft_router",
    "space_division_router",
    "space_resources_router",
    "multiplanetary_router",
    "mission_planning_router",
]
