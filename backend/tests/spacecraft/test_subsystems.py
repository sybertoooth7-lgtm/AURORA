"""Tests for CubeSat spacecraft subsystems (no DB, no network)."""

import math
import pytest
from app.spacecraft.adcs import ADCS, Quaternion, AttitudeState, SunSensor, Magnetometer, ReactionWheel
from app.spacecraft.power import PowerSystem, SolarPanelModel, BatteryModel
from app.spacecraft.thermal import ThermalModel, ThermalState
from app.spacecraft.comms import RadioTransceiver, LinkBudget, Packet, GroundStation
from app.spacecraft.payload import ImagingPayload, PayloadManager, PayloadMode
from app.spacecraft.fsw import FlightSoftware, TaskScheduler, FaultManager, FaultSeverity, FSWMode
from app.spacecraft.mission import MissionTimeline, GroundSegment, TelemetryDownlink, MissionPhase
from app.spacecraft.simulation import SpacecraftSimulator, OrbitalState, EclipseModel


class TestQuaternion:
    def test_identity(self):
        q = Quaternion()
        assert q.w == 1.0
        r, p, y = q.to_euler_deg()
        assert r == pytest.approx(0.0, abs=0.1)
        assert p == pytest.approx(0.0, abs=0.1)

    def test_normalized(self):
        q = Quaternion(2, 0, 0, 0)
        n = q.normalized()
        assert n.w == pytest.approx(1.0)


class TestADCS:
    def test_tick_updates_state(self):
        adcs = ADCS()
        state = adcs.tick(1.0)
        assert isinstance(state, AttitudeState)

    def test_detumble(self):
        adcs = ADCS()
        for w in adcs.wheels:
            w.rpm = 5000.0
        adcs.detumble()
        for w in adcs.wheels:
            assert w.rpm == 0.0


class TestSolarPanel:
    def test_no_power_in_eclipse(self):
        panel = SolarPanelModel()
        assert panel.power_w(1.0, eclipse=True) == 0.0

    def test_power_scales_with_angle(self):
        panel = SolarPanelModel()
        p1 = panel.power_w(1.0)
        p05 = panel.power_w(0.5)
        assert p1 > p05


class TestBattery:
    def test_discharge(self):
        bat = BatteryModel(capacity_wh=10.0)
        assert bat.soc_percent == pytest.approx(100.0)
        bat.discharge(5.0)
        assert bat.soc_percent == pytest.approx(50.0)

    def test_charge(self):
        bat = BatteryModel(capacity_wh=10.0)
        bat.discharge(8.0)
        bat.charge(5.0)
        assert bat.soc_percent > 20.0

    def test_depleted(self):
        bat = BatteryModel(capacity_wh=1.0)
        bat.discharge(1.0)
        assert bat.is_depleted


class TestPowerSystem:
    def test_tick_eclipse_drains_battery(self):
        ps = PowerSystem()
        bgt1 = ps.tick(60.0, sun_angle_cos=1.0, eclipse=False)
        bgt2 = ps.tick(60.0, sun_angle_cos=0.0, eclipse=True)
        assert bgt2.battery_soc_percent < bgt1.battery_soc_percent


class TestThermalModel:
    def test_tick_updates_temperature(self):
        tm = ThermalModel()
        state = tm.tick(10.0, eclipse=True)
        assert isinstance(state, ThermalState)
        assert state.temperature_c < 25.0

    def test_heater_turns_on_when_cold(self):
        tm = ThermalModel(min_operating_c=-10.0, initial_temp_c=-15.0)
        state = tm.tick(1.0, eclipse=True)
        assert state.heater_on

    def test_heater_turns_off_when_warm(self):
        tm = ThermalModel(min_operating_c=-10.0, initial_temp_c=25.0)
        state = tm.tick(1.0, eclipse=False, sun_angle_cos=1.0)
        assert not state.heater_on


class TestLinkBudget:
    def test_path_loss_increases_with_distance(self):
        lb = LinkBudget()
        loss100 = lb.free_space_path_loss_db(100)
        loss1000 = lb.free_space_path_loss_db(1000)
        assert loss1000 > loss100

    def test_max_range_positive(self):
        lb = LinkBudget()
        assert lb.max_range_km() > 0


class TestRadioTransceiver:
    def test_turn_on_off(self):
        radio = RadioTransceiver()
        radio.turn_on()
        assert radio.mode.value == "receive"
        radio.turn_off()
        assert radio.mode.value == "off"

    def test_queue_packet(self):
        radio = RadioTransceiver()
        radio.turn_on()
        pkt = Packet(source="sat", dest="gs", payload=b"hello")
        radio.queue_packet(pkt)
        assert len(radio._tx_buffer) == 1


class TestImagingPayload:
    def test_capture_and_store(self):
        cam = ImagingPayload(storage_capacity_mb=100.0)
        cam.power_on()
        img = cam.capture(0.0, -1.2, 36.8)
        assert img is not None
        assert cam.image_count == 1

    def test_storage_full_blocks_capture(self):
        cam = ImagingPayload(storage_capacity_mb=5.0, data_per_image_mb=5.0)
        cam.power_on()
        cam.capture(0.0, 0, 0)
        result = cam.capture(1.0, 0, 0)
        assert result is None


class TestTaskScheduler:
    def test_schedule_and_tick(self):
        sched = TaskScheduler()
        called = []
        sched.schedule("test", lambda: called.append(1), interval_s=0.0)
        executed = sched.tick(0.0)
        assert "test" in executed
        assert len(called) == 1


class TestFaultManager:
    def test_report_fault(self):
        fm = FaultManager()
        evt = fm.report_fault(0.0, "power", FaultSeverity.WARNING, "low battery")
        assert evt.subsystem == "power"
        assert fm.critical_count == 0

    def test_critical_fault(self):
        fm = FaultManager()
        fm.report_fault(0.0, "adcs", FaultSeverity.CRITICAL, "pointing loss")
        assert fm.critical_count == 1


class TestMissionTimeline:
    def test_default_timeline(self):
        mt = MissionTimeline(mission_duration_days=365.0)
        mt.default_timeline()
        phase = mt.tick(0.0)
        assert phase == MissionPhase.LAUNCH

    def test_elapsed_days(self):
        mt = MissionTimeline()
        mt.tick(86400.0)
        assert mt.elapsed_days == pytest.approx(1.0)


class TestEclipseModel:
    def test_eclipse_at_180_deg(self):
        em = EclipseModel()
        assert em.is_in_eclipse(180.0)

    def test_no_eclipse_at_0_deg(self):
        em = EclipseModel()
        assert not em.is_in_eclipse(0.0)


class TestOrbitalState:
    def test_update_advances_true_anomaly(self):
        os = OrbitalState()
        os.update(60.0)
        assert os.true_anomaly_deg > 0

    def test_velocity(self):
        os = OrbitalState(altitude_km=400.0)
        v = os.velocity_kms()
        assert 7.0 < v < 8.0


class TestSpacecraftSimulator:
    def test_tick_produces_state(self):
        sim = SpacecraftSimulator(altitude_km=400.0)
        state = sim.tick()
        assert state.fsw_mode == "nominal"

    def test_run_produces_history(self):
        sim = SpacecraftSimulator()
        history = sim.run(10.0)
        assert len(history) == 10