"""Robotics field-inspection pipeline (Earth-revenue AURORA-2).

Post-flight NDVI-based damage assessment for a field / site visited by a
drone or ground robot. The satellite signal replaces the human walking the
field; the robot telemetry (battery, GPS accuracy, fault flags) is fused at
the route layer, not here -- this pipeline only ever sees the same
``SatelliteObservation`` contract every other pipeline does, so it stays
automatically interchangeable with the demo/real providers.

Prototype: an NDVI dip does not identify *why* a crop is damaged (drought,
disease, pests), so confidence is intentionally deflated and the output must
not be used for loss quantification until validated against field truth.
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

DAMAGE_LABEL_THRESHOLD = 0.4


class RoboticsInspectionPipeline(Pipeline):
    name = "robotics_inspection"
    description = (
        "Post-flight field damage assessment from NDVI for drone/ground "
        "robot inspection reports. Prototype: not a loss-quantification "
        "model; must be validated against on-the-ground surveys."
    )
    handles = frozenset({AnalysisType.ROBOTICS_INSPECTION})
    model = ModelRef(
        name="composite-index:ndvi-field-damage", version="1.0.0", kind=ModelKind.PROTOTYPE
    )
    preprocessing = ["clipped 0-1 NDVI damage proxy", "confidence deflated until ground-truth validation"]

    @staticmethod
    def damage_proxy_from_ndvi(ndvi: float) -> float:
        """Map area-mean NDVI onto a 0..1 vegetation damage proxy."""
        condition = (pp.clip01(ndvi) - 0.12) / 0.68
        return pp.clip01(1.0 - condition)

    def run(
        self,
        observation: SatelliteObservation,
        history: list[SatelliteObservation] | None = None,
    ) -> PipelineResult:
        damage = self.damage_proxy_from_ndvi(observation.ndvi)
        findings: list[str] = [
            (
                f"Field vegetation damage proxy {damage:.2f} (NDVI "
                f"{observation.ndvi:.3f})."
            )
            + (
                " Damage warrants a follow-up ground survey."
                if damage >= DAMAGE_LABEL_THRESHOLD
                else " No significant vegetation damage indicated."
            )
        ]
        confidence = 0.68 if observation.is_simulated else 0.8
        return PipelineResult(
            analysis_type=AnalysisType.ROBOTICS_INSPECTION,
            severity=round(damage, 4),
            confidence=round(confidence, 4),
            findings=findings,
            metrics={"ndvi": round(observation.ndvi, 4), "field_damage_proxy": round(damage, 4)},
            provenance=provenance_for_observation(observation),
            source=observation.source,
            image_id=observation.image_id,
            acquired_at=observation.acquired_at,
            model=self.model,
            preprocessing=self.preprocessing,
            labels=[
                Label(
                    class_="field_damage" if damage >= DAMAGE_LABEL_THRESHOLD else "crop_normal",
                    confidence=confidence,
                    attributes={"field_damage_proxy": round(damage, 4)},
                )
            ],
            history_length=len(history or []),
        )
