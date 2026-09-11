"""Tests for the modular AI pipelines (pure logic -- no DB, no network).

Covers: severity/confidence bounds, provenance honesty (demo input must
always come out simulated), history-aware anomaly detection, registry
resolution, and index math helpers.
"""

from datetime import datetime, timezone

import numpy as np
import pytest

from app.ai import preprocessing as pp
from app.ai.anomaly import AnomalyPipeline
from app.ai.base import PipelineResult, Provenance
from app.ai.environmental import EnvironmentalPipeline
from app.ai.flood import FloodPipeline
from app.ai.infrastructure import InfrastructurePipeline
from app.ai.land_change import LandChangePipeline
from app.ai.registry import get_pipeline
from app.ai.vegetation import VegetationPipeline
from app.ai.wildfire import WildfirePipeline
from app.models.analysis import AnalysisType
from app.satellite.providers import SatelliteObservation


def make_observation(
    ndvi=0.5,
    change_score=0.1,
    ndwi=None,
    evi=None,
    bsi=None,
    source="demo",
    image_id="demo-abc",
):
    return SatelliteObservation(
        source=source,
        image_id=image_id,
        acquired_at=datetime.now(timezone.utc),
        cloud_coverage=0.05,
        resolution_m=10.0,
        ndvi=ndvi,
        change_score=change_score,
        ndwi=ndwi,
        evi=evi,
        bsi=bsi,
    )


class TestIndexMath:
    def test_safe_divide_zero_denominator(self):
        assert pp.safe_divide(1.0, 0.0) == 0.0
        assert pp.safe_divide(1.0, np.nan) == 0.0

    def test_ndvi_stress_severity_bounds(self):
        assert pp.ndvi_stress_severity(0.8) < pp.ndvi_stress_severity(0.1)
        assert 0.0 <= pp.ndvi_stress_severity(5.0) <= 1.0

    def test_robust_zscore_is_median_mad_based(self):
        series = [0.4, 0.42, 0.41, 0.43, 0.41, 0.42, 0.41]
        z = pp.robust_zscore(0.1, series)
        assert z > 2.0  # a big deviation must register
        quiet = pp.robust_zscore(0.42, series)
        assert quiet < 1.0

    def test_anomaly_severity_saturates(self):
        assert pp.anomaly_severity_from_zscores([0.5]) < 0.5
        assert pp.anomaly_severity_from_zscores([9.0]) == pytest.approx(1.0)


class TestProvenanceHonesty:
    def test_demo_source_is_always_simulated(self):
        result = VegetationPipeline().run(make_observation(source="demo"))
        assert isinstance(result, PipelineResult)
        assert result.provenance == Provenance.SIMULATED
        assert result.to_dict()["simulated"] is True

    def test_real_sentinel_source_is_not_simulated(self):
        result = VegetationPipeline().run(
            make_observation(source="sentinel-2-l2a", image_id="cdse-1")
        )
        assert result.provenance == Provenance.REAL
        assert result.to_dict()["simulated"] is False
        # real data earns the higher confidence band only
        assert result.confidence >= 0.8

    def test_metadata_is_json_safe(self):
        result = VegetationPipeline().run(make_observation())
        import json

        round_trip = json.loads(json.dumps(result.to_metadata()))
        assert round_trip["analysis_type"] == "vegetation_stress"


class TestVegetationPipeline:
    def test_bad_ndvi_raises_severity(self):
        result = VegetationPipeline().run(make_observation(ndvi=0.15, change_score=0.4))
        assert result.severity >= 0.3
        assert result.findings

    def test_healthy_ndvi_low_severity(self):
        result = VegetationPipeline().run(make_observation(ndvi=0.7, change_score=0.05))
        assert result.severity < 0.3
        assert "healthy" in result.labels[0].class_


class TestLandChangePipeline:
    def test_change_score_maps_to_severity(self):
        result = LandChangePipeline().run(make_observation(change_score=0.8))
        assert result.severity >= 0.7

    def test_history_keeps_confidence_higher(self):
        history = [make_observation(ndvi=0.4, change_score=0.1) for _ in range(4)]
        no_history = LandChangePipeline().run(make_observation(change_score=0.5))
        with_history = LandChangePipeline().run(
            make_observation(change_score=0.5), history=history
        )
        assert with_history.confidence > no_history.confidence


class TestInfrastructurePipeline:
    def test_warns_about_area_level_scope(self):
        result = InfrastructurePipeline().run(
            make_observation(bsi=0.7, change_score=0.5)
        )
        assert result.severity >= 0.35
        assert result.warning is not None


