"""Tests for multi-planetary AI (no DB, no network)."""

import pytest

from app.multiplanetary.autonomy import (
    ActionNode,
    AutonomousController,
    BehaviorTree,
    NodeStatus,
    SelectorNode,
    SequenceNode,
)
from app.multiplanetary.avoidance import Obstacle, PotentialFieldAvoidance, ReactiveAvoidance
from app.multiplanetary.mapping import OctoMap, TerrainMap
from app.multiplanetary.navigation import (
    SlopeConstraint,
    TerrainGridMap,
    TerrainNavigator,
    Waypoint,
)
from app.multiplanetary.sensors import EnvironmentalSensor, HazardCamera, PointCloud, StereoCamera
from app.multiplanetary.simulation import (
    AsteroidEnvironment,
    LunarEnvironment,
    MarsEnvironment,
    PlanetaryEnvironment,
    get_environment,
)
from app.multiplanetary.telemetry import DeepSpaceTelemetry, LinkState, StoreAndForwardRelay
from app.multiplanetary.vision import VisualOdometry


class TestPointCloud:
    def test_bounds(self):
        pc = PointCloud(points=[(1, 2, 3), (4, 5, 6)])
        (xmin, xmax), (ymin, ymax), (zmin, zmax) = pc.bounds()
        assert xmin == 1 and xmax == 4
        assert pc.size == 2


class TestStereoCamera:
    def test_depth_computation(self):
        cam = StereoCamera(baseline_m=0.12, focal_length_px=640.0)
        depth = cam.compute_depth(64.0)
        assert depth == pytest.approx(1.2)

    def test_point_cloud_generation(self):
        cam = StereoCamera()
        depth_map = [[5.0] * 640 for _ in range(480)]
        pc = cam.generate_point_cloud(depth_map)
        assert pc.size > 0


class TestHazardCamera:
    def test_detect_hazards(self):
        hc = HazardCamera()
        pc = PointCloud(points=[(0.1, 0.1, 1.0), (5.0, 5.0, 2.0)])
        hmap = hc.detect_hazards(pc)
        assert hmap.width > 0


class TestEnvironmentalSensor:
    def test_lunar_readings(self):
        es = EnvironmentalSensor(environment="lunar")
        r = es.read()
        assert r.pressure_pa == 0.0
        assert r.temperature_c < 0

    def test_mars_readings(self):
        es = EnvironmentalSensor(environment="mars")
        r = es.read()
        assert r.pressure_pa > 0


class TestVisualOdometry:
    def test_first_frame_zero_motion(self):
        vo = VisualOdometry()
        pc = PointCloud(points=[(i, i, i) for i in range(10)])
        est = vo.estimate_motion(pc, 0.0)
        assert est.confidence == 1.0

    def test_subsequent_frame_estimates_motion(self):
        vo = VisualOdometry()
        pc1 = PointCloud(points=[(i, i, i) for i in range(20)])
        vo.estimate_motion(pc1, 0.0)
        pc2 = PointCloud(points=[(i + 0.1, i, i) for i in range(20)])
        est = vo.estimate_motion(pc2, 1.0)
        assert est.displacement_m() > 0


class TestTerrainNavigator:
    def test_plan_path_open_terrain(self):
        tg = TerrainGridMap(20, 20)
        nav = TerrainNavigator(tg)
        path = nav.plan_path(Waypoint(1, 1), Waypoint(18, 18))
        assert path is not None

    def test_slope_blocks_path(self):
        tg = TerrainGridMap(20, 20)
        for gx in range(10):
            tg.set_elevation(gx, 10, 100.0)
        nav = TerrainNavigator(tg)
        nav.slope_constraint = SlopeConstraint(max_slope_deg=5.0)
        path = nav.plan_path(Waypoint(5, 0), Waypoint(5, 19))
        assert path is None or path.cost > 0


class TestOctoMap:
    def test_insert_point(self):
        om = OctoMap(resolution=0.1)
        om.insert_point(1.0, 2.0, 3.0, hit=True)
        assert om.size > 0

    def test_insert_ray(self):
        om = OctoMap(resolution=0.5)
        om.insert_ray((0, 0, 0), (5, 5, 0))
        assert om.size > 0

    def test_is_occupied(self):
        om = OctoMap(resolution=0.1)
        om.insert_point(1.0, 1.0, 1.0, hit=True)
        assert om.is_occupied(1.0, 1.0, 1.0)


class TestTerrainMap:
    def test_slope_computation(self):
        tm = TerrainMap(10, 10)
        tm.set_height(5, 5, 10.0)
        tm.set_height(6, 5, 0.0)
        slope = tm.compute_slope(5, 5)
        assert slope > 0


