"""Wildfire risk pipeline.

Wildfire fuel/dryness risk from optical area means: vegetation dryness (low
NDVI), bare/dry surface (BSI when the provider emits it), and moisture deficit
(negative NDWI). These are *proxy* signals for fuel availability and dryness,
not a fire model -- this pipeline is a prototype and must be validated against
real fire-scar / burning-season records before anything it says is treated as
operational. The description, model name (``composite-index:fire-proxy``), and
prototype model kind make that explicit to consumers.
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


class WildfirePipeline(Pipeline):
    name = "wildfire"
    description = (
        "Wildfire fuel/dryness risk from dry-vegetation (NDVI), bare/dry surface "
        "(BSI), and moisture deficit (NDWI) proxies. Prototype: must be validated "
        "against ground-truth fire records before operational use."
    )
    handles = frozenset({AnalysisType.WILDFIRE_RISK})
    model = ModelRef(name="composite-index:fire-proxy", version="1.0.0", kind=ModelKind.PROTOTYPE)
    preprocessing = ["clipped 0-1 dryness proxies", "weighted fuel-dryness composite"]

    def run(
        self,
        observation: SatelliteObservation,
        history: list[SatelliteObservation] | None = None,
    ) -> PipelineResult:
        history_length = len(history or [])
        # Antecedent dry spell: higher prior NDVI stress raises current risk.
        antecedent = 0.0
        if history:
            antecedent = pp.clip01(
                sum(pp.ndvi_stress_severity(h.ndvi) for h in history) / len(history)
            )

        dry_vegetation = pp.ndvi_stress_severity(observation.ndvi)
        moisture_deficit = None
        if observation.ndwi is not None:
            moisture_deficit = pp.clip01(max(0.0 - observation.ndwi, 0.0) / 0.4)
        bareness = pp.clip01(observation.bsi) if observation.bsi is not None else None

        findings: list[str] = []
        metrics: dict = {"ndvi": round(observation.ndvi, 4), "fire_fuel_proxy": round(dry_vegetation, 4)}
        if observation.ndwi is not None:
            metrics["ndwi"] = round(observation.ndwi, 4)
        if bareness is not None:
            metrics["bsi"] = round(bareness, 4)

        # Weights renormalize over whatever proxies are actually available so
        # missing inputs degrade gracefully instead of skewing the composite.
        components = [("vegetation", dry_vegetation, 0.5)]
        if bareness is not None:
            components.append(("bare_surface", bareness, 0.3))
        if moisture_deficit is not None:
            components.append(("moisture_deficit", moisture_deficit, 0.2))
        weights = sum(w for _, _, w in components)
        severity = (
            sum(v * w for _, v, w in components) / weights
            if weights > 0
            else 0.0
        )
        severity = pp.clip01(0.7 * severity + 0.3 * antecedent)

        if moisture_deficit is None:
            findings.append("No NDWI from provider; moisture-deficit component not assessed.")
        if bareness is None:
            findings.append("No BSI from provider; bare-surface component not assessed.")
        if antecedent > 0.5:
            findings.append("History shows sustained vegetation dryness (fuel-build-up risk).")

        dominant = max(components, key=lambda item: item[1])[0]
        findings.append(
            f"Fuel-dryness composite {severity:.2f}; dominant driver '{dominant}'."
            + (" Elevated fire risk." if severity >= 0.4 else " Low fire risk.")
        )

        confidence = (0.7 if observation.is_simulated else 0.82) * (1.05 if antecedent > 0.5 else 1.0)
        confidence = min(0.99, confidence)

        return PipelineResult(
            analysis_type=AnalysisType.WILDFIRE_RISK,
            severity=round(severity, 4),
            confidence=round(confidence, 4),
            findings=findings,
            metrics=metrics,
            provenance=provenance_for_observation(observation),
            source=observation.source,
            image_id=observation.image_id,
            acquired_at=observation.acquired_at,
            model=self.model,
            preprocessing=self.preprocessing,
            labels=[
                Label(
                    class_="fire_risk" if severity >= 0.4 else "low_fire_risk",
                    confidence=confidence,
                    attributes={"severity": round(severity, 4), "dominant_driver": dominant},
                )
            ],
            history_length=history_length,
        )

    def supports_history(self) -> bool:
        return True
