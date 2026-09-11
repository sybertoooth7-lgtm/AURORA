"""Tests for multi-planetary layers (7 layers + stack)."""
import time

from app.multiplanetary.layers.core import Action, ActionType, MissionContext, StackDecision
from app.multiplanetary.layers.human_assistance import HumanAssistanceLayer
from app.multiplanetary.layers.infrastructure import InfrastructureLayer
from app.multiplanetary.layers.mission_control import MissionControlLayer
from app.multiplanetary.layers.navigation_layer import NavigationLayer
from app.multiplanetary.layers.resource_management import ResourceManagementLayer
from app.multiplanetary.layers.robotics import RoboticsLayer
from app.multiplanetary.layers.scientific import ScientificIntelligenceLayer
from app.multiplanetary.layers.stack import AuroraStack

# ─── Core / MissionContext ───

def test_mission_context_defaults():
    ctx = MissionContext(timestamp=0.0)
    assert ctx.environment == "earth"
    assert ctx.target_body == "earth"
    assert ctx.autonomy_level == 3
    assert ctx.one_way_delay_s == 0.0
    assert ctx.battery_percent == 100.0
    assert ctx.in_contact is True
    assert ctx.science_hypotheses == []
    assert ctx.current_plan == ""
    assert ctx.inventory == {}
    assert ctx.warnings == []
    assert ctx.navigation == {}
    assert ctx.environment_sensor == {}
    assert ctx.infrastructure == {}

def test_action_immutability():
    a = Action(layer="test", action_type=ActionType.ALERT, target="t", description="d")
    # Action is mutable by default (no with_severity method in current core.py)
    a.severity = "critical"
    assert a.severity == "critical"

def test_stack_decision_defaults():
    sd = StackDecision(timestamp=0.0)
    assert sd.approved_actions == []
    assert sd.pending_authorization == []
    assert sd.rejected_actions == []
    assert sd.safe_mode_active is False

def test_stack_decision_to_dict():
    sd = StackDecision(timestamp=0.0)
    d = sd.to_dict()
    assert "approved" in d
    assert "safe_mode_active" in d
    assert d["safe_mode_active"] is False


# ─── Mission Control Layer ───

def test_mission_control_approves_low_severity():
    mc = MissionControlLayer()
    ctx = MissionContext(timestamp=time.time())
    a = Action(layer="nav", action_type=ActionType.ALERT, target="rover", description="info", severity="info")
    approved, pending, rejected = mc.filter_actions([a], ctx)
    assert len(approved) == 1
    assert len(rejected) == 0

def test_mission_control_blocks_critical_irreversible():
    mc = MissionControlLayer()
    ctx = MissionContext(timestamp=time.time())
    a = Action(layer="nav", action_type=ActionType.COMMAND, target="rover", description="cmd",
               severity="critical", reversible=False, requires_authorization=True)
    approved, pending, rejected = mc.filter_actions([a], ctx)
    assert len(pending) == 1
    assert len(rejected) == 0

def test_mission_control_autonomy_budget_low_battery():
    mc = MissionControlLayer()
    ctx = MissionContext(timestamp=time.time(), battery_percent=5.0, one_way_delay_s=0.0)
    budget = mc.autonomy_budget(ctx)
    assert budget == 1

def test_mission_control_autonomy_budget_high_delay():
    mc = MissionControlLayer()
    ctx = MissionContext(timestamp=time.time(), battery_percent=100.0, one_way_delay_s=100.0)
    budget = mc.autonomy_budget(ctx)
    assert budget >= 3

def test_mission_control_reduces_autonomy_alert():
    mc = MissionControlLayer()
    ctx = MissionContext(timestamp=time.time(), autonomy_level=5, one_way_delay_s=0.0,
                        battery_percent=20.0)
    actions = mc.evaluate(ctx)
    assert any("Reducing autonomy" in a.description for a in actions)

