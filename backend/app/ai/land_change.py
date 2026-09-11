"""Land change detection pipeline (land intelligence).

Land intelligence: surface change between the latest pass and a trailing
baseline (vegetation loss, vegetation gain, construction, water retreat).

Change is quantified from the provider's change_score (latest-vs-baseline
NDVI delta) and, when history is available, the robustness of that delta
against natural variation. The direction of change (greening vs. browning)
is inferred from the NDVI sign.
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


class LandChangePipeline(Pipeline):
    name = "land_change"
    description = (
        "Detects land-surface change against a trailing baseline: "
        "vegetation loss/gain, new bare or built-up surface, water retreat."
    )
    handles = frozenset({AnalysisType.LAND_CHANGE})
    model = ModelRef(name="statistical:change-score", version="1.0.0", kind=ModelKind.PROTOTYPE)
    preprocessing = ["baseline normalization", "change-score vs trailing mean"]

    def run(
        self,
        observation: SatelliteObservation,
        history: list[SatelliteObservation] | None = None,
    ) -> PipelineResult:
        change = pp.clip01(observation.change_score)
        direction = "greening" if observation.ndvi >= 0.3 else "browning or surface change"

        history_length = len(history or [])
        # When we have history, pull a z-score of the latest NDVI against the
        # past so natural seasonality doesn't get flagged as real change.
        zscore = 0.0
        if history is not None and len(history) >= 2:
            historical_ndvi = [h.ndvi for h in history]
            zscore = pp.robust_zscore(observation.ndvi, historical_ndvi)
            change = pp.clip01(max(change, pp.anomaly_severity_from_zscores([zscore])))

        severity = change
        confidence = (0.7 if observation.is_simulated else 0.85) * (
            1.0 if history_length >= 2 else 0.9
        )

        if severity < 0.35:
            finding = "No significant land change detected"
        elif severity < 0.7:
            finding = f"Moderate land change detected ({direction})"
        else:
            finding = f"Significant land change detected ({direction})"

        return PipelineResult(
            analysis_type=AnalysisType.LAND_CHANGE,
            severity=round(severity, 4),
            confidence=round(confidence, 4),
            findings=[finding],
            metrics={
                "change_score": round(observation.change_score, 4),
                "change_direction": 1.0 if observation.ndvi >= 0.3 else -1.0,
                "ndvi": round(observation.ndvi, 4),
                "robust_zscore": round(zscore, 4),
            },
            provenance=provenance_for_observation(observation),
            source=observation.source,
            image_id=observation.image_id,
            acquired_at=observation.acquired_at,
            model=self.model,
            preprocessing=self.preprocessing,
            labels=[
                Label(
                    class_="change" if severity >= 0.35 else "stable",
                    confidence=confidence,
                    attributes={"direction": direction, "magnitude": round(severity, 4)},
                )
            ],
            history_length=history_length,
        )

    def supports_history(self) -> bool:
        return True
