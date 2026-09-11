"""Tests for multi-planetary ops (comms delay, radiation, disconnected, fail-safe, security)."""

from app.multiplanetary.ops.comms_delay import CommsDelayModel, TargetBody
from app.multiplanetary.ops.radiation import (
    ComponentDoseTracker,
    RadiationEnvironment,
    RadHardStrategy,
    RadiationEventLevel,
)
from app.multiplanetary.ops.disconnected import (
    DisconnectedOpsManager,
    MissionPlaybook,
)
from app.multiplanetary.ops.fail_safe import FailSafeController, HealthSignal, SafeModeLevel
from app.multiplanetary.ops.security import CyberSecurityLayer, ThreatType


# ─── Comms Delay ───

def test_moon_delay():
    m = CommsDelayModel.for_target(TargetBody.MOON)
    assert m.owlt_seconds == 1.3
    assert m.round_trip_delay_s == 2.6
    assert not m.is_real_time_controllable()

def test_mars_delay_high_autonomy():
    m = CommsDelayModel.for_target(TargetBody.MARS)
    assert m.owlt_seconds == 780.0
    assert m.autonomy_level >= 3

def test_deep_space_max_autonomy():
    m = CommsDelayModel.for_target(TargetBody.DEEP_SPACE)
    assert m.autonomy_level == 5
    assert m.max_autonomous_operations_s == float("inf")

def test_leo_real_time():
    m = CommsDelayModel.for_target(TargetBody.EARTH_LEO)
    assert m.is_real_time_controllable()
    assert m.autonomy_level == 1

def test_comms_delay_to_dict():
    m = CommsDelayModel.for_target(TargetBody.MOON)
    d = m.to_dict()
    assert d["target_body"] == "moon"
    assert d["rtt_s"] == 2.6


# ─── Radiation ───

def test_component_dose_tracker():
    comp = ComponentDoseTracker("avionics", total_dose_gy=50.0, max_tolerance_gy=100.0)
    assert comp.dose_remaining_gy == 50.0
    assert comp.is_end_of_life is False

def test_component_end_of_life():
    comp = ComponentDoseTracker("avionics", total_dose_gy=110.0, max_tolerance_gy=100.0)
    assert comp.is_end_of_life is True

def test_component_needs_replacement():
    comp = ComponentDoseTracker("avionics", watchdog_resets=6)
    assert comp.needs_replacement is True

def test_radiation_environment_for_target():
    lunar = RadiationEnvironment.for_target("lunar")
    deep = RadiationEnvironment.for_target("deep_space")
    assert lunar.dose_gy_per_day() < deep.dose_gy_per_day()

def test_radiation_environment_spe():
    env = RadiationEnvironment.for_target("lunar")
    baseline = env.dose_gy_per_day()
    env.start_spe(rate_gy_per_hour=0.1)
    assert env.dose_gy_per_day() > baseline
    env.stop_spe()
    assert abs(env.dose_gy_per_day() - baseline) < 1e-9

def test_radiation_status():
    env = RadiationEnvironment.for_target("mars")
    status = env.status()
    assert status["target_body"] == "mars"
    assert "dose_per_day_gy" in status

def test_radhard_strategy_tick():
    env = RadiationEnvironment.for_target("mars")
    comp = ComponentDoseTracker("cpu")
    strategy = RadHardStrategy([comp])
    result = strategy.tick(env, dt_days=2.0)
    assert comp.total_dose_gy > 0
    assert "dose_applied_gy" in result

def test_radhard_strategy_watchdog():
    env = RadiationEnvironment.for_target("mars")
    comp = ComponentDoseTracker("cpu")
    strategy = RadHardStrategy()
    strategy.register_component(comp)
    assert strategy.reset_watchdog(comp) is True
    comp.watchdog_resets = 4
    assert strategy.reset_watchdog(comp) is True
    assert strategy.reset_watchdog(comp) is False