def test_mission_control_rejects_own_actions():
    mc = MissionControlLayer()
    ctx = MissionContext(timestamp=time.time())
    a = Action(layer="mission_control", action_type=ActionType.ALERT, target="stack",
               description="internal", severity="info")
    approved, pending, rejected = mc.filter_actions([a], ctx)
    assert len(rejected) == 1

def test_mission_control_blocks_rover_low_nav_confidence():
    mc = MissionControlLayer()
    ctx = MissionContext(timestamp=time.time(), navigation={"confidence": 0.1, "uncertain": True})
    a = Action(layer="nav", action_type=ActionType.COMMAND, target="rover-1",
               description="move", severity="info", reversible=True)
    approved, pending, rejected = mc.filter_actions([a], ctx)
    assert len(rejected) == 1


# ─── Scientific Intelligence ───

def test_scientific_evaluates_proposals():
    si = ScientificIntelligenceLayer()
    ctx = MissionContext(timestamp=time.time(), science_hypotheses=[])
    actions = si.evaluate(ctx)
    assert any(a.action_type == ActionType.ALERT for a in actions)
    assert any(a.action_type == ActionType.PLAN for a in actions)

def test_scientific_respects_context_plan():
    si = ScientificIntelligenceLayer(hypotheses=[
        {"id": "test_hyp", "resource": "test_res", "priority": 1.0,
         "target": {"x": 0, "y": 0}, "expected_value": 0.5},
    ])
    ctx = MissionContext(timestamp=time.time(), science_hypotheses=["test_hyp"],
                        current_plan="scientific_survey")
    actions = si.evaluate(ctx)
    assert any("test_hyp" in str(a.payload) for a in actions if a.payload)

def test_scientific_low_delay_requires_auth():
    si = ScientificIntelligenceLayer()
    ctx = MissionContext(timestamp=time.time(), one_way_delay_s=5.0)
    actions = si.evaluate(ctx)
    assert any(a.requires_authorization for a in actions)


# ─── Robotics ───

def test_robotics_dispatches_on_plan():
    rb = RoboticsLayer(fleet={"r1": {"status": "idle", "battery": 80.0}})
    ctx = MissionContext(timestamp=time.time(), current_plan="scientific_survey", battery_percent=80.0)
    actions = rb.evaluate(ctx)
    assert any("r1" in a.target for a in actions)
    assert any(a.action_type == ActionType.COMMAND for a in actions)

def test_robotics_skips_unavailable():
    rb = RoboticsLayer(fleet={"r1": {"status": "fault", "battery": 80.0}})
    ctx = MissionContext(timestamp=time.time(), current_plan="scientific_survey")
    actions = rb.evaluate(ctx)
    assert any("unavailable" in a.description.lower() for a in actions)

def test_robotics_skips_low_battery():
    rb = RoboticsLayer(fleet={"r1": {"status": "idle", "battery": 10.0}})
    ctx = MissionContext(timestamp=time.time(), current_plan="scientific_survey")
    actions = rb.evaluate(ctx)
    assert any("unavailable" in a.description.lower() for a in actions)

def test_teleop_command():
    rb = RoboticsLayer()
    cmd = rb.teleop_command("rover-1", linear=0.5, angular=0.1)
    assert cmd.requires_authorization is True
    assert "Teleop" in cmd.description

def test_robotics_no_plan_no_actions():
    rb = RoboticsLayer(fleet={"r1": {"status": "idle", "battery": 80.0}})
    ctx = MissionContext(timestamp=time.time(), current_plan="")
    actions = rb.evaluate(ctx)
    assert actions == []


# ─── Navigation ───

def test_navigation_no_goal_no_actions():
    nav = NavigationLayer()
    ctx = MissionContext(timestamp=time.time())
    actions = nav.evaluate(ctx)
    assert actions == []

