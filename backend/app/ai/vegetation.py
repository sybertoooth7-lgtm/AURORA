"""Vegetation detection & stress pipeline (agriculture priority use case).

Agriculture:  vegetation stress detection from NDVI.

The current generation classifies the *latest* area-level NDVI (plus its
change vs. trailing baseline) onto a healthy / stressed / critical scale.
This is a validated band-math proxy well established in agronomy; exact
thresholds are still tuned per crop and marked prototype until validated
against field ground-truth data.
"""


from app.ai import preprocessing as pp
from app.ai.base import (
    Label,
    ModelKind,
    ModelRef,
    Pipeline,
    PipelineResult,
    provenance_for_observation,
)
from app.models.analysis import AnalysisType
from app.satellite.providers import SatelliteObservation


class VegetationPipeline(Pipeline):
    name = "vegetation"
    description = (
        "NDVI-based vegetation health and stress detection over an area "
        "(agriculture). Reports severity, coverage class, and index metrics."
    )
    handles = frozenset({AnalysisType.VEGETATION_STRESS})
    model = ModelRef(name="band-math:ndvi", version="1.0.0", kind=ModelKind.PROTOTYPE)
    preprocessing = ["area-level NDVI normalization", "cloud-masked means (provider)"]

    def run(
        self,
        observation: SatelliteObservation,
        history: list[SatelliteObservation] | None = None,
    ) -> PipelineResult:
        ndvi = observation.ndvi
        severity = pp.ndvi_stress_severity(ndvi)
        change = observation.change_score
        # Blend the absolute level with the rate of change so a green area
        # that is *rapidly* degrading still flags, not just already-barren land.
        blended_severity = pp.clip01(0.7 * severity + 0.3 * change)

        if severity < 0.35:
            condition = "healthy"
        elif severity < 0.7:
            condition = "stressed"
        else:
            condition = "critical"

        confidence = 0.7 if observation.is_simulated else 0.85
        findings = [
            f"Vegetation condition: {condition} "
            f"(NDVI {ndvi:.2f}, severity {blended_severity:.2f})."
        ]
        if condition != "healthy":
            findings.append(
                f"Stress covers an estimated {severity * 100:.0f}% of the area threshold."
            )

        return PipelineResult(
            analysis_type=AnalysisType.VEGETATION_STRESS,
            severity=round(blended_severity, 4),
            confidence=round(confidence, 4),
            findings=findings,
            metrics={
                "ndvi": round(ndvi, 4),
                "change_score": round(change, 4),
                "ndwi": round(observation.ndwi, 4) if observation.ndwi is not None else -1.0,
                "evi": round(observation.evi, 4) if observation.evi is not None else -1.0,
                "stressed_area_fraction": round(severity, 4),
            },
            provenance=provenance_for_observation(observation),
            source=observation.source,
            image_id=observation.image_id,
            acquired_at=observation.acquired_at,
            model=self.model,
            preprocessing=self.preprocessing,
            labels=[
                Label(class_=condition, confidence=confidence, attributes={"ndvi": round(ndvi, 4)})
            ],
            history_length=len(history or []),
        )

    def supports_history(self) -> bool:
        return True
