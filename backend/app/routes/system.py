"""Platform-wide system endpoints: capabilities index.

Kept separate from /health because a capability snapshot is a product-level
answer ("what can this platform do?") whereas health is an operations-level
answer ("is this instance up?").
"""

from fastapi import APIRouter

from app.capabilities import build_capabilities
from app.config import get_settings

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/capabilities")
def platform_capabilities():
    """Public index of every subsystem, AI pipeline and satellite source.

    No auth: it is product metadata (like OpenAPI), not operational state.
    Subsystems are listed statically from the registry; AI pipelines and
    satellite sources are resolved lazily and degrade gracefully if their
    backing packages cannot load.
    """
    return build_capabilities(version=get_settings().APP_VERSION)