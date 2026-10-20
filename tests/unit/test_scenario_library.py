from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from holo_desert.dashboard.server import DashboardServer
from holo_desert.scenarios.config import ScenarioManager
from holo_desert.scenarios.library import ScenarioLibrary, ScenarioConflict


def configuration(name="Tre droni"):
    config = ScenarioManager().load("e01_chat").model_dump()
    config["name"] = name
    config["nodes"].append({"id": "auv_03", "position": [60, 0, -20], "yaw": 0, "waypoints": []})
    config["flows"][0].update(destination="auv_03", reply=False)
    config["network"]["routes"] = {"auv_01": {"auv_03": "auv_02"}}
    return config


def test_library_roundtrip_conflicts_atomic_write_and_restart(tmp_path, monkeypatch):
    library = ScenarioLibrary(tmp_path)
    record = library.save(configuration())
    assert len(ScenarioLibrary(tmp_path).get(record["id"])["configuration"]["nodes"]) == 3
    with pytest.raises(ScenarioConflict, match="nome"):
        library.save(configuration("  TRE DRONI  "))
    updated = configuration("Tre droni modificati")
    with pytest.raises(ScenarioConflict, match="cambiato"):
        library.save(updated, record["id"], "obsolete")
    from holo_desert.scenarios import library as module
    original = module.os.replace
    monkeypatch.setattr(module.os, "replace", lambda *args: (_ for _ in ()).throw(OSError("disk error")))
    with pytest.raises(OSError):
        library.save(updated, record["id"], record["revision"])
    assert library.get(record["id"]) == record
    assert not list(tmp_path.glob("*.tmp"))
    monkeypatch.setattr(module.os, "replace", original)
    new = library.save(updated, record["id"], record["revision"])
    assert new["revision"] != record["revision"]
    with pytest.raises(ScenarioConflict):
        library.delete(new["id"], record["revision"])
    library.delete(new["id"], new["revision"])
    assert library.list() == []


@pytest.mark.parametrize("identifier", ["../scenario", "..", "C:\\temp\\file", "user_../../config", "user_file:ads", "e03_mobility", "CON"])
def test_library_rejects_paths_and_example_identifiers(tmp_path, identifier):
    library = ScenarioLibrary(tmp_path)
    with pytest.raises(ValueError):
        library.get(identifier)
    with pytest.raises(ValueError):
        library.delete(identifier, "revision")
    assert list(tmp_path.glob("*.yaml")) == []


def test_two_manager_instances_cannot_create_duplicate_names(tmp_path):
    def save(_):
        try:
            ScenarioLibrary(tmp_path).save(configuration("Stesso nome"))
            return "saved"
        except ScenarioConflict:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(save, range(2)))
    assert sorted(results) == ["conflict", "saved"]
    assert len(ScenarioLibrary(tmp_path).list()) == 1


def test_personal_scenario_api_preserves_examples_and_cli_yaml(tmp_path):
    server = DashboardServer(manage_docker=False, scenario_directory=tmp_path)
    examples = {name: server.manager.load(name).model_dump() for name in server.manager.list()}
    with TestClient(server.application()) as client:
        assert client.get("/api/user-scenarios").json() == []
        record = client.post("/api/user-scenarios", json={"configuration": configuration()}).json()
        identifier = record["id"]
        assert client.get(f"/api/scenarios/{identifier}").json()["network"]["routes"]["auv_01"]["auv_03"] == "auv_02"
        exported = client.get(f"/api/scenarios/{identifier}/yaml")
        assert exported.status_code == 200
        imported = client.post("/api/user-scenarios/import", json={"yaml": exported.text})
        assert imported.json() == record["configuration"]
        config = imported.json()
        config["name"] = "Scenario ricaricato"
        response = client.put(f"/api/user-scenarios/{identifier}", json={"configuration": config, "revision": record["revision"]})
        assert response.status_code == 200
        assert client.put(f"/api/user-scenarios/{identifier}", json={"configuration": config, "revision": record["revision"]}).status_code == 409
        invalid = configuration("Non valido")
        invalid["network"]["routes"]["auv_01"]["auv_03"] = "auv_99"
        assert client.post("/api/user-scenarios", json={"configuration": invalid}).status_code == 422
        assert client.post("/api/user-scenarios/import", json={"yaml": "!!python/object:os.system {}"}).status_code == 422
        assert client.put("/api/user-scenarios/e03_mobility", json={"configuration": config}).status_code == 422
        assert client.delete("/api/user-scenarios/e03_mobility?revision=abc").status_code == 422
        assert all(server.manager.load(name).model_dump() == data for name, data in examples.items())
        cli_file = tmp_path / "cli-scenario.yaml"
        cli_file.write_text(exported.text, encoding="utf-8")
        assert server.manager.load(str(cli_file)).nodes[2].id == "auv_03"
    with TestClient(DashboardServer(scenario_directory=tmp_path).application()) as restarted:
        assert restarted.get(f"/api/scenarios/{identifier}").json()["name"] == "Scenario ricaricato"
        assert len(restarted.get("/api/user-scenarios").json()) == 1


def test_duplicate_e03_keeps_waypoints_and_original(tmp_path):
    manager = ScenarioManager(user_root=tmp_path)
    original = manager.load("e03_mobility").model_dump()
    copy = {**original, "name": "La mia mobilità"}
    record = manager.save_user(copy)
    assert manager.load(record["id"]).nodes[0].waypoints == manager.load("e03_mobility").nodes[0].waypoints
    assert manager.load("e03_mobility").model_dump() == original
