import time
import pytest
from fastapi.testclient import TestClient
from holo_desert import ManagedSimulation, ScenarioManager
from holo_desert.dashboard.server import DashboardServer

pytestmark = [pytest.mark.desert, pytest.mark.holoocean]


def test_two_real_holoocean_drones_desert_and_dashboard(engine):
    scenario = ScenarioManager().load("e01_chat")
    scenario.realtime = False
    run = ManagedSimulation(scenario, manage_engine=False)
    try:
        run.run()
        assert run.error is None, run.error
        snapshot = run.snapshot()
        assert run.state == "finished"
        received = [p for p in snapshot["packets"] if p["status"] == "received"]
        assert {p["type"] for p in received} == {"request", "reply"}
        assert all(p["receive_time"] >= p["creation_time"] for p in received)
        assert all(any(e["event"] == "rx" for e in p["events"]) for p in received)
        assert set(snapshot["fleet"]) == {"auv_01", "auv_02"}
        # Verify the same actual events reach dashboard's HTTP API.
        server = DashboardServer(initial_run=run, manage_docker=False)
        with TestClient(server.application()) as client:
            data = client.get("/api/state").json()
            assert data["counts"]["received"] >= 2 and data["scenario_id"] == "e01_chat"
            assert client.get("/api/export").content[:2] == b"PK"
    finally:
        run.close()
