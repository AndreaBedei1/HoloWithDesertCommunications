import threading
import socket
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from holo_desert.common.models import Message, Pose
from holo_desert.core.applications import HeartbeatCoordinator
from holo_desert.core.orchestrator import SimulationOrchestrator
from holo_desert.dashboard.server import DashboardServer
from holo_desert.scenarios.config import Scenario, ScenarioManager
from holo_desert.telemetry.collector import TelemetryCollector


def test_routes_reject_cycles_and_accept_existing_scenarios():
    manager = ScenarioManager()
    for name in manager.list():
        Scenario.model_validate(manager.load(name).model_dump())
    config = manager.load("e05_multihop").model_dump()
    config["network"]["routes"]["auv_02"] = {"auv_03": "auv_01"}
    with pytest.raises(ValueError, match="loop"):
        Scenario.model_validate(config)
    config["network"]["routes"] = {"auv_01": {"auv_03": "auv_01"}}
    with pytest.raises(ValueError, match="own source"):
        Scenario.model_validate(config)


def test_metric_geometry_queue_and_snapshot_are_observations():
    collector = TelemetryCollector(ScenarioManager().load("e01_chat").model_dump())
    try:
        collector.positions({"auv_01": Pose(0, 0, -20), "auv_02": Pose(3, 4, -20)}, 0)
        collector.sample(.5)
        point = collector.snapshot()["series"][-1]
        assert point["distances_m"]["auv_01>auv_02"] == 5
        assert point["nodes"]["auv_01"]["mac_queue"] is None
        collector.engine_event(dict(event="stats", time=1, node=1, mac_queue=7), {1: "auv_01"})
        collector.sample(1)
        snap = collector.snapshot()
        assert snap["series"][-1]["nodes"]["auv_01"]["mac_queue"] == 7
        snap["stats"]["auv_01"]["mac_queue"] = 999
        assert collector.snapshot()["stats"]["auv_01"]["mac_queue"] == 7
        assert collector.summary()["mac_queue_peak"] == 7
    finally:
        collector.close()


def test_physical_hops_do_not_create_early_application_receptions():
    collector = TelemetryCollector(ScenarioManager().load("e05_multihop").model_dump())
    inverse = {1: "auv_01", 2: "auv_02", 3: "auv_03"}
    message = Message("auv_01", "auv_03", b"hop", 0, ttl=2)
    try:
        collector.generated(message)
        for node, mac in ((1, 0), (2, 1), (3, 2)):
            collector.engine_event(dict(event="node_info", time=0, node=node, mac_address=mac), inverse)
        collector.engine_event(dict(event="phy_tx_start", time=.1, node=1,
                                    next_hop_mac=1, transmitter_mac=0, wire_hex=message.encode().hex()), inverse)
        snap = collector.snapshot()
        assert not snap["edges"] and snap["counts"]["received"] == 0
        assert snap["observations"][-1]["next_hop_id"] == "auv_02"
        assert snap["packets"][0]["status"] == "phy_tx_observed"
        for i in range(300):
            collector.engine_event(dict(event="forward", time=1, node=2,
                                        next_hop_address=3, wire_hex=message.encode().hex()), inverse)
        collector.sample(3)
        snap = collector.snapshot()
        assert len(snap["packets"][0]["events"]) == 256
        assert snap["packets"][0]["omitted_events"] > 0
        assert len(snap["observations"]) == 300
        assert snap["packets"][0]["status"] == "timeout_unknown_cause"
        assert collector.phy_errors["interference_error"] == 0
        # A late frame may outlive its pruned inspector row: count the PHY event.
        del collector.packets[message.id]
        collector.engine_event(dict(event="phy_rx_end", time=4, node=2, outcome="noise_error",
                                    wire_hex=message.encode().hex()), inverse)
        assert collector.summary()["phy_observations"]["noise_error"] == 1
    finally:
        collector.close()


def test_heartbeat_age_uses_arrival_clock():
    app = HeartbeatCoordinator(None, "auv_01", (20, 0, -20))
    msg = Message("auv_01", "auv_02", b"clear", 0, message_type="heartbeat")
    app.update(2, Pose(0, 0, -20), [SimpleNamespace(message=msg, network_time=1.25)])
    assert app.snapshot(2)["heartbeat_age_s"] == .75
    assert app.state == "PROCEED"
    app.update(5, Pose(1, 0, -20), [])
    assert app.state == "HOLD"
    assert app.snapshot(5)["last_heartbeat_s"] == 1.25


