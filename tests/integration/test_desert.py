import pytest
from holo_desert.common.models import Message, Pose
from holo_desert.desert_adapter.backend import DESERTAdapter, BackendError
from holo_desert.scenarios.config import ScenarioManager

pytestmark = pytest.mark.desert


def exchange(scenario, payload=b"\x00hello\xff\n", distance=30, reverse=False):
    backend = DESERTAdapter(manage_docker=False)
    try:
        backend.start(scenario)
        for node, id in scenario.node_map.items():
            backend.update_node_position(node, Pose(distance * (id - 1), 0, -20), 0)
        message = Message("auv_01", "auv_02", payload, 0)
        backend.send(message)
        if reverse:
            backend.send(Message("auv_02", "auv_01", b"reverse", 0))
        events = backend.advance(10)
        received = [e for e in events if e["event"] == "rx" and Message.decode(bytes.fromhex(e["wire_hex"])).id == message.id]
        return received, events
    finally:
        backend.stop()


@pytest.mark.parametrize("mac", ["csma_aloha", "aloha"])
def test_real_binary_payload_both_mac_profiles(engine, mac):
    scenario = ScenarioManager().load("e01_chat")
    scenario.network.mac.protocol = mac
    received, events = exchange(scenario)
    assert len(received) == 1
    assert Message.decode(bytes.fromhex(received[0]["wire_hex"])).payload == b"\x00hello\xff\n"
    assert received[0]["node"] == 2
    assert received[0]["time"] > 30 / 1600  # conservative lower bound, no Python propagation
    assert {e["node"] for e in events if e["event"] == "position_applied"} == {1, 2}


def test_distance_and_bitrate_change_real_delay(engine):
    scenario = ScenarioManager().load("e01_chat")
    short, _ = exchange(scenario, distance=30)
    far, _ = exchange(scenario, distance=500)
    assert short and far
    assert far[0]["time"] > short[0]["time"] + .2
    scenario.network.acoustic.bitrate_bps = 1200
    slow, _ = exchange(scenario, distance=30)
    assert slow[0]["time"] > short[0]["time"] + .5


def test_multiple_nodes_and_restart(engine):
    scenario = ScenarioManager().load("e02_multi_node")
    for _ in range(2):
        backend = DESERTAdapter(manage_docker=False)
        try:
            backend.start(scenario)
            for node, id in scenario.node_map.items():
                backend.update_node_position(node, Pose(id * 20, 0, -20), 0)
            for i, (src, dst) in enumerate((("auv_01", "auv_02"), ("auv_03", "auv_04"))):
                backend.send(Message(src, dst, b"real concurrent", 0))
            events = backend.advance(10)
            assert len([e for e in events if e["event"] == "app_tx"]) == 2
            assert all(e["time"] >= 0 for e in events)
            assert any(e["event"] == "rx" for e in events)
        finally:
            backend.stop()


def test_position_updates_and_power_outage_recovery(engine):
    scenario = ScenarioManager().load("e01_chat")
    backend = DESERTAdapter(manage_docker=False)
    try:
        backend.start(scenario)
        backend.update_node_position("auv_01", Pose(0, 0, -20), 0)
        backend.update_node_position("auv_02", Pose(30, 0, -20), 0)
        backend.set_power("auv_01", 0)
        lost = Message("auv_01", "auv_02", b"outage", 0)
        backend.send(lost)
        assert not [e for e in backend.advance(5) if e["event"] == "rx"]
        backend.update_node_position("auv_02", Pose(60, 0, -20), 5)
        backend.set_power("auv_01", 135)
        recovered = Message("auv_01", "auv_02", b"recovered", 5)
        backend.send(recovered)
        events = backend.advance(10)
        assert any(e["event"] == "position_applied" and e["x"] == 60 for e in events)
        assert any(e["event"] == "rx" and Message.decode(bytes.fromhex(e["wire_hex"])).id == recovered.id for e in events)
    finally:
        backend.stop()


