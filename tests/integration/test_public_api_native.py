"""Public API against the real DESERT engine, without HoloOcean or dashboard."""
import io
import json
import math
import zipfile

import pytest

from holo_desert import ManagedSimulation, NetworkSession, SessionError, load_scenario

pytestmark = pytest.mark.desert


def open_session(name="e01_chat"):
    return NetworkSession(load_scenario(name), manage_engine=False)


def test_standalone_binary_and_json_roundtrip(engine):
    received = []
    with open_session() as net:
        a, b = net.node("auv_01"), net.node("auv_02")
        b.on_receive(received.append)
        a.send("auv_02", bytes(range(16)))
        a.send_json("auv_02", {"cmd": "hold", "depth": -20})
        net.run_until(15)
        payloads = sorted((d.message.message_type, d.message.payload) for d in received)
        assert ("binary", bytes(range(16))) in payloads
        assert any(kind == "json" for kind, _ in payloads)
        pa, pb = a.pose, b.pose
        distance = math.dist((pa.x, pa.y, pa.z), (pb.x, pb.y, pb.z))
        # End-to-end latency includes propagation (distance / sound speed) and MAC/PHY time.
        assert all(d.network_time - d.message.creation_time > distance / 1500 for d in received)
        summary = net.summary()
        assert summary["received"] == len(received) and summary["mac_stats"]
        assert net.engine_info["engine_fingerprint"]


def test_moved_node_is_out_of_range_then_returns(engine):
    with open_session() as net:
        a, b = net.node("auv_01"), net.node("auv_02")
        b.update_pose((5000, 0, -20))
        a.send("auv_02", b"far")
        net.run_until(12)
        assert b.receive() == []
        b.update_pose((30, 0, -20))
        net.step()
        a.send("auv_02", b"near")
        net.run_until(24)
        assert [d.message.payload for d in b.receive()] == [b"near"]


def test_multihop_relay_is_decided_by_desert(engine):
    with open_session("e05_multihop") as net:
        net.node("auv_01").send("auv_03", b"relay me", ttl=16)
        events = net.run_until(16)
        assert [d.message.payload for d in net.node("auv_03").receive()] == [b"relay me"]
        relay = net.scenario.node_map["auv_02"]
        assert any(e["event"] == "phy_tx_start" and e["node"] == relay for e in events)


def test_sequential_sessions_and_clean_restart(engine):
    net = open_session()
    for _ in range(2):
        net.start() if net.state != "running" else net.restart()
        net.node("auv_01").send("auv_02", b"x")
        net.run_until(5)
        assert len(net.node("auv_02").receive()) == 1
    net.close()
    with pytest.raises(SessionError):
        net.step()


def test_managed_simulation_without_holoocean(engine, tmp_path):
    with ManagedSimulation("e01_chat", holoocean=False, realtime=False, manage_engine=False) as sim:
        sim.annotate("run_selection", scenario_id="e01_chat")
        summary = sim.run()
        assert sim.state == "finished" and sim.holoocean is False and sim.run_id
        assert summary["generated"] >= 2 and summary["received"] >= 2
        assert sim.export(tmp_path / "e01.zip").stat().st_size > 0
        assert sim.versions["engine"]["engine_fingerprint"] == sim.snapshot()["engine_info"]["engine_fingerprint"]
        assert set(sim.trajectory_fingerprint()["nodes"]) == {"auv_01", "auv_02"}
        archive = zipfile.ZipFile(io.BytesIO(sim.export_bytes()))
        assert {"config.json", "events.jsonl", "packets.csv", "summary.json"} <= set(archive.namelist())
        events = [json.loads(line) for line in archive.read("events.jsonl").splitlines()]
        assert any(e["event"] == "run_selection" and e["scenario_id"] == "e01_chat" for e in events)
    sim.close()  # a second close after the context manager is harmless