def test_terminal_state_waits_for_cleanup_and_factory_needs_no_engine_api():
    scenario = ScenarioManager().load("e01_chat")
    scenario.duration = .1
    scenario.realtime = False
    entered, release = threading.Event(), threading.Event()

    class Backend:
        time = 0
        versions = {}
        pause_supported = True
        def start(self, scenario): pass
        def update_node_position(self, *args): pass
        def request_stats(self): pass
        def advance(self, target):
            self.time = target
            return [dict(event="position_applied", time=target, node=n) for n in (1, 2)]
        def stop(self): pass

    class Physics:
        def start(self): return {n.id: Pose(*n.position) for n in scenario.nodes}
        tick = start
        def stop(self):
            entered.set()
            assert release.wait(3)

    class Application:
        def update(self, now, own_pose, received): return None

    run = SimulationOrchestrator(scenario, backend=Backend(), physics=Physics(), standalone=True,
                                 application_factory=lambda node, comm, cfg: Application())
    try:
        run.start_background()
        assert entered.wait(3)
        assert run.state == "stopping"
        release.set()
        run.thread.join(3)
        assert run.state == "finished" and run.error is None
    finally:
        release.set()
        run.close()


def test_dashboard_validation_comparison_equivalence_and_reset():
    server = DashboardServer(manage_docker=False)

    def completed(mac, run_id):
        scenario = ScenarioManager().load("e04_congestion")
        scenario.network.mac.protocol = mac
        collector = TelemetryCollector(scenario.model_dump())
        return SimpleNamespace(state="finished", standalone=False, scenario=scenario,
                               telemetry=collector, run_id=run_id, close=collector.close)

    with TestClient(server.application()) as client:
        config = ScenarioManager().load("e05_multihop").model_dump()
        assert client.post("/api/validate", json=config).status_code == 200
        config["network"]["routes"]["auv_01"]["auv_03"] = "auv_99"
        assert client.post("/api/validate", json=config).status_code == 422
        for i, mac in enumerate(("aloha", "csma_aloha")):
            server.run = completed(mac, str(i))
            assert client.post("/api/comparison").status_code == 200
            assert client.post("/api/comparison").status_code == 200  # idempotent per run
            assert client.post("/api/reset").status_code == 200
        result = client.get("/api/comparisons").json()
        assert len(result["runs"]) == 2 and result["equivalent"]
        server.run = completed("aloha", "third")
        server.run.scenario.network.acoustic.bitrate_bps = 2400
        assert client.post("/api/comparison").status_code == 200
        result = client.get("/api/comparisons").json()
        assert len(result["runs"]) == 3 and not result["equivalent"]
        server.run.state = "stopping"
        assert client.post("/api/reset").status_code == 409
        assert client.post("/api/start", json={}).status_code == 409


def test_occupied_dashboard_port_cannot_start_simulators():
    from holo_desert.cli import serve_dashboard
    calls = []
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        with pytest.raises(OSError):
            serve_dashboard(None, occupied.getsockname()[1], lambda: calls.append("started"))
    assert calls == []


def test_comparison_records_phy_changes_versions_and_common_experiment():
    server=DashboardServer(manage_docker=False)
    collectors=[]
    try:
        with TestClient(server.application()) as client:
            for index,phy in enumerate(('bpsk_upstream','bpsk_corrected')):
                scenario=ScenarioManager().load('e01_chat')
                scenario.network.acoustic.phy=phy
                collector=TelemetryCollector(scenario.model_dump());collectors.append(collector)
                collector.emit('run_started',0,versions={'engine':{'desert_source_commit':'compiled-test'}})
                collector.positions({'auv_01':Pose(index,0,-20),'auv_02':Pose(20,0,-20)},0,origin='holoocean')
                server.run=SimpleNamespace(state='finished',standalone=False,scenario=scenario,
                                          telemetry=collector,run_id=str(index),close=lambda:None)
                assert client.post('/api/comparison').status_code==200
            result=client.get('/api/comparisons').json()
            assert result['same_experiment']
            assert result['changed_sections']==['phy']
            assert 'network.acoustic.phy' in result['changed_fields']
            assert result['runs'][0]['versions']['engine']['desert_source_commit']=='compiled-test'
            assert result['runs'][0]['observed_trajectory']!=result['runs'][1]['observed_trajectory']
    finally:
        for collector in collectors:collector.close()


def test_frontend_module_mime_does_not_depend_on_windows_registry(monkeypatch):
    import starlette.responses
    monkeypatch.setattr(starlette.responses, "guess_type", lambda path: ("text/plain", None))
    with TestClient(DashboardServer().application()) as client:
        for name in ("app", "ui", "charts", "maps", "configuration", "packets"):
            assert client.get(f"/static/{name}.js").headers["content-type"].startswith("text/javascript")
        assert client.get("/static/style.css").headers["content-type"].startswith("text/css")
