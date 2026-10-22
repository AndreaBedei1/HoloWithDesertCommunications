import io
import zipfile

import pytest
from fastapi.testclient import TestClient
from holo_desert.common.models import Message, Delivery
from holo_desert.telemetry.collector import TelemetryCollector
from holo_desert.scenarios.config import ScenarioManager
from holo_desert.dashboard.server import DashboardServer


def test_metrics_pending_not_lost_export_and_cleanup():
    scenario = ScenarioManager().load("e01_chat")
    collector = TelemetryCollector(scenario.model_dump())
    directory = collector.directory
    try:
        first = Message("auv_01", "auv_02", b"1234", 0, ttl=2)
        second = Message("auv_01", "auv_02", b"12", 0, ttl=10)
        collector.generated(first)
        collector.generated(second)
        collector.sample(1)
        assert collector.snapshot()["series"][-1]["pdr_resolved"] is None
        assert collector.snapshot()["counts"]["pending"] == 2
        collector.received(Delivery(first, "auv_02", 1, 2000, {}))
        collector.sample(3)
        assert collector.snapshot()["counts"] == dict(generated=2, received=1, timed_out=0, pending=1)
        collector.sample(11)
        assert collector.snapshot()["series"][-1]["pdr_resolved"] == .5
        with zipfile.ZipFile(io.BytesIO(collector.export())) as archive:
            assert set(archive.namelist()) == {"events.jsonl", "config.json", "packets.csv"}
    finally:
        collector.close()
    assert not directory.exists()


def test_dashboard_routes_and_invalid_config():
    with TestClient(DashboardServer(manage_docker=False).application()) as client:
        assert client.get("/").status_code == 200
        assert len(client.get("/api/scenarios").json()) == 6
        assert client.get("/api/state").json()["state"] == "idle"
        assert client.post("/api/pause").status_code == 409
        assert client.get("/api/export").status_code == 409
        assert client.post("/api/start", json={"configuration": {"name": "invalid"}}).status_code == 422


def test_correlated_engine_event_retains_type_and_timestamp():
    collector = TelemetryCollector(ScenarioManager().load("e01_chat").model_dump())
    try:
        message = Message("auv_01", "auv_02", b"correlate", 0)
        collector.generated(message)
        collector.engine_event({"event": "rx", "time": 1, "node": 2,
                                "wire_hex": message.encode().hex()}, {2: "auv_02"})
        packet = collector.snapshot()["packets"][0]
        assert packet["events"][0]["event"] == "rx"
        assert packet["events"][0]["time"] == 1
    finally:
        collector.close()


def test_ranging_estimates_are_kept_beside_the_geometric_reference():
    from holo_desert.common.models import Pose
    collector = TelemetryCollector(ScenarioManager().load("e01_chat").model_dump())
    inverse = {1: "auv_01", 2: "auv_02"}
    try:
        collector.positions({"auv_01": Pose(0, 0, -20), "auv_02": Pose(30, 40, -20)}, 1)
        for observer, travel, distance in ((1, 0.0333, 49.95), (2, None, None)):
            collector.engine_event({"event": "ranging_estimate", "time": 1, "node": observer, "peer_a": 1, "peer_b": 2,
                                    "travel_time_s": travel, "distance_m": distance, "valid": travel is not None,
                                    "measurement_time": None, "protocol": "ranging_tokenbus"}, inverse)
        ranging = collector.snapshot()["ranging"]
        point = ranging["series"]["auv_01>auv_02"][0]
        assert point["time"] == 1 and point["geometric_distance_m"] == 50
        assert point["estimates"] == {"auv_01": 49.95}
        latest = {row["observer"]: row for row in ranging["latest"]}
        assert latest["auv_01"]["error_m"] == pytest.approx(-0.05) and latest["auv_01"]["protocol"] == "ranging_tokenbus"
        assert latest["auv_02"]["valid"] is False and latest["auv_02"]["error_m"] is None
    finally:
        collector.close()


def test_native_bindings_are_kept_per_node_and_shared():
    collector = TelemetryCollector(ScenarioManager().load("e01_chat").model_dump())
    try:
        collector.engine_event({"event": "native_bindings", "time": 0, "module": "channel", "class": "Module/UnderwaterChannel",
                                "values": {"propSpeed_": 1500}}, {1: "auv_01", 2: "auv_02"})
        collector.engine_event({"event": "native_bindings", "time": 0, "node": 2, "module": "phy", "interface_index": 2,
                                "class": "Module/MPhy/BPSK/Underwater/HOLO", "values": {"MaxTxSPL_dB_": 145}}, {1: "auv_01", 2: "auv_02"})
        applied = collector.snapshot()["applied_configuration"]
        assert applied["shared"] == [{"module": "channel", "class": "Module/UnderwaterChannel", "values": {"propSpeed_": 1500}}]
        assert applied["auv_02"] == [{"module": "phy", "class": "Module/MPhy/BPSK/Underwater/HOLO", "interface_index": 2,
                                      "values": {"MaxTxSPL_dB_": 145}}]
    finally:
        collector.close()