def test_radhard_strategy_latchup():
    comp = ComponentDoseTracker("cpu")
    strategy = RadHardStrategy()
    strategy.register_component(comp)
    assert strategy.handle_latchup(comp) is True
    comp.single_event_latchup_count = 2
    assert strategy.handle_latchup(comp) is True
    assert strategy.handle_latchup(comp) is False


# ─── Disconnected Ops ───

def test_disconnected_normal():
    mgr = DisconnectedOpsManager(autonomy_level=3, max_autonomous_s=3600.0)
    mgr.enter_disconnected(elapsed_s=0.0)
    state = mgr.tick(elapsed_s=100.0, battery_percent=90.0)
    assert state.fallback_safe is False

def test_disconnected_safe_mode_timeout():
    mgr = DisconnectedOpsManager(autonomy_level=3, max_autonomous_s=3600.0)
    mgr.enter_disconnected(elapsed_s=0.0)
    state = mgr.tick(elapsed_s=7200.0, battery_percent=90.0)
    assert state.fallback_safe is True
    assert state.playbook_active == "safe_mode"

def test_disconnected_safe_mode_low_battery():
    mgr = DisconnectedOpsManager(autonomy_level=3, max_autonomous_s=999999.0)
    mgr.enter_disconnected(elapsed_s=0.0)
    state = mgr.tick(elapsed_s=7200.0, battery_percent=5.0)
    assert state.fallback_safe is True

def test_disconnected_playbook_registration():
    mgr = DisconnectedOpsManager()
    mgr.register_playbook(MissionPlaybook(
        name="continue_survey",
        triggers={"min_battery": 20.0},
        actions=[{"action": "move_to_next_waypoint"}],
    ))
    mgr.enter_disconnected(0.0)
    state = mgr.tick(elapsed_s=100.0, battery_percent=90.0)
    assert state.playbook_active == "continue_survey"

def test_disconnected_execute_action():
    mgr = DisconnectedOpsManager()
    mgr.register_playbook(MissionPlaybook(
        name="continue_survey",
        triggers={"min_battery": 20.0},
        actions=[{"action": "move_to_next_waypoint"}],
    ))
    mgr.enter_disconnected(0.0)
    mgr.tick(elapsed_s=100.0, battery_percent=90.0)
    action = mgr.execute_playbook_action()
    assert action is not None
    assert "playbook" in action

def test_disconnected_safe_mode_action():
    mgr = DisconnectedOpsManager(max_autonomous_s=10.0)
    mgr.enter_disconnected(0.0)
    mgr.tick(elapsed_s=100.0, battery_percent=90.0)
    assert mgr.state.fallback_safe is True
    action = mgr.execute_playbook_action()
    assert action["action"] == "enter_safe_mode"


# ─── Fail-Safe ───

def test_fail_safe_normal():
    controller = FailSafeController()
    controller.register_signal(HealthSignal("battery", value=90.0, threshold_safe=30.0, threshold_caution=15.0))
    level = controller.check()
    assert level == SafeModeLevel.NORMAL

def test_fail_safe_low_battery():
    controller = FailSafeController()
    controller.register_signal(HealthSignal("battery", value=5.0, threshold_safe=30.0, threshold_caution=15.0))
    level = controller.check()
    assert level == SafeModeLevel.SAFE

def test_fail_safe_high_temp():
    controller = FailSafeController()
    controller.register_signal(HealthSignal("temperature", value=60.0, threshold_safe=50.0,
                                            threshold_caution=65.0, is_lower_better=True))
    assert controller.check() == SafeModeLevel.CAUTION

def test_fail_safe_extreme_temp_safe():
    controller = FailSafeController()
    controller.register_signal(HealthSignal("temperature", value=90.0, threshold_safe=50.0,
                                            threshold_caution=65.0, is_lower_better=True))
    assert controller.check() == SafeModeLevel.SAFE

