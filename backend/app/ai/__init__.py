"""AI/ML modules for AURORA.

Public surface:
    get_pipeline(analysis_type) -> Pipeline
    list_pipeline_descriptions() -> list[dict]
    PipelineResult / Pipeline / ModelRef / Provenance
    infer(analysis_type, observation[, history]) -> PipelineResult

Importing this package registers the default workspace pipelines (idempotent).
"""

from app.ai.base import (
    Label,
    ModelKind,
    ModelRef,
    Pipeline,
    PipelineExecutionError,
    PipelineResult,
    Provenance,
    provenance_for_observation,
)
from app.ai.registry import (
    get_pipeline,
    get_registry,
    list_pipeline_descriptions,
    list_pipelines,
)

__all__ = [
    "get_pipeline",
    "get_registry",
    "list_pipeline_descriptions",
    "list_pipelines",
    "Label",
    "ModelKind",
    "ModelRef",
    "Pipeline",
    "PipelineExecutionError",
    "PipelineResult",
    "Provenance",
    "provenance_for_observation",
]


def infer(analysis_type, observation, history=None) -> PipelineResult:
    """Highest-level helper: resolve a pipeline and execute it.

    Used by the analysis runner (RQ worker) and by POST /ai/infer.
    """
    pipeline = get_pipeline(analysis_type)
    return pipeline.run(observation, history=history)