"""Tests for AURORA robotics core (no DB, no network, no hardware)."""

import math
import pytest
from app.robotics.core.robot import Pose3D, Velocity3D, RobotSnapshot, RobotState, Sensor, SensorReading, Actuator, ActuatorCommand, Robot
from app.robotics.navigation import Waypoint, Path, GridMap, astar, SimpleNavigator, NavMode
from app.robotics.perception import (
    BBox2D, Detection, DetectionClass, PerceptionResult,
    SyntheticPerceptionEngine, SegmentationMask,
)
from app.robotics.control import PIDGains, PIDController, VelocityPIDController, PositionPIDController
from app.robotics.simulation import SimConfig, SimulatedWorld, KinematicSimulator
from app.robotics.telemetry import TelemetryLogger


class TestPose3D:
    def test_default_is_origin(self):
        p = Pose3D()
        assert p.x == 0.0 and p.y == 0.0 and p.z == 0.0
        assert p.qw == 1.0

    def test_to_dict(self):
        d = Pose3D(x=1.0, y=2.0).to_dict()
        assert d["x"] == 1.0 and d["y"] == 2.0


class TestWaypoint:
    def test_distance(self):
        a = Waypoint(0, 0)
        b = Waypoint(3, 4)
        assert a.distance_to(b) == pytest.approx(5.0)

    def test_frozen(self):
        wp = Waypoint(1, 2)
        with pytest.raises(AttributeError):
            wp.x = 5  # type: ignore


class TestGridMap:
    def test_occupancy(self):
        g = GridMap(10, 10, 1.0)
        assert g.is_free(5, 5)
        g.set_occupied(5, 5)
        assert not g.is_free(5, 5)
        g.set_free(5, 5)
        assert g.is_free(5, 5)

    def test_world_grid_roundtrip(self):
        g = GridMap(100, 100, 0.5)
        gx, gy = g.world_to_grid(5.25, 10.75)
        wx, wy = g.grid_to_world(gx, gy)
        assert wx == pytest.approx(5.25, abs=0.5)
        assert wy == pytest.approx(10.75, abs=0.5)


class TestAStar:
    def test_finds_path_on_open_grid(self):
        g = GridMap(20, 20)
        start = Waypoint(1, 1)
        goal = Waypoint(18, 18)
        path = astar(g, start, goal)
        assert path is not None
        assert len(path.waypoints) > 2

    def test_blocked_grid_returns_none(self):
        g = GridMap(10, 10)
        for x in range(10):
            g.set_occupied(x, 5)
        path = astar(g, Waypoint(0, 0), Waypoint(0, 9))
        assert path is None


class TestSimpleNavigator:
    def test_navigate_plans_path(self):
        g = GridMap(20, 20)
        nav = SimpleNavigator(g)
        path = nav.navigate_from_to(Waypoint(1, 1), Waypoint(18, 18))
        assert path is not None
        assert len(path.waypoints) > 2

    def test_update_returns_next_waypoint(self):
        g = GridMap(20, 20)
        nav = SimpleNavigator(g)
        nav.navigate_from_to(Waypoint(0, 0), Waypoint(19, 19))
        nav.current_goal = Waypoint(19, 19)
        wp = nav.update(Pose3D(x=0, y=0), 0.1)
        assert wp is not None


class TestBBox2D:
    def test_iou_identical(self):
        a = BBox2D(0, 0, 10, 10)
        assert a.iou(a) == pytest.approx(1.0)

    def test_iou_no_overlap(self):
        a = BBox2D(0, 0, 5, 5)
        b = BBox2D(10, 10, 15, 15)
        assert a.iou(b) == 0.0


class TestSyntheticPerception:
    def test_returns_empty_on_no_obstacles(self):
        eng = SyntheticPerceptionEngine()
        result = eng.process_frame(None, 0.0)
        assert len(result.detections) == 0

    def test_returns_configured_obstacles(self):
        obs = [{"x_min": 10, "y_min": 10, "x_max": 50, "y_max": 50, "class": "hazard", "confidence": 0.95}]
        eng = SyntheticPerceptionEngine(obstacles=obs)
        result = eng.process_frame(None, 1.0)
        assert len(result.detections) == 1
        assert result.detections[0].detection_class == DetectionClass.HAZARD


class TestPIDController:
    def test_converges_to_zero_error(self):
        pid = PIDController(PIDGains(kp=1.0, ki=0.1, kd=0.01))
        error = 10.0
        for _ in range(100):
            output = pid.compute(error, 0.1)
            error -= output * 0.1
        assert abs(error) < 1.0

    def test_output_clamps(self):
        pid = PIDController(PIDGains(kp=100.0, output_min=-5.0, output_max=5.0))
        out = pid.compute(100.0, 0.1)
        assert out == pytest.approx(5.0)


class TestKinematicSimulator:
    def test_tick_advances_time(self):
        world = SimulatedWorld(GridMap(20, 20))
        sim = KinematicSimulator(world, SimConfig(dt=0.1))
        sim.reset()
        snap = sim.tick(0.5, 0.0)
        assert snap.timestamp == pytest.approx(0.1)
        assert snap.pose.x > 0

    def test_battery_drains(self):
        world = SimulatedWorld(GridMap(20, 20))
        sim = KinematicSimulator(world, SimConfig(dt=1.0))
        sim.reset()
        for _ in range(100):
            sim.tick(1.0, 0.0)
        assert sim.battery_percent < 100.0


class TestTelemetryLogger:
    def test_log_and_recent(self):
        log = TelemetryLogger()
        log.log_sensor("imu", {"ax": 0.1})
        log.log_sensor("imu", {"ax": 0.2})
        recent = log.recent("sensor", n=5)
        assert len(recent) == 2

    def test_counters(self):
        log = TelemetryLogger()
        log.log("nav", "planner", {"cost": 5.0})
        log.log("nav", "planner", {"cost": 3.0})
        c = log.counters()
        assert c["nav:planner"] == 2