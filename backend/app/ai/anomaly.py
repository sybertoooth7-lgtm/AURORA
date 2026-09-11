"""Anomaly detection pipeline.

Flag observations that deviate sharply from an area's own recent history
across multiple indices (NDVI, change score, NDWI, EVI) using robust
median/MAD z-scores. Without history the pipeline cannot detect anomalies
against a baseline -- it returns a low-confidence, explicitly-warned result
instead of inventing one.

This is the statistical foundation future autonomous-perception modules
(robotics site monitoring, spacecraft/planetary surface change) will build
on: the anomaly *interface* (history -> deviations) stays the same while
the input sources broaden.
"""

from typing import List, Optional

import numpy as np

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


class AnomalyPipeline(Pipeline):
    name = "anomaly"
    description = (
        "Detects statistically unusual readings vs. an area's own recent "
        "history (robust z-scores over NDVI/change/water indices)."
    )
    handles = frozenset({AnalysisType.ANOMALY_DETECTION})
    model = ModelRef(name="statistical:robust-zscore", version="1.0.0", kind=ModelKind.PROTOTYPE)
    preprocessing = ["median/MAD normalization", "per-index robust z-scores"]

    @staticmethod
    def _index_history(history: List[SatelliteObservation], attr: str, varied: bool) -> List[float]:
        values = []
        for obs in history:
            value = getattr(obs, attr)
            if value is not None and np.isfinite(float(value)):
                values.append(float(value))
            elif not varied:
                values.append(0.0)
        return values

    def run(
        self,
        observation: SatelliteObservation,
        history: Optional[List[SatelliteObservation]] = None,
    ) -> PipelineResult:
        history = history or []
        history_length = len(history)

        if history_length < 3:
            severity = 0.5 if observation.change_score >= 0.5 else 0.0
            confidence = 0.25
            return PipelineResult(
                analysis_type=AnalysisType.ANOMALY_DETECTION,
                severity=round(severity, 4),
                confidence=round(confidence, 4),
                findings=[
                    "Not enough history to establish an anomaly baseline "
                    f"(need >= 3 prior passes, have {history_length})."
                ],
                metrics={"change_score": round(observation.change_score, 4)},
                provenance=provenance_for_observation(observation),
                source=observation.source,
                image_id=observation.image_id,
                acquired_at=observation.acquired_at,
                model=self.model,
                preprocessing=self.preprocessing,
                warning="Insufficient history -- anomaly confidence is low and advisory only.",
                history_length=history_length,
            )

        # Collect one robust z-score per available index dimension.
        index_specs = [
            ("ndvi", True),
            ("change_score", True),
            ("ndwi", False),
            ("evi", False),
        ]
        zscores: List[float] = []
        dimensions: List[str] = []
        for attr, varied in index_specs:
            current = getattr(observation, attr)
            series = self._index_history(history, attr, varied)
            if current is not None and np.isfinite(float(current)) and series:
                zscores.append(pp.robust_zscore(float(current), series))
                dimensions.append(attr)

        if not zscores:
            return PipelineResult(
                analysis_type=AnalysisType.ANOMALY_DETECTION,
                severity=0.0,
                confidence=0.0,
                findings=["No usable index dimensions for anomaly detection."],
                metrics={},
                provenance=provenance_for_observation(observation),
                source=observation.source,
                image_id=observation.image_id,
                acquired_at=observation.acquired_at,
                model=self.model,
                preprocessing=self.preprocessing,
                history_length=history_length,
            )

        severity = pp.anomaly_severity_from_zscores(zscores)
        peak_z = max(zscores)
        worst_dim = dimensions[int(np.argmax(zscores))]

        confidence = (0.75 if observation.is_simulated else 0.88) * max(
            0.5, min(1.0, history_length / 8)
        )
        anomalous = severity >= 0.5
        findings = [
            (
                f"Anomaly flagged in {worst_dim} "
                f"(robust z-score {peak_z:.2f}); {len(zscores)} index dimensions checked."
            )
            if anomalous
            else f"No material anomaly (peak robust z-score {peak_z:.2f})."
        ]

        metric_map = {attr: round(float(zscores[i]), 4) for i, attr in enumerate(dimensions)}
        return PipelineResult(
            analysis_type=AnalysisType.ANOMALY_DETECTION,
            severity=round(severity, 4),
            confidence=round(confidence, 4),
            findings=findings,
            metrics={**metric_map, "peak_zscore": round(peak_z, 4)},
            provenance=provenance_for_observation(observation),
            source=observation.source,
            image_id=observation.image_id,
            acquired_at=observation.acquired_at,
            model=self.model,
            preprocessing=self.preprocessing,
            labels=[
                Label(
                    class_="anomaly" if anomalous else "nominal",
                    confidence=confidence,
                    attributes={"peak_zscore": round(peak_z, 4), "worst_dimension": worst_dim},
                )
            ],
            history_length=history_length,
        )

    def supports_history(self) -> bool:
        return True