class TestEnvironmentalPipeline:
    def test_negative_ndwi_detects_dry_surface(self):
        result = EnvironmentalPipeline().run(
            make_observation(ndwi=-0.4, ndvi=0.55, change_score=0.1)
        )
        assert result.severity >= 0.5

    def test_no_ndwi_falls_back_to_ecosystem_proxy(self):
        result = EnvironmentalPipeline().run(
            make_observation(ndwi=None, ndvi=0.7, change_score=0.05)
        )
        assert isinstance(result.severity, float)


class TestAnomalyPipeline:
    def test_insufficient_history_is_low_confidence(self):
        result = AnomalyPipeline().run(make_observation(change_score=0.9), history=[])
        assert result.confidence < 0.5
        assert result.warning is not None

    def test_anomalous_observation_against_history(self):
        history = [
            make_observation(ndvi=0.41 + (i % 3) * 0.01, change_score=0.1)
            for i in range(6)
        ]
        current = make_observation(ndvi=0.1, change_score=0.6)
        result = AnomalyPipeline().run(current, history=history)
        assert result.severity >= 0.5
        assert result.labels[0].class_ == "anomaly"

    def test_nominal_observation_low_severity(self):
        history = [
            make_observation(ndvi=0.4 + (i % 3) * 0.01, change_score=0.1)
            for i in range(6)
        ]
        current = make_observation(ndvi=0.42, change_score=0.12)
        result = AnomalyPipeline().run(current, history=history)
        assert result.severity < 0.5


class TestWildfirePipeline:
    def test_dry_vegetation_raises_risk(self):
        result = WildfirePipeline().run(
            make_observation(ndvi=0.1, ndwi=-0.3, bsi=0.6)
        )
        assert result.severity >= 0.5
        assert result.labels[0].class_ == "fire_risk"

    def test_healthy_area_is_low_risk(self):
        result = WildfirePipeline().run(
            make_observation(ndvi=0.75, ndwi=0.1, bsi=0.1)
        )
        assert result.severity < 0.4

    def test_missing_bsi_and_ndwi_degrades_gracefully(self):
        # Real Sentinel currently emits no BSI; pipeline must not crash.
        result = WildfirePipeline().run(make_observation(ndvi=0.5, ndwi=None, bsi=None))
        assert 0.0 <= result.severity <= 1.0

    def test_history_dry_spell_raises_antecedent_risk(self):
        history = [make_observation(ndvi=0.2, change_score=0.1) for _ in range(5)]
        no_history = WildfirePipeline().run(
            make_observation(ndvi=0.35, ndwi=-0.1, bsi=0.4)
        )
        with_history = WildfirePipeline().run(
            make_observation(ndvi=0.35, ndwi=-0.1, bsi=0.4), history=history
        )
        assert with_history.severity > no_history.severity


class TestFloodPipeline:
    def test_high_ndwi_triggers_flood_signal(self):
        result = FloodPipeline().run(make_observation(ndwi=0.45))
        assert result.severity >= 0.5
        assert result.labels[0].class_ == "flood_signal"

    def test_missing_ndwi_reports_not_assessed(self):
        result = FloodPipeline().run(make_observation(ndwi=None))
        assert result.severity == 0.0
        assert result.warning is not None
        assert result.labels[0].class_ == "not_assessed"

    def test_excess_water_over_baseline_flags_inundation(self):
        history = [
            make_observation(ndwi=-0.35 + (i % 3) * 0.02) for i in range(6)
        ]
        current = make_observation(ndwi=0.4)
        with_history = FloodPipeline().run(current, history=history)
        current_only = FloodPipeline().run(current)
        assert with_history.severity > current_only.severity
        assert with_history.confidence > current_only.confidence

    def test_no_baseline_reduces_confidence(self):
        result = FloodPipeline().run(make_observation(ndwi=0.3))
        assert result.confidence < 0.6
        assert result.warning is not None


class TestRegistry:
    def test_all_workspace_types_resolve(self):
        for analysis_type in AnalysisType:
            pipeline = get_pipeline(analysis_type)
            assert analysis_type in pipeline.handles

    def test_descriptions_are_serializable(self):
        from app.ai.registry import list_pipeline_descriptions

        descriptions = list_pipeline_descriptions()
        names = {d["name"] for d in descriptions}
        assert {"vegetation", "land_change", "infrastructure", "environmental", "anomaly"} <= names
        # every description carries a model identity + kind
        for d in descriptions:
            assert d["model"]["name"]
            assert d["model"]["kind"] in {"prototype", "production"}