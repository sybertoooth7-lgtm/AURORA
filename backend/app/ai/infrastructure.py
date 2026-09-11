"""Infrastructure monitoring & change detection pipeline.

Infrastructure: monitoring of built-up surface, construction, and site
change (roads, buildings, industrial/mining sites, logistics hubs).

The MVP works on area-level statistics -- a Bare Soil Index (BSI) proxy
for exposed/built surface plus the provider's change score. This tells a
site monitor "surface composition around here changed" but cannot yet
identify specific structures; that requires pixel-level imagery and is the
natural next stage. This is why the model is marked prototype.
"""

from typing import List, Optional

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


class InfrastructurePipeline(Pipeline):
    name = "infrastructure"
    description = (
        "Monitors built-up / exposed-surface change for infrastructure sites "
        "(construction, mining, logistics). Area-level BSI proxy + change."
    )
    handles = frozenset({AnalysisType.INFRASTRUCTURE_CHANGE, AnalysisType.INFRASTRUCTURE_MONITORING})
    model = ModelRef(name="rules:bsi+change", version="1.0.0", kind=ModelKind.PROTOTYPE)
    preprocessing = ["bare-soil-index proxy", "change-vs-baseline normalization"]

    def run(
        self,
        observation: SatelliteObservation,
        history: Optional[List[SatelliteObservation]] = None,
    ) -> PipelineResult:
        change = pp.clip01(observation.change_score)
        bsi = pp.clip01(observation.bsi) if observation.bsi is not None else None

        news = []
        if bsi is not None:
            news.append("area-level bare-soil proxy computed from provider bands")
        bsi_component = bsi if bsi is not None else 0.0
        # Infrastructure activity shows up as both new exposed surface AND
        # deviation from the site's own baseline -- weight the two equally,
        # but degrade gracefully when no BSI is available.
        if bsi is not None:
            severity = pp.clip01(0.5 * bsi_component + 0.5 * change)
        else:
            severity = change
            news = news + ["no BSI available; severity based on change score only"]

        history_length = len(history or [])
        confidence = (0.7 if observation.is_simulated else 0.82) * (0.9 if history_length >= 2 else 0.75)
        warning = (
            "Area-level statistics only; structure-level detection requires "
            "pixel imagery (planned: pixel-level built-up segmentation)."
        )

        if severity < 0.35:
            finding = "No significant infrastructure/surface change detected"
        elif severity < 0.7:
            finding = "Moderate surface change detected (possible construction/activity)"
        else:
            finding = "Significant surface change detected (possible major construction/activity)"

        return PipelineResult(
            analysis_type=AnalysisType.INFRASTRUCTURE_CHANGE,
            severity=round(severity, 4),
            confidence=round(confidence, 4),
            findings=[finding] + news if news else [finding],
            metrics={
                "change_score": round(observation.change_score, 4),
                "bsi": round(bsi, 4) if bsi is not None else -1.0,
                "surface_activity_proxy": round(severity, 4),
            },
            provenance=provenance_for_observation(observation),
            source=observation.source,
            image_id=observation.image_id,
            acquired_at=observation.acquired_at,
            model=self.model,
            preprocessing=self.preprocessing,
            labels=[
                Label(
                    class_="active" if severity >= 0.35 else "stable",
                    confidence=confidence,
                    attributes={"change_score": round(observation.change_score, 4)},
                )
            ],
            warning=warning,
            history_length=history_length,
        )

    def supports_history(self) -> bool:
        return True