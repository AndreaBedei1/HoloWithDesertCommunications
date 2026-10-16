import math
import pytest
from pydantic import ValidationError
from holo_desert.common.models import Message, Pose
from holo_desert.common.coordinates import CoordinateConverter
from holo_desert.scenarios.config import ScenarioManager, Scenario, Network


def test_binary_message_roundtrip():
    message = Message("auv_01", "auv_02", b"\x00\xff\n{}", 1.25)
    assert Message.decode(message.encode()) == message
    assert message.id != Message("auv_01", "auv_02", b"", 1.25).id


@pytest.mark.parametrize("change", [{"version": 2}, {"ttl": -1}, {"creation_time": float("nan")}])
def test_invalid_message(change):
    data = dict(source="auv_01", destination="auv_02", payload=b"", creation_time=0)
    data.update(change)
    with pytest.raises(ValueError):
        Message(**data)


def test_coordinate_contract():
    pose = Pose(20, -30, -10, 45)
    assert CoordinateConverter().to_network(pose) == pose
    assert CoordinateConverter((10, 0, 2)).to_network(pose) == Pose(10, -30, -12, 45)
    with pytest.raises(ValueError):
        Pose(math.inf, 0, 0)


def test_all_scenarios_validate():
    manager = ScenarioManager()
    assert len(manager.list()) == 6
    for name in manager.list():
        scenario = manager.load(name)
        assert list(scenario.node_map.values()) == list(range(1, len(scenario.nodes) + 1))


@pytest.mark.parametrize("network", [{"mac": {"protocol": "fake"}}, {"acoustic": {"sound_speed_m_s": 1400}}, {"woss": True}])
def test_unknown_protocol_or_parameter_rejected(network):
    with pytest.raises(ValidationError):
        Network.model_validate(network)


def test_duplicate_nodes_and_bad_route_rejected():
    data = ScenarioManager().load("e01_chat").model_dump()
    data["nodes"][1]["id"] = data["nodes"][0]["id"]
    with pytest.raises(ValidationError):
        Scenario.model_validate(data)
    data = ScenarioManager().load("e01_chat").model_dump()
    data["network"]["routes"] = {"auv_01": {"auv_02": "auv_99"}}
    with pytest.raises(ValidationError):
        Scenario.model_validate(data)
