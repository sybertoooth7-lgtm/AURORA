"""Core abstractions for the AURORA AI pipeline system.

Design goals
------------
* Every analysis type resolves to a *pipeline* -- a modular, named unit that
  takes one satellite observation (plus optional history) and produces a
  structured result with severity, confidence, findings, and provenance.
* Pipelines are deliberately backend-agnostic. The current generation is
  lightweight (band-math / statistical indices computed from area-level
  statistics emitted by the satellite provider), but the same interface is
  what future modules (pixel-level ML segmentation, autonomous robotics
  perception, spacecraft/planetary surface mapping) will implement -- the
  registry and the API contract stay identical.
* Provenance is part of every result: a result produced from the real
  Sentinel-2 provider is marked ``real``; anything from the deterministic
  demo provider is ``simulated``. Simulated results are never surfaced as
  real, and model status separates ``prototype`` (to be validated) from
  ``production`` (validated for operational use).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from app.models.analysis import AnalysisType
from app.satellite.providers import SatelliteObservation


class Provenance(str, Enum):
    """Where a result's underlying data came from."""

    REAL = "real"
    SIMULATED = "simulated"


class ModelKind(str, Enum):
    """Maturity of the model/approach behind a pipeline.

    ``PROTOTYPE`` means the approach is implemented and works but was not
    yet validated against ground truth for operational use. ``PRODUCTION``
    means it has been validated and may be used for customer outputs.
    This is declared per pipeline and reinforced by model-management
    endpoints (`POST /ai/models/{id}/promote`).
    """

    PROTOTYPE = "prototype"
    PRODUCTION = "production"


@dataclass(frozen=True)
class ModelRef:
    """Identity of the model/approach backing one pipeline result."""

    name: str
    version: str
    kind: ModelKind

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "version": self.version, "kind": self.kind.value}


@dataclass
class Label:
    """A geospatial assertion produced by a pipeline (area-level for now).

    The MVP works on area-aggregated statistics, so labels are area-wide
    classifications rather than per-pixel polygons. Future pixel-level
    stages will attach real geometries here.
    """

    class_: str
    confidence: float
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    """Structured output of one pipeline run over one observation."""

    analysis_type: AnalysisType
    severity: float  # 0..1
    confidence: float  # 0..1
    findings: list[str]
    metrics: dict[str, float | None]
    provenance: Provenance
    source: str
    image_id: str
    acquired_at: datetime
    model: ModelRef
    preprocessing: list[str] = field(default_factory=list)
    labels: list[Label] = field(default_factory=list)
    warning: str | None = None
    history_length: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_type": self.analysis_type.value,
            "severity": round(self.severity, 4),
            "confidence": round(self.confidence, 4),
            "findings": self.findings,
            "metrics": self.metrics,
            "provenance": self.provenance.value,
            "simulated": self.provenance == Provenance.SIMULATED,
            "source": self.source,
            "image_id": self.image_id,
            "acquired_at": self.acquired_at.isoformat(),
            "model": self.model.to_dict(),
            "preprocessing": self.preprocessing,
            "labels": [
                {
                    "class": label.class_,
                    "confidence": round(label.confidence, 4),
                    "attributes": label.attributes,
                }
                for label in self.labels
            ],
            "warning": self.warning,
            "history_length": self.history_length,
        }

    def to_metadata(self) -> dict[str, Any]:
        """JSON-safe dict for persisting in ``analysis_results.metadata``."""
        return self.to_dict()


def provenance_for_observation(observation: SatelliteObservation) -> Provenance:
    """Derive provenance from the observation source.

    The demo provider always reports source="demo"; every real sensor in
    ``REAL_SOURCE_IDS`` counts as real. Anything unknown is treated as real
    *data* only when the provider says so -- unknown sources degrade to
    simulated to avoid ever presenting unknown-origin data as verified.
    """
    if observation.is_simulated:
        return Provenance.SIMULATED
    return Provenance.REAL


class Pipeline(ABC):
    """Base class every analysis pipeline implements.

    A pipeline is stateless and re-entrant (safe for concurrent worker
    processes): all configuration lives on the instance at construction,
    and ``run`` closes over only the provided observation(s).
    """

    name: str = ""
    description: str = ""
    handles: frozenset[AnalysisType] = frozenset()
    model: ModelRef = ModelRef(name="base", version="0.0.0", kind=ModelKind.PROTOTYPE)
    preprocessing: list[str] = ["no preprocessing (area-aggregated statistics input)"]

    @abstractmethod
    def run(
        self,
        observation: SatelliteObservation,
        history: list[SatelliteObservation] | None = None,
    ) -> PipelineResult:
        """Run inference over one (latest) observation and optionally its history."""

    def describe(self) -> dict[str, Any]:
        """Registry-facing description of the pipeline."""
        return {
            "name": self.name,
            "description": self.description,
            "handles": sorted(t.value for t in self.handles),
            "model": self.model.to_dict(),
            "preprocessing": self.preprocessing,
            "data_requirements": {
                "history_supported": self.supports_history(),
                "min_inputs": sorted(self.handles),
            },
        }

    def supports_history(self) -> bool:
        """Whether the pipeline uses time-series history when available."""
        return False


class PipelineExecutionError(RuntimeError):
    """Raised when a pipeline cannot produce a result from the given input."""
