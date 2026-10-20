import pytest

from holo_desert.common.models import Message, Pose
from holo_desert.desert_adapter.backend import DESERTAdapter
from holo_desert.scenarios.config import ScenarioManager


pytestmark = pytest.mark.desert


def test_corrected_isolated_packet_tests_noise_once(engine):
    scenario = ScenarioManager().load("e01_chat")
    scenario.network.acoustic.phy = "bpsk_corrected"
    scenario.network.acoustic.tx_power_db = 105
    backend = DESERTAdapter(manage_docker=False)
    try:
        backend.start(scenario)
        backend.update_node_position("auv_01", Pose(0, 0, -20), 0)
        backend.update_node_position("auv_02", Pose(40, 0, -20), 0)
        outcomes = []
        for i in range(24):
            backend.send(Message("auv_01", "auv_02", b"x"*16, i*2))
            events = backend.advance(i*2+2)
            rx = [e for e in events if e["event"] == "phy_rx_end" and e["node"] == 2]
            assert len(rx) == 1
            frame = rx[0]
            assert frame["phy_patch_id"] == "conditional-bpsk-v1"
            assert frame["conditional_interference_per"] == 0
            assert frame["pi"] == pytest.approx(0, abs=1e-5)
            assert frame["phy_bits"] > 16*8
            assert frame["pr"] > 0 and frame["pn"] > 0 and frame["pt"] > frame["pr"]
            assert frame["snr_db"] == pytest.approx(17.4230, abs=.001)
            assert frame["phy_rx_time"] > frame["phy_tx_time"]
            outcomes.append(frame["outcome"])
        assert set(outcomes) == {"decoded", "noise_error"}
    finally:
        backend.stop()


def test_corrected_simultaneous_frames_have_real_interference(engine):
    scenario = ScenarioManager().load("e02_multi_node")
    scenario.network.acoustic.phy = "bpsk_corrected"
    scenario.network.acoustic.tx_power_db = 135
    scenario.network.mac.protocol = "aloha"
    backend = DESERTAdapter(manage_docker=False)
    try:
        backend.start(scenario)
        for index, node in enumerate(scenario.nodes):
            backend.update_node_position(node.id, Pose(40*index, 0, -20), 0)
        backend.send(Message("auv_01", "auv_02", b"a"*1000, 0))
        backend.send(Message("auv_03", "auv_02", b"b"*1000, 0))
        events = backend.advance(15)
        failures = [e for e in events if e["event"] == "phy_rx_end"
                    and e["node"] == 2 and e["outcome"] == "interference_error"]
        assert failures
        assert all(e["pi"] > 0 and e["positive_interference"]
                   and e["conditional_interference_per"] > .99 for e in failures)
        assert any(e["event"] == "phy_rx_start" and e["node"] == 2
                   and e["outcome"] == "receiver_busy_overlap" for e in events)
    finally:
        backend.stop()


def test_control_frames_have_native_identity_without_fake_envelope(engine):
    scenario = ScenarioManager().load("e01_chat")
    scenario.network.acoustic.phy = "bpsk_corrected"
    scenario.network.mac.ack = True
    backend = DESERTAdapter(manage_docker=False)
    try:
        backend.start(scenario)
        for node in scenario.nodes:
            backend.update_node_position(node.id, Pose(*node.position), 0)
        backend.send(Message("auv_01", "auv_02", b"ACK proof", 0))
        events = backend.advance(10)
        control = [e for e in events if e["event"].startswith("phy_control_")]
        assert control
        assert all("wire_hex" not in e and e["phy_bits"] > 0 and "ns_uid" in e for e in control)
        assert any(e["event"] == "rx" for e in events)
    finally:
        backend.stop()