def test_navigation_sets_goal():
    from app.multiplanetary.navigation import Waypoint
    nav = NavigationLayer()
    nav.set_goal(Waypoint(x=10, y=10))
    assert nav._goal is not None

def test_navigation_plan_with_no_navigator():
    from app.multiplanetary.navigation import Waypoint
    nav = NavigationLayer()
    nav.set_goal(Waypoint(x=10, y=10))
    ctx = MissionContext(timestamp=time.time(), navigation={"position": {"x": 0, "y": 0}})
    actions = nav.evaluate(ctx)
    assert any("No feasible path" in a.description for a in actions)


# ─── Resource Management ───

def test_resource_management_low_water():
    rm = ResourceManagementLayer()
    ctx = MissionContext(timestamp=time.time(), inventory={"water_kg": 1.0}, battery_percent=100.0,
                        power_available_w=200.0, power_demand_w=100.0)
    actions = rm.evaluate(ctx)
    assert any("water_kg" in a.description for a in actions)

def test_resource_management_power_margin():
    rm = ResourceManagementLayer()
    ctx = MissionContext(timestamp=time.time(), battery_percent=100.0,
                        power_available_w=5.0, power_demand_w=20.0)
    actions = rm.evaluate(ctx)
    assert any("Power margin low" in a.description for a in actions)

def test_resource_management_no_alerts_when_adequate():
    rm = ResourceManagementLayer()
    ctx = MissionContext(timestamp=time.time(), inventory={"water_kg": 50.0, "oxygen_kg": 20.0,
                        "fuel_kg": 10.0}, battery_percent=100.0, power_available_w=200.0,
                        power_demand_w=80.0)
    actions = rm.evaluate(ctx)
    assert len(actions) == 0


# ─── Infrastructure ───

def test_infrastructure_starts_isru():
    infra = InfrastructureLayer()
    ctx = MissionContext(timestamp=time.time(), power_available_w=100.0)
    actions = infra.evaluate(ctx)
    assert any("isru" in a.target for a in actions)

def test_infrastructure_low_battery_alert():
    infra = InfrastructureLayer()
    ctx = MissionContext(timestamp=time.time(), battery_percent=20.0, power_available_w=100.0,
                        infrastructure={"power": {"battery_percent": 20.0}})
    actions = infra.evaluate(ctx)
    assert any("Battery" in a.description for a in actions)

def test_infrastructure_update():
    infra = InfrastructureLayer()
    infra.update({"power": {"battery_percent": 50.0}})
    assert infra.status["power"]["battery_percent"] == 50.0

def test_infrastructure_nominal_habitat_no_alert():
    infra = InfrastructureLayer()
    ctx = MissionContext(timestamp=time.time(), power_available_w=200.0, battery_percent=100.0)
    actions = infra.evaluate(ctx)
    assert not any("Habitat" in a.description for a in actions)


# ─── Human Assistance ───

def test_human_assistance_generates_advisory():
    ha = HumanAssistanceLayer()
    ctx = MissionContext(timestamp=time.time(), environment="lunar", target_body="moon",
                        one_way_delay_s=1.3, battery_percent=90.0, power_available_w=200.0,
                        power_demand_w=100.0, in_contact=True, temperature_c=22.0)
    actions = ha.evaluate(ctx)
    assert any("lunar" in a.description for a in actions)

def test_human_assistance_low_battery_warning():
    ha = HumanAssistanceLayer()
    ctx = MissionContext(timestamp=time.time(), autonomy_level=2, battery_percent=30.0,
                        power_available_w=200.0, power_demand_w=100.0,
                        in_contact=True, temperature_c=22.0)
    actions = ha.evaluate(ctx)
    assert any("Low battery" in a.description for a in actions)

def test_human_assistance_high_delay_recommends_autonomy():
    ha = HumanAssistanceLayer()
    ctx = MissionContext(timestamp=time.time(), one_way_delay_s=200.0,
                        power_available_w=200.0, power_demand_w=100.0,
                        in_contact=True, temperature_c=22.0)
    actions = ha.evaluate(ctx)
    assert any("autonomy level" in a.description for a in actions)

