"""Platform capability registry.

Single index of everything AURORA can do, so a client or operator can ask
"what is this platform?" once instead of probing each subsystem's API.
New subsystems (robotics operators, constellation command, ISRU plant
control, ...) register here and the response grows without the core system
changing.  Exposed publicly at ``GET /system/capabilities``.

Design rule: importing this module must never import heavy subsystem code.
Subsystem metadata is static strings; live data (AI pipelines, satellite
sources) is fetched lazily inside ``build_capabilities()`` and failures
degrade gracefully instead of taking the whole endpoint down.
"""

from typing import Any, List

APP_VERSION = "0.2.0"

# Static index of platform subsystems.  `modules` lists the import path(s)
# that implement the capability; `status` reflects that the code is present
# and wired into the platform (not that hardware is operational).
SUBSYSTEMS: List[dict] = [
    {
        "id": "satellite",
        "name": "Satellite Data Providers",
        "description": (
            "Sentinel-2/1 + Landsat observation boundary with deterministic "
            "demo provider and live Copernicus Data Space Ecosystem (Sentinel "
            "Hub) integration."
        ),
        "modules": ["app.satellite"],
        "status": "active",
    },
    {
        "id": "ai",
        "name": "AI Analysis Pipelines",
        "description": (
            "Modular band-math pipelines (vegetation, land change, "
            "infrastructure, environmental, anomaly, wildfire, flood) with "
            "provenance-aware results and a governed model registry."
        ),
        "modules": ["app.ai"],
        "status": "active",
    },
    {
        "id": "robotics",
        "name": "Terrestrial Robotics",
        "description": (
            "Robot core abstractions, navigation, perception, control, "
            "simulation, telemetry and configuration.  Hardware-agnostic, "
            "simulation-first."
        ),
        "modules": ["app.robotics"],
        "status": "active",
    },
    {
        "id": "spacecraft",
        "name": "Spacecraft (CubeSat) Subsystems",
        "description": (
            "AURORA-1 3U CubeSat: ADCS, power, thermal, comms, imaging "
            "payload, flight software, mission timeline and spacecraft "
            "simulation."
        ),
        "modules": ["app.spacecraft"],
        "status": "active",
    },
    {
        "id": "multiplanetary",
        "name": "Multi-Planetary AI Architecture",
        "description": (
            "One autonomy brain for Earth, Moon, Mars and asteroids: layered "
            "decision stack (mission control .. human assistance), plus ops "
            "for comms delay, radiation, disconnected operation, fail-safe "
            "and command security."
        ),
        "modules": ["app.multiplanetary"],
        "status": "active",
    },
    {
        "id": "space_resources",
        "name": "Space Resource Program (ISRU)",
        "description": (
            "TRL-grounded technology registry, extraction process models, "
            "ISRU plant simulation, delivery-cost economics, prospecting "
            "planner and 8-phase program roadmap."
        ),
        "modules": ["app.space_resources"],
        "status": "active",
    },
]


def _list_ai_pipelines() -> List[dict]:
    try:
        from app.ai.registry import list_pipeline_descriptions

        return list_pipeline_descriptions()
    except Exception:  # pragma: no cover - registry failure must not kill the endpoint
        return []


def _list_satellite_sources() -> List[dict]:
    try:
        from app.config import get_settings
        from app.satellite.providers import REAL_SOURCE_IDS, get_satellite_provider

        provider = get_satellite_provider()
        settings = get_settings()
        return [
            {
                "id": source_id,
                "is_real": source_id in REAL_SOURCE_IDS,
                "active_provider": type(provider).__name__,
                "simulated": not (
                    settings.SENTINEL_CLIENT_ID and settings.SENTINEL_CLIENT_SECRET
                ),
            }
            for source_id in sorted(REAL_SOURCE_IDS)
        ]
    except Exception:  # pragma: no cover - provider failure must not kill the endpoint
        return []


def build_capabilities(version: str = APP_VERSION) -> dict:
    """Assemble the full capability snapshot for the current platform."""
    return {
        "platform": "AURORA",
        "version": version,
        "subsystems": SUBSYSTEMS,
        "ai_pipelines": _list_ai_pipelines(),
        "satellite_sources": _list_satellite_sources(),
    }