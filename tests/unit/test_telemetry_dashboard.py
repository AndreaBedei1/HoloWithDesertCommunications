import io
import zipfile
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