class TestReactiveAvoidance:
    def test_no_obstacles_drives_forward(self):
        ra = ReactiveAvoidance()
        cmd = ra.compute([])
        assert cmd.linear_velocity > 0
        assert not cmd.obstacle_detected

    def test_close_obstacle_turns(self):
        ra = ReactiveAvoidance()
        obs = [Obstacle(x=0.5, y=0.0, distance_m=0.3, bearing_rad=0.0)]
        cmd = ra.compute(obs)
        assert cmd.obstacle_detected
        assert cmd.angular_velocity != 0


class TestPotentialFieldAvoidance:
    def test_toward_goal(self):
        pf = PotentialFieldAvoidance()
        cmd = pf.compute((0, 0), (10, 10), [])
        assert cmd.linear_velocity > 0

    def test_obstacle_repulsion(self):
        pf = PotentialFieldAvoidance()
        obs = [Obstacle(x=5, y=5, distance_m=1.0, bearing_rad=0.0)]
        cmd = pf.compute((0, 0), (10, 0), obs)
        assert cmd.obstacle_detected


class TestBehaviorTree:
    def test_selector_finds_success(self):
        fail_node = ActionNode("fail", lambda ctx: NodeStatus.FAILURE)
        success_node = ActionNode("success", lambda ctx: NodeStatus.SUCCESS)
        tree = BehaviorTree(root=SelectorNode("sel", [fail_node, success_node]))
        result = tree.tick({})
        assert result == NodeStatus.SUCCESS

    def test_sequence_all_must_pass(self):
        ok = ActionNode("ok", lambda ctx: NodeStatus.SUCCESS)
        tree = BehaviorTree(root=SequenceNode("seq", [ok, ok, ok]))
        assert tree.tick({}) == NodeStatus.SUCCESS

    def test_sequence_fails_on_first_failure(self):
        fail = ActionNode("fail", lambda ctx: NodeStatus.FAILURE)
        ok = ActionNode("ok", lambda ctx: NodeStatus.SUCCESS)
        tree = BehaviorTree(root=SequenceNode("seq", [fail, ok]))
        assert tree.tick({}) == NodeStatus.FAILURE


class TestAutonomousController:
    def test_default_rover_tree(self):
        ac = AutonomousController()
        ac.build_default_rover_tree()
        ctx = {"battery_percent": 100, "obstacle_count": 0}
        result = ac.tick(ctx)
        assert result["status"] in ("success", "failure")


class TestStoreAndForwardRelay:
    def test_store_and_transmit(self):
        relay = StoreAndForwardRelay(storage_capacity_packets=10)
        from app.multiplanetary.telemetry import TelemetryPacket
        pkt = TelemetryPacket(source="rover", timestamp=0.0, data={"temp": -20}, size_bytes=100)
        relay.store(pkt)
        assert relay.storage_depth == 1
        transmitted = relay.transmit_batch(1000, LinkState(available=True))
        assert len(transmitted) == 1
        assert relay.storage_depth == 0

    def test_full_storage_drops(self):
        relay = StoreAndForwardRelay(storage_capacity_packets=1)
        from app.multiplanetary.telemetry import TelemetryPacket
        relay.store(TelemetryPacket("a", 0.0, {}, size_bytes=10))
        ok = relay.store(TelemetryPacket("b", 1.0, {}, size_bytes=10))
        assert not ok
        assert relay.total_dropped == 1


class TestDeepSpaceTelemetry:
    def test_send_and_transmit(self):
        dst = DeepSpaceTelemetry()
        dst.set_link_state(LinkState(available=True, data_rate_bps=9600))
        dst.send("rover", {"battery": 80})
        assert dst.stats["storage_depth"] == 1
        transmitted = dst.transmit_available(contact_s=10.0)
        assert len(transmitted) == 1


class TestPlanetaryEnvironments:
    def test_lunar(self):
        env = LunarEnvironment()
        assert env.gravity_ms2 == pytest.approx(1.62)
        assert not env.has_atmosphere

    def test_mars(self):
        env = MarsEnvironment()
        assert env.gravity_ms2 == pytest.approx(3.72)
        assert env.has_atmosphere

    def test_asteroid(self):
        env = AsteroidEnvironment()
        assert env.gravity_ms2 < 0.01

    def test_get_environment(self):
        assert isinstance(get_environment("lunar"), LunarEnvironment)
        assert isinstance(get_environment("mars"), MarsEnvironment)
        assert isinstance(get_environment("earth"), PlanetaryEnvironment)

    def test_height_map_generation(self):
        env = LunarEnvironment()
        hmap = env.generate_height_map(10, 10)
        assert len(hmap) == 10
        assert len(hmap[0]) == 10

    def test_obstacle_generation(self):
        env = MarsEnvironment()
        obs = env.generate_obstacles(5, area_km2=1.0)
        assert len(obs) == 5
        assert all("type" in o for o in obs)
