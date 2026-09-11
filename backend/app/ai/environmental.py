"""Environmental monitoring pipeline.

Environmental monitoring: water bodies / water stress (NDWI), and climate /
ecosystem stress signals (vegetation trend + change). Serves climate_impact,
water_monitoring, and environmental_monitoring analyses.

Water monitoring uses the McFeeters NDWI (green/NIR) when the provider
emits it; climate impact uses a blend of NDVI level, change trend, and (when
available) EVI. All values are area means and prototypes until
ground-validated.
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


class EnvironmentalPipeline(Pipeline):
    name = "environmental"
    description = (
        "Environmental monitoring: water-body stress (NDWI), vegetation/climate "
        "stress trends (NDVI/EVI + change)."
    )
    handles = frozenset(
        {
            AnalysisType.CLIMATE_IMPACT,
            AnalysisType.WATER_MONITORING,
            AnalysisType.ENVIRONMENTAL_MONITORING,
        }
    )
    model = ModelRef(name="rules:ndwi/evi/ndvi", version="1.0.0", kind=ModelKind.PROTOTYPE)
    preprocessing = ["water index (NDWI) proxy", "vegetation index (NDVI/EVI) trend"]

    def run(
        self,
        observation: SatelliteObservation,
        history: list[SatelliteObservation] | None = None,
    ) -> PipelineResult:
        history_length = len(history or [])
        change = pp.clip01(observation.change_score)
        ndvi = observation.ndvi
        evi = observation.evi
        ndwi = observation.ndwi

        findings: list[str] = []
        metrics: dict = {"change_score": round(change, 4), "ndvi": round(ndvi, 4)}

        # Water stress component (when the provider gives NDWI).
        water_severity = None
        if ndwi is not None:
            # NDWI > ~0.2 = open water; strongly negative = dry/exposed.
            water_severity = pp.clip01(max(0.0 - ndwi, 0.0) / (0.0 - (-0.4)))
            metrics["ndwi"] = round(ndwi, 4)
            findings.append(
                f"Water index NDWI {ndwi:.2f}"
                + (" (dry/exposed surface)." if water_severity > 0.5 else " (stable).")
            )
        else:
            findings.append("No NDWI available from provider; water stress not assessed.")

        if evi is not None:
            metrics["evi"] = round(evi, 4)

        # Climate / ecosystem stress component: vegetation level + change.
        climate_severity = pp.clip01(0.6 * pp.ndvi_stress_severity(ndvi) + 0.4 * change)
        metrics["climate_stress_proxy"] = round(climate_severity, 4)

        if water_severity is not None:
            severity = pp.clip01(max(water_severity, climate_severity))
            findings.append(
                "Environmental stress detected"
                if severity >= 0.35
                else "No significant environmental stress detected."
            )
        else:
            severity = climate_severity

        confidence = (0.7 if observation.is_simulated else 0.84) * (0.9 if history_length >= 2 else 0.8)
        primary = "water" if water_severity is not None and water_severity > climate_severity else "ecosystem"

        return PipelineResult(
            analysis_type=AnalysisType.ENVIRONMENTAL_MONITORING,
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
                    class_=primary + "_stress" if severity >= 0.35 else "stable",
                    confidence=confidence,
                    attributes={"severity": round(severity, 4)},
                )
            ],
            history_length=history_length,
        )

    def supports_history(self) -> bool:
        return True
