"""Parametric agriculture-insurance index pipeline (Earth-revenue AURORA-2).

Estimates a crop *damage proxy* for area-yield index insurance from optical
area means: vegetation stress (low NDVI), moisture deficit (negative NDWI)
and -- when history is available -- the deviation of the current crop
condition from the multi-season baseline. Higher severity = worse for the
farmer = more likely to breach a parametric trigger.

Honesty contract (same as every pipeline):

* This is a **prototype**. It has not been validated against ground truth
  (field surveys, loss adjuster records). The model kind is PROTOTYPE and
  every description/finding makes that explicit. Nothing here is a payout
  recommendation on its own -- ``POST /insurance/trigger-check`` applies the
  policy threshold and flags simulated provenance, but the decision still
  needs an underwriter.
* Interpreting NDVI as crop condition works for green vegetation; it does
  *not* separate drought damage from disease, pest, or harvest senescence.
  The pipeline only ever claims "vegetation damage proxy", never a cause.
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

DEFAULT_TRIGGER_THRESHOLD = 0.4


class InsuranceIndexPipeline(Pipeline):
    name = "insurance_index"
    description = (
        "Crop condition / parametric damage proxy for area-yield index "
        "insurance from vegetation (NDVI), moisture (NDWI) and multi-season "
        "baseline deviation. Prototype: must be validated against field "
        "survey / loss-adjuster ground truth before any payout decision."
    )
    handles = frozenset({AnalysisType.INSURANCE_INDEX})
    model = ModelRef(
        name="composite-index:parametric-crop", version="1.0.0", kind=ModelKind.PROTOTYPE
    )
    preprocessing = [
        "clipped 0-1 vegetation/moisture proxies",
        "historical crop-condition baseline deviation",
        "reweighted composite when NDWI/history unavailable",
    ]

    @staticmethod
    def condition_index(ndvi: float) -> float:
        """Map area-mean NDVI onto a 0..1 crop condition (1 = healthy).

        Linear ramp from NDVI ~0.12 (total loss / bare ground) to ~0.8
        (vigorous vegetation). Band-math threshold, not an agronomy model --
        kept deliberately coarse until validated against field data.
        """
        return pp.clip01((pp.clip01(ndvi) - 0.12) / 0.68)

    def run(
        self,
        observation: SatelliteObservation,
        history: list[SatelliteObservation] | None = None,
    ) -> PipelineResult:
        history_length = len(history or [])

        current_condition = self.condition_index(observation.ndvi)
        stress = pp.clip01(1.0 - current_condition)

        moisture_deficit = None
        ndwi = observation.ndwi
        if ndwi is not None:
            moisture_deficit = pp.clip01(max(0.0 - ndwi, 0.0) / 0.4)

        baseline_condition = None
        baseline_deviation = 0.0
        if history:
            valid_ndvi = [h.ndvi for h in history if h.ndvi is not None]
            if valid_ndvi:
                baseline_condition = self.condition_index(
                    sum(valid_ndvi) / len(valid_ndvi)
                )
                baseline_deviation = pp.clip01(
                    (baseline_condition - current_condition)
                    / max(baseline_condition, 1e-6)
                )

        components = [("current_stress", stress, 0.6)]
        if moisture_deficit is not None:
            components.append(("moisture_deficit", moisture_deficit, 0.25))
        if baseline_condition is not None:
            components.append(("baseline_deviation", baseline_deviation, 0.15))
        weights = sum(weight for _, _, weight in components)
        severity = (
            sum(value * weight for _, value, weight in components) / weights
            if weights > 0
            else 0.0
        )
        severity = pp.clip01(severity)

        findings: list[str] = [
            (
                f"Crop condition index {current_condition:.2f}; parametric "
                f"damage proxy {severity:.2f}."
            )
            + (
                " Payout threshold typically breached."
                if severity >= DEFAULT_TRIGGER_THRESHOLD
                else " Below a typical parametric payout trigger."
            )
        ]
        if moisture_deficit is None:
            findings.append("No NDWI from provider; moisture component not assessed.")
        if baseline_condition is None:
            findings.append(
                "No history from provider; multi-season baseline deviation not assessed."
            )

        metrics: dict = {
            "ndvi": round(observation.ndvi, 4),
            "crop_condition_index": round(current_condition, 4),
            "damage_proxy": round(severity, 4),
        }
        ndwi = observation.ndwi
        if ndwi is not None:
            metrics["ndwi"] = round(ndwi, 4)
            metrics["moisture_deficit"] = round(pp.clip01(max(0.0 - ndwi, 0.0) / 0.4), 4)
        if baseline_condition is not None:
            metrics["baseline_condition_index"] = round(baseline_condition, 4)
            metrics["baseline_deviation"] = round(baseline_deviation, 4)

        confidence = 0.7 if observation.is_simulated else 0.82
        if baseline_condition is not None:
            confidence += 0.03
        confidence = min(0.98, confidence)

        return PipelineResult(
            analysis_type=AnalysisType.INSURANCE_INDEX,
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
                    class_="parametric_damage"
                    if severity >= DEFAULT_TRIGGER_THRESHOLD
                    else "crop_normal",
                    confidence=confidence,
                    attributes={
                        "damage_proxy": round(severity, 4),
                        "crop_condition_index": round(current_condition, 4),
                    },
                )
            ],
            history_length=history_length,
        )

    def supports_history(self) -> bool:
        return True