def test_geometry_changes_delay_without_restarting_engine(engine):
    scenario = ScenarioManager().load("e01_chat")
    backend = DESERTAdapter(manage_docker=False)
    try:
        backend.start(scenario)
        delays = []
        for start, distance in ((0, 30), (5, 500), (10, 30)):
            backend.update_node_position("auv_01", Pose(0, 0, -20), start)
            backend.update_node_position("auv_02", Pose(distance, 0, -20), start)
            message = Message("auv_01", "auv_02", b"geometry", start)
            backend.send(message)
            events = backend.advance(start + 5)
            rx = [e for e in events if e["event"] == "rx"]
            assert len(rx) == 1
            assert rx[0]["time"] <= start + 5
            # MAC listen/backoff changes between packets in the same RNG stream.
            # Isolate observed propagation using PHY timestamps, not app latency.
            tx = next(e for e in events if e["event"] == "phy_tx_start" and e["node"] == 1)
            arrival = next(e for e in events if e["event"] == "phy_rx_start" and e["node"] == 2)
            delays.append(arrival["time"] - tx["time"])
        assert delays[1] > delays[0] + .2
        assert abs(delays[2] - delays[0]) < 1e-5
    finally:
        backend.stop()


def test_engine_death_is_reported_and_new_session_recovers(engine):
    from holo_desert.desert_adapter.backend import docker_command, COMPOSE
    scenario = ScenarioManager().load("e01_chat")
    backend = DESERTAdapter(manage_docker=False)
    try:
        backend.start(scenario)
        import os
        target=os.environ.get('DESERT_TEST_CONTAINER')
        command=["exec",target] if target else [*COMPOSE,"exec","-T","desert"]
        docker_command(*command, "pkill", "-9", "-x", "ns", timeout=10)
        with pytest.raises(BackendError):
            backend.advance(1)
    finally:
        backend.stop()
    received, _ = exchange(scenario)
    assert received


def test_barrier_prevents_wall_clock_advancement(engine):
    import time
    scenario = ScenarioManager().load("e01_chat")
    backend = DESERTAdapter(manage_docker=False)
    try:
        backend.start(scenario)
        backend.update_node_position("auv_01", Pose(0, 0, -20), 0)
        backend.update_node_position("auv_02", Pose(30, 0, -20), 0)
        message = Message("auv_01", "auv_02", b"barrier", 0)
        backend.send(message)
        time.sleep(.15)
        assert backend.time == 0
        assert not [e for e in backend.advance(.001) if e["event"] == "rx"]
        assert any(e["event"] == "rx" for e in backend.advance(5))
    finally:
        backend.stop()


def test_multihop_requires_relay_under_validated_channel(engine):
    scenario = ScenarioManager().load("e05_multihop")
    backend = DESERTAdapter(manage_docker=False)
    try:
        backend.start(scenario)
        for node in scenario.nodes:
            backend.update_node_position(node.id, Pose(*node.position), 0)
        message = Message("auv_01", "auv_03", b"relay proof", 0)
        backend.send(message)
        events = backend.advance(10)
        assert any(e["event"] == "forward" and e["node"] == 2 for e in events)
        assert any(e["event"] == "rx" and e["node"] == 3 for e in events)
    finally:
        backend.stop()
    direct = ScenarioManager().load("e01_chat")
    direct.network.acoustic.tx_power_db = scenario.network.acoustic.tx_power_db
    received, events = exchange(direct, payload=b"direct control", distance=1000)
    assert not received
    assert any(e["event"] == "phy_rx_end" and e["outcome"] in ("noise_error", "not_synchronized") for e in events)


@pytest.mark.parametrize("protocol", ["aloha", "csma_aloha"])
def test_ack_mode_and_real_mac_header_identity(engine, protocol):
    scenario = ScenarioManager().load("e01_chat")
    scenario.network.mac.protocol = protocol
    scenario.network.mac.ack = True
    backend = DESERTAdapter(manage_docker=False)
    try:
        backend.start(scenario)
        addresses = {e["node"]: e["mac_address"] for e in backend.initial_events if e["event"] == "node_info"}
        assert len(addresses) == 2 and len(set(addresses.values())) == 2
        for node in scenario.nodes:
            backend.update_node_position(node.id, Pose(*node.position), 0)
        backend.send(Message("auv_01", "auv_02", b"ACK enabled", 0))
        events = backend.advance(10)
        assert any(e["event"] == "rx" and e["node"] == 2 for e in events)
        tx = next(e for e in events if e["event"] == "phy_tx_start")
        assert tx["transmitter_mac"] == addresses[1] and tx["next_hop_mac"] == addresses[2]
    finally:
        backend.stop()
