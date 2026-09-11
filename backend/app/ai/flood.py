"""Flood / inundation monitoring pipeline.

Flags inundation using the McFeeters NDWI (from the provider) compared against
an area's own Sentinel history. A flood signal is an NDWI that is both high in
absolute terms (open water present) and far above the area's seasonal baseline
(excess water). With no history, only the single-scene wetness can be assessed
(low confidence, explicit warning). Prototype: real inundation claims need
validation against river-gauge or flooding records.
"""

from statistics import mean

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


class FloodPipeline(Pipeline):
    name = "flood"
    description = (
        "Flood/inundation risk from NDWI against the area's own baseline: "
        "absolute wetness plus excess-over-baseline. Prototype; needs validation "
        "against ground-truth flooding records before operational use."
    )
    handles = frozenset({AnalysisType.FLOOD_MONITORING})
    model = ModelRef(name="statistical:ndwi-baseline", version="1.0.0", kind=ModelKind.PROTOTYPE)
    preprocessing = ["NDWI current vs area baseline", "excess-water anomaly (z-score)"]

    def run(
        self,
        observation: SatelliteObservation,
        history: list[SatelliteObservation] | None = None,
    ) -> PipelineResult:
        history_length = len(history or [])
        ndwi = observation.ndwi
        if ndwi is None:
            return PipelineResult(
                analysis_type=AnalysisType.FLOOD_MONITORING,
                severity=0.0,
                confidence=0.1,
                findings=["Provider gave no NDWI; flood/inundation cannot be assessed."],
                metrics={"ndwi": None, "baseline_ndwi": None},
                provenance=provenance_for_observation(observation),
                source=observation.source,
                image_id=observation.image_id,
                acquired_at=observation.acquired_at,
                model=self.model,
                preprocessing=self.preprocessing,
                labels=[Label(class_="not_assessed", confidence=0.1)],
                warning="NDWI is required for flood monitoring and was not available.",
                history_length=history_length,
            )

        baseline_ndwi = [h.ndwi for h in (history or []) if h.ndwi is not None]
        baseline_value = mean(baseline_ndwi) if baseline_ndwi else None

        # Absolute wetness: NDWI near/above ~0.2 signals open water.
        wetness = pp.clip01((ndwi - 0.1) / 0.4)

        excess_severity = None
        if baseline_value is not None and len(baseline_ndwi) >= 2:
            z = pp.robust_zscore(ndwi, baseline_ndwi)
            excess_severity = pp.anomaly_severity_from_zscores([z])
        elif baseline_value is not None:
            excess_severity = pp.clip01((ndwi - baseline_value) / 0.4)

        severity = wetness if excess_severity is None else max(wetness, excess_severity)
        severity = pp.clip01(severity)

        baseline_used = baseline_value is not None
        findings: list[str] = []
        if baseline_used:
            findings.append(
                f"NDWI {ndwi:.3f} vs baseline {baseline_value:.3f} "
                f"({len(baseline_ndwi)} prior scenes)"
            )
        else:
            findings.append("No usable history baseline; single-scene wetness only.")
        findings.append(
            "Inundation signal detected." if severity >= 0.5 else "No significant wetness anomaly."
        )

        confidence = (0.72 if observation.is_simulated else 0.85) * (0.95 if baseline_used else 0.55)
        warning = None if baseline_used else "No history baseline; confidence reduced."

        return PipelineResult(
            analysis_type=AnalysisType.FLOOD_MONITORING,
            severity=round(severity, 4),
            confidence=round(confidence, 4),
            findings=findings,
            metrics={
                "ndwi": round(ndwi, 4),
                "wetness": round(wetness, 4),
                "baseline_ndwi": round(baseline_value, 4) if baseline_value is not None else None,
                "excess_severity": round(excess_severity, 4) if excess_severity is not None else None,
            },
            provenance=provenance_for_observation(observation),
            source=observation.source,
            image_id=observation.image_id,
            acquired_at=observation.acquired_at,
            model=self.model,
            preprocessing=self.preprocessing,
            labels=[
                Label(
                    class_="flood_signal" if severity >= 0.5 else "no_flood_signal",
                    confidence=confidence,
                    attributes={"severity": round(severity, 4)},
                )
            ],
            warning=warning,
            history_length=history_length,
        )

    def supports_history(self) -> bool:
        return True
