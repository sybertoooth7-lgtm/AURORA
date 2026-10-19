"""Shared envelope for the Stage 0 division simulations.

The spacecraft, multi-planetary, space-resource, constellation and mission
planning engines are architecture and model code: deterministic, offline, no
hardware and no live telemetry behind them. Their endpoints therefore say so
in the payload itself rather than in a README nobody reads -- every response
carries the provenance flag and the specific things its model leaves out, so
a simulated number cannot be forwarded as a measurement.
"""

from pydantic import BaseModel, Field

from app.ai.base import Provenance

STAGE = "stage_0_simulation"


class SimulationResponse(BaseModel):
    """Base for every division endpoint response."""

    provenance: Provenance = Field(
        default=Provenance.SIMULATED,
        description=(
            "Model code, not hardware or live space-domain data. An endpoint "
            "that reports the platform's own observed state overrides this."
        ),
    )
    stage: str = Field(
        default=STAGE,
        description="Maturity of the code behind the response.",
    )
    model_limitations: list[str] = Field(
        default_factory=list,
        description="What this specific model does not account for.",
    )