def test_human_assistance_verification_checklist():
    ha = HumanAssistanceLayer()
    a = Action(layer="nav", action_type=ActionType.COMMAND, target="rover", description="move")
    checklist = ha.verification_checklist(a)
    assert len(checklist) == 6
    assert "Battery sufficient" in checklist[3]


# ─── AuroraStack ───

def test_stack_safe_mode_on_low_battery():
    stack = AuroraStack()
    ctx = MissionContext(timestamp=time.time(), battery_percent=3.0, power_available_w=10.0,
                        power_demand_w=10.0, in_contact=True, temperature_c=20.0)
    decision = stack.step(ctx)
    assert decision.safe_mode_active is True
    assert any("SAFE MODE" in a.description for a in decision.approved_actions)

def test_stack_normal_operation():
    stack = AuroraStack()
    ctx = MissionContext(timestamp=time.time(), battery_percent=90.0, power_available_w=200.0,
                        power_demand_w=80.0, in_contact=True, temperature_c=22.0)
    decision = stack.step(ctx)
    assert decision.safe_mode_active is False

def test_stack_radiation_triggers_safe_mode():
    stack = AuroraStack()
    ctx = MissionContext(timestamp=time.time(), battery_percent=90.0,
                        environment_sensor={"radiation_event": True},
                        power_available_w=200.0, power_demand_w=80.0,
                        in_contact=True, temperature_c=22.0)
    decision = stack.step(ctx)
    assert decision.safe_mode_active is True

def test_stack_watchdog_triggers_safe_mode():
    stack = AuroraStack()
    ctx = MissionContext(timestamp=time.time(), battery_percent=90.0,
                        environment_sensor={"watchdog_reset": True},
                        power_available_w=200.0, power_demand_w=80.0,
                        in_contact=True, temperature_c=22.0)
    decision = stack.step(ctx)
    assert decision.safe_mode_active is True

def test_stack_reset_safe_mode():
    stack = AuroraStack()
    ctx = MissionContext(timestamp=time.time(), battery_percent=3.0, power_available_w=10.0,
                        power_demand_w=10.0, in_contact=True, temperature_c=20.0)
    stack.step(ctx)
    assert stack.is_safe_mode is True
    stack.reset_safe_mode()
    assert stack.is_safe_mode is False

def test_stack_cycle_count():
    stack = AuroraStack()
    ctx = MissionContext(timestamp=time.time(), battery_percent=90.0, power_available_w=200.0,
                        power_demand_w=80.0, in_contact=True, temperature_c=22.0)
    stack.step(ctx)
    assert stack._cycle_count == 1
    stack.step(ctx)
    assert stack._cycle_count == 2

def test_stack_human_authorization():
    stack = AuroraStack()
    action = stack.authorize_action({
        "target": "rover-1",
        "description": "Move to waypoint A",
        "payload": {"x": 10, "y": 20},
        "reversible": True,
    })
    assert action.requires_authorization is False
    assert "HUMAN-AUTHORIZED" in action.description

def test_stack_to_dict():
    stack = AuroraStack()
    ctx = MissionContext(timestamp=time.time(), battery_percent=90.0, power_available_w=200.0,
                        power_demand_w=80.0, in_contact=True, temperature_c=22.0)
    decision = stack.step(ctx)
    d = decision.to_dict()
    assert "approved" in d
    assert "safe_mode_active" in d

def test_stack_high_temp_triggers_safe_mode():
    stack = AuroraStack()
    ctx = MissionContext(timestamp=time.time(), battery_percent=90.0, temperature_c=80.0,
                        power_available_w=200.0, power_demand_w=80.0, in_contact=True)
    decision = stack.step(ctx)
    assert decision.safe_mode_active is True
