"""Pipeline registry: the single place analysis types resolve to pipelines.

Kept intentionally simple -- a process-local registry populated at import
time. Pipelines are stateless, so the registry is safe to share across the
API process and every RQ worker process (each process builds its own
registry, deterministically, from the same code).
"""

from dataclasses import dataclass

from app.ai.base import Pipeline
from app.models.analysis import AnalysisType


class UnknownPipelineError(KeyError):
    """Raised when no pipeline handles the requested analysis type."""


@dataclass
class RegisteredPipeline:
    pipeline: Pipeline
    active: bool = True


class PipelineRegistry:
    def __init__(self) -> None:
        self._pipelines: dict[str, RegisteredPipeline] = {}
        self._by_type: dict[AnalysisType, Pipeline] = {}

    def register(self, pipeline: Pipeline, active: bool = True) -> None:
        if not pipeline.name or not pipeline.handles:
            raise ValueError("Pipeline must define a name and at least one handled analysis type")
        if pipeline.name in self._pipelines:
            raise ValueError(f"Pipeline '{pipeline.name}' already registered")
        self._pipelines[pipeline.name] = RegisteredPipeline(pipeline=pipeline, active=active)
        for analysis_type in pipeline.handles:
            if analysis_type in self._by_type and self._by_type[analysis_type].name != pipeline.name:
                raise ValueError(
                    f"Analysis type {analysis_type.value} is already handled by "
                    f"'{self._by_type[analysis_type].name}'"
                )
            self._by_type[analysis_type] = pipeline

    def resolve(self, analysis_type: AnalysisType) -> Pipeline:
        """Return the active pipeline for an analysis type or raise."""
        pipeline = self._by_type.get(analysis_type)
        if pipeline is None or not self._pipelines[pipeline.name].active:
            raise UnknownPipelineError(
                f"No active pipeline handles analysis type '{analysis_type.value}'"
            )
        return pipeline

    def get(self, name: str) -> RegisteredPipeline | None:
        return self._pipelines.get(name)

    def list_active(self) -> list[RegisteredPipeline]:
        return [entry for entry in self._pipelines.values() if entry.active]

    def list_descriptions(self) -> list[dict]:
        return sorted(
            (entry.pipeline.describe() for entry in self.list_active()),
            key=lambda info: info["name"],
        )


_registry = PipelineRegistry()


def build_workspace_pipelines() -> None:
    """Register all pipelines shipped in this workspace.

    Importing this registers the standard set exactly once; calling it again
    is harmless but idempotent is not guaranteed if the set changes between
    calls -- intended for app/worker startup and tests only.
    """
    from app.ai.anomaly import AnomalyPipeline
    from app.ai.environmental import EnvironmentalPipeline
    from app.ai.flood import FloodPipeline
    from app.ai.infrastructure import InfrastructurePipeline
    from app.ai.insurance_index import InsuranceIndexPipeline
    from app.ai.land_change import LandChangePipeline
    from app.ai.robotics_inspection import RoboticsInspectionPipeline
    from app.ai.vegetation import VegetationPipeline
    from app.ai.wildfire import WildfirePipeline

    for pipeline in (
        VegetationPipeline(),
        LandChangePipeline(),
        InfrastructurePipeline(),
        EnvironmentalPipeline(),
        AnomalyPipeline(),
        WildfirePipeline(),
        FloodPipeline(),
        InsuranceIndexPipeline(),
        RoboticsInspectionPipeline(),
    ):
        if not _registry.get(pipeline.name):
            _registry.register(pipeline)


def get_registry() -> PipelineRegistry:
    """Return the process-wide registry (populated on first use)."""
    build_workspace_pipelines()
    return _registry


def get_pipeline(analysis_type: AnalysisType) -> Pipeline:
    """Convenience helper behind the analysis runner and inference API."""
    return get_registry().resolve(analysis_type)


def list_pipelines() -> frozenset[dict]:
    """Registered pipeline descriptions (for the API)."""
    return frozenset(get_registry().list_descriptions())


def list_pipeline_descriptions() -> list[dict]:
    return get_registry().list_descriptions()