def test_fail_safe_watchdog():
    controller = FailSafeController(max_watchdog_before_safe=3)
    assert controller.watchdog_reset() is True
    assert controller.watchdog_reset() is True
    assert controller.watchdog_reset() is False
    assert controller.is_safe_mode is True

def test_fail_safe_command_loss():
    controller = FailSafeController(command_loss_timeout_s=300.0)
    controller.command_received(0.0)
    assert controller.check(current_time=600.0) == SafeModeLevel.SAFE

def test_fail_safe_callback():
    events = []
    controller = FailSafeController()
    controller.register_safe_mode_callback(lambda old, new: events.append((old, new)))
    controller.register_signal(HealthSignal("battery", value=5.0, threshold_safe=30.0, threshold_caution=15.0))
    controller.check()
    assert len(events) == 1
    assert events[0][1] == "safe"

def test_fail_safe_reset():
    controller = FailSafeController()
    controller.register_signal(HealthSignal("battery", value=5.0, threshold_safe=30.0, threshold_caution=15.0))
    controller.check()
    assert controller.is_safe_mode is True
    controller.reset()
    assert controller.is_safe_mode is False

def test_fail_safe_status():
    controller = FailSafeController()
    status = controller.status()
    assert status["level"] == "normal"
    assert status["is_safe_mode"] is False


# ─── Security ───

def test_security_sign_verify():
    sec = CyberSecurityLayer(secret_key=b"test-key")
    payload = b"FIRE_LANDING_ENGINE"
    sig = sec.sign_command("cmd-1", payload, timestamp=1000.0)
    assert sec.verify_command("cmd-1", payload, timestamp=1000.0, signature=sig) is True

def test_security_rejects_bad_signature():
    sec = CyberSecurityLayer(secret_key=b"test-key")
    payload = b"FIRE_LANDING_ENGINE"
    sig = sec.sign_command("cmd-1", payload, timestamp=1000.0)
    bad = "0" * len(sig)
    assert sec.verify_command("cmd-1", payload, timestamp=1000.0, signature=bad) is False

def test_security_replay_detection():
    sec = CyberSecurityLayer(secret_key=b"test-key")
    payload = b"COMMAND"
    sig = sec.sign_command("cmd-replay", payload, timestamp=1000.0)
    assert sec.verify_command("cmd-replay", payload, timestamp=1000.0, signature=sig) is True
    assert sec.verify_command("cmd-replay", payload, timestamp=1000.0, signature=sig) is False
    assert any(e.threat == ThreatType.REPLAY_ATTACK for e in sec.events)

def test_security_config_integrity():
    sec = CyberSecurityLayer(secret_key=b"test-key")
    sec.register_config_hash("flight-config", b"original content")
    assert sec.verify_config("flight-config", b"original content") is True
    assert sec.verify_config("flight-config", b"tampered content") is False
    assert any(e.threat == ThreatType.CONFIG_TAMPER for e in sec.events)

def test_security_rate_limit():
    sec = CyberSecurityLayer(secret_key=b"test-key", rate_limit_per_minute=5)
    for i in range(15):
        sig = sec.sign_command(f"rate-{i}", b"x", timestamp=float(i))
        sec.verify_command(f"rate-{i}", b"x", timestamp=float(i), signature=sig)
    assert any(e.threat == ThreatType.ANOMALOUS_VOLUME for e in sec.events)

def test_security_blocked_source():
    sec = CyberSecurityLayer(secret_key=b"test-key")
    sec._blocked_sources.add("192.168.99.99")
    sig = sec.sign_command("cmd-x", b"x", timestamp=1.0)
    assert sec.verify_command("cmd-x", b"x", timestamp=1.0, signature=sig,
                         source_ip="192.168.99.99") is False
    assert any(e.threat == ThreatType.UNAUTHORIZED_ACCESS for e in sec.events)

def test_security_level_nominal():
    sec = CyberSecurityLayer(secret_key=b"test-key")
    assert sec.level.value == "nominal"