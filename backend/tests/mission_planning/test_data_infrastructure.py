from datetime import UTC, datetime

from app.mission_planning.data_infrastructure import (
    DataInfrastructureRegistry,
    DataSource,
    SourceStatus,
)


def test_healthy_source_with_room_left_is_schedulable():
    source = DataSource(name="sentinel-hub", provider="CDSE", status=SourceStatus.HEALTHY,
                         quota_used=10, quota_limit=100)
    assert source.is_schedulable is True
    assert source.quota_fraction_used == 0.1


def test_down_source_is_never_schedulable_regardless_of_quota():
    source = DataSource(name="sentinel-hub", provider="CDSE", status=SourceStatus.DOWN)
    assert source.is_schedulable is False


def test_exhausted_quota_makes_a_healthy_source_unschedulable():
    source = DataSource(name="sentinel-hub", provider="CDSE", status=SourceStatus.HEALTHY,
                         quota_used=100, quota_limit=100)
    assert source.is_schedulable is False


def test_registry_readiness_report_reflects_mixed_status():
    registry = DataInfrastructureRegistry()
    registry.register(DataSource(name="a", provider="CDSE", status=SourceStatus.HEALTHY))
    registry.register(DataSource(name="b", provider="demo", status=SourceStatus.DOWN))

    report = registry.readiness_report()

    assert report["overall"] == "degraded"
    assert len(report["sources"]) == 2


def test_update_status_and_record_usage_affect_schedulability():
    registry = DataInfrastructureRegistry()
    registry.register(DataSource(name="a", provider="CDSE", quota_limit=100))

    registry.update_status("a", SourceStatus.HEALTHY, datetime.now(UTC))
    assert registry.get("a") in registry.schedulable_sources()

    registry.record_usage("a", 100)
    assert registry.get("a") not in registry.schedulable_sources()


def test_unknown_source_raises_on_update():
    import pytest

    registry = DataInfrastructureRegistry()
    with pytest.raises(KeyError):
        registry.update_status("nope", SourceStatus.HEALTHY, datetime.now(UTC))
