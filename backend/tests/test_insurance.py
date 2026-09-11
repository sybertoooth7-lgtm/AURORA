"""Tests for the parametric agriculture insurance index (AURORA-2).

Pure-logic coverage (no DB/network): insurance-index pipeline bounds and
honesty contract, registry resolution, and the trigger/payout math used by
POST /insurance/trigger-check.
"""

from datetime import UTC, datetime

from app.ai.base import Provenance
from app.ai.insurance_index import DEFAULT_TRIGGER_THRESHOLD, InsuranceIndexPipeline
from app.ai.registry import get_pipeline
from app.models.analysis import AnalysisType
from app.satellite.providers import SatelliteObservation
from app.services.insurance import evaluate_trigger


def make_observation(ndvi=0.5, ndwi=-0.1, source="demo", image_id="demo-ins"):
    return SatelliteObservation(
        source=source,
        image_id=image_id,
        acquired_at=datetime.now(UTC),
        cloud_coverage=0.05,
        resolution_m=10.0,
        ndvi=ndvi,
        change_score=0.1,
        ndwi=ndwi,
        evi=None,
        bsi=None,
    )


def make_history(ndvis):
    return [make_observation(ndvi=v, image_id=f"demo-hist-{i}") for i, v in enumerate(ndvis)]


class TestInsuranceIndexPipeline:
    def test_condition_index_mapping(self):
        assert 0.0 <= InsuranceIndexPipeline.condition_index(-5.0) <= 1.0
        assert 0.0 <= InsuranceIndexPipeline.condition_index(5.0) <= 1.0
        assert InsuranceIndexPipeline.condition_index(0.8) > InsuranceIndexPipeline.condition_index(0.3)

    def test_healthy_crop_is_low_severity(self):
        result = InsuranceIndexPipeline().run(make_observation(ndvi=0.8, ndwi=0.2))
        assert result.severity < DEFAULT_TRIGGER_THRESHOLD
        assert result.labels[0].class_ == "crop_normal"
        assert result.metrics["crop_condition_index"] > 0.8

    def test_damaged_crop_crosses_trigger(self):
        result = InsuranceIndexPipeline().run(make_observation(ndvi=0.1, ndwi=-0.5))
        assert result.severity >= DEFAULT_TRIGGER_THRESHOLD
        assert result.labels[0].class_ == "parametric_damage"

    def test_severity_and_confidence_bounded(self):
        result = InsuranceIndexPipeline().run(make_observation(ndvi=0.4))
        assert 0.0 <= result.severity <= 1.0
        assert 0.0 <= result.confidence <= 0.98

    def test_simulated_source_stays_simulated(self):
        result = InsuranceIndexPipeline().run(make_observation(ndvi=0.5, source="demo"))
        assert result.provenance == Provenance.SIMULATED
        assert result.to_dict()["simulated"] is True

    def test_real_source_is_real(self):
        result = InsuranceIndexPipeline().run(
            make_observation(ndvi=0.5, source="sentinel-2-l2a")
        )
        assert result.provenance == Provenance.REAL

    def test_history_adds_baseline_metrics(self):
        result = InsuranceIndexPipeline().run(
            make_observation(ndvi=0.3), history=make_history([0.6, 0.65, 0.6])
        )
        assert "baseline_condition_index" in result.metrics
        assert "baseline_deviation" in result.metrics
        assert result.history_length == 3

    def test_missing_ndwi_is_disclosed(self):
        obs = SatelliteObservation(
            source="demo",
            image_id="demo-nondwi",
            acquired_at=datetime.now(UTC),
            cloud_coverage=0.05,
            resolution_m=10.0,
            ndvi=0.5,
            change_score=0.1,
        )
        result = InsuranceIndexPipeline().run(obs)
        assert any("No NDWI" in finding for finding in result.findings)

    def test_registry_resolves_insurance_index(self):
        pipeline = get_pipeline(AnalysisType.INSURANCE_INDEX)
        assert isinstance(pipeline, InsuranceIndexPipeline)
        assert pipeline.handles == frozenset({AnalysisType.INSURANCE_INDEX})

    def test_default_trigger_threshold_is_sane(self):
        assert 0.0 < DEFAULT_TRIGGER_THRESHOLD <= 1.0


class TestEvaluateTrigger:
    def test_no_payout_below_threshold(self):
        result = evaluate_trigger(severity=0.2, sum_insured_usd=1_000_000, trigger_threshold=0.4)
        assert result.trigger_breached is False
        assert result.payout_usd == 0.0
        assert result.estimated_liability_usd == 200_000.0

    def test_payout_above_threshold_scales_with_severity(self):
        result = evaluate_trigger(severity=0.6, sum_insured_usd=1_000_000, trigger_threshold=0.4)
        assert result.trigger_breached is True
        assert result.estimated_liability_usd == 600_000.0
        assert result.payout_usd == 600_000.0

    def test_coverage_ratio_haircuts_payout_not_liability(self):
        result = evaluate_trigger(
            severity=0.6, sum_insured_usd=1_000_000, trigger_threshold=0.4, coverage_ratio=0.8
        )
        assert result.estimated_liability_usd == 600_000.0
        assert result.payout_usd == 480_000.0

    def test_boundary_exactly_at_threshold_is_a_trigger(self):
        result = evaluate_trigger(severity=0.4, sum_insured_usd=100_000, trigger_threshold=0.4)
        assert result.trigger_breached is True
