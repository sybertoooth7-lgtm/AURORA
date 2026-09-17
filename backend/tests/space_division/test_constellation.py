import pytest

from app.space_division.constellation import (
    Constellation,
    GroundContactConflict,
    GroundContactScheduler,
    OrbitalPlane,
    Satellite,
    SatelliteStatus,
)
from app.spacecraft.mission import ContactWindow


def _plane(altitude_km=500.0, inclination_deg=97.4, raan_deg=0.0):
    return OrbitalPlane(inclination_deg=inclination_deg, altitude_km=altitude_km, raan_deg=raan_deg)


def _sat(sat_id, plane, status=SatelliteStatus.OPERATIONAL, priority=0):
    return Satellite(id=sat_id, name=sat_id, plane=plane, status=status, priority=priority)


class TestOrbitalPlane:
    def test_period_matches_known_value_for_500km_altitude(self):
        plane = _plane(altitude_km=500.0)
        assert plane.period_minutes() == pytest.approx(94.469, abs=0.01)

    def test_period_increases_with_altitude(self):
        low = _plane(altitude_km=400.0).period_minutes()
        high = _plane(altitude_km=550.0).period_minutes()
        assert low < high


class TestConstellation:
    def test_satellites_in_plane_groups_correctly(self):
        plane_a = _plane(raan_deg=0.0)
        plane_b = _plane(raan_deg=90.0)
        constellation = Constellation("test-fleet")
        constellation.add_satellite(_sat("sat-1", plane_a))
        constellation.add_satellite(_sat("sat-2", plane_a))
        constellation.add_satellite(_sat("sat-3", plane_b))

        assert {s.id for s in constellation.satellites_in_plane(plane_a)} == {"sat-1", "sat-2"}
        assert {s.id for s in constellation.satellites_in_plane(plane_b)} == {"sat-3"}

    def test_operational_satellites_excludes_other_statuses(self):
        plane = _plane()
        constellation = Constellation("test-fleet")
        constellation.add_satellite(_sat("op", plane, status=SatelliteStatus.OPERATIONAL))
        constellation.add_satellite(_sat("comm", plane, status=SatelliteStatus.COMMISSIONING))
        constellation.add_satellite(_sat("dead", plane, status=SatelliteStatus.DECOMMISSIONED))

        assert [s.id for s in constellation.operational_satellites()] == ["op"]

    def test_revisit_interval_is_none_with_no_operational_satellites(self):
        constellation = Constellation("empty-fleet")
        constellation.add_satellite(_sat("comm", _plane(), status=SatelliteStatus.COMMISSIONING))
        assert constellation.estimated_revisit_interval_hours() is None

    def test_revisit_interval_improves_with_more_satellites(self):
        plane = _plane()
        one_sat = Constellation("one")
        one_sat.add_satellite(_sat("s1", plane))

        four_sats = Constellation("four")
        for i in range(4):
            four_sats.add_satellite(_sat(f"s{i}", plane))

        assert four_sats.estimated_revisit_interval_hours() < one_sat.estimated_revisit_interval_hours()
        # Exactly 4x fewer hours between passes with 4x the satellites,
        # given the simplified even-phasing assumption this estimate uses.
        assert four_sats.estimated_revisit_interval_hours() == pytest.approx(
            one_sat.estimated_revisit_interval_hours() / 4, rel=1e-9
        )


class TestGroundContactScheduler:
    def test_non_overlapping_requests_are_all_granted(self):
        plane = _plane()
        sat_a, sat_b = _sat("a", plane), _sat("b", plane)
        requests = [
            (sat_a, ContactWindow(ground_station="Nairobi", start_s=0, end_s=100)),
            (sat_b, ContactWindow(ground_station="Nairobi", start_s=100, end_s=200)),
        ]

        granted, conflicts = GroundContactScheduler().schedule(requests)

        assert len(granted) == 2
        assert conflicts == []

    def test_different_ground_stations_never_conflict(self):
        plane = _plane()
        sat_a, sat_b = _sat("a", plane), _sat("b", plane)
        requests = [
            (sat_a, ContactWindow(ground_station="Nairobi", start_s=0, end_s=100)),
            (sat_b, ContactWindow(ground_station="Mombasa", start_s=0, end_s=100)),
        ]

        granted, conflicts = GroundContactScheduler().schedule(requests)

        assert len(granted) == 2
        assert conflicts == []

    def test_higher_priority_satellite_wins_the_overlapping_slot(self):
        plane = _plane()
        low_priority = _sat("low", plane, priority=0)
        high_priority = _sat("high", plane, priority=10)
        requests = [
            (low_priority, ContactWindow(ground_station="Nairobi", start_s=0, end_s=100)),
            (high_priority, ContactWindow(ground_station="Nairobi", start_s=50, end_s=150)),
        ]

        granted, conflicts = GroundContactScheduler().schedule(requests)

        granted_ids = {sat.id for sat, _ in granted}
        assert "high" in granted_ids
        assert "low" not in granted_ids
        assert len(conflicts) == 1
        assert conflicts[0].satellite_id == "low"

    def test_conflict_reason_names_the_satellite_that_won(self):
        plane = _plane()
        winner = _sat("winner", plane, priority=10)
        loser = _sat("loser", plane, priority=0)
        requests = [
            (winner, ContactWindow(ground_station="Nairobi", start_s=0, end_s=100)),
            (loser, ContactWindow(ground_station="Nairobi", start_s=0, end_s=100)),
        ]

        _, conflicts = GroundContactScheduler().schedule(requests)

        assert isinstance(conflicts[0], GroundContactConflict)
        assert "winner" in conflicts[0].reason
