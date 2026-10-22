"""Position-based routing: roles, surveyed positions and tables reach the bridge; nothing else does."""
import pytest

from holo_desert.resources.docker.stack_builder import render
from holo_desert.scenarios.config import Scenario, ScenarioManager


def scenario(**position_based):
    data = ScenarioManager().load('e01_chat').model_dump()
    data['nodes'] = [{'id': 'auv_01', 'position': [-500, 0, -100]}, {'id': 'auv_02', 'position': [0, 0, -100]},
                     {'id': 'auv_03', 'position': [-500, 200, -100], 'waypoints': [[10, 0, 200, -100]]}]
    data['flows'] = [{'source': 'auv_03', 'destination': 'auv_01', 'reply': False}]
    data['network']['routing'] = 'position_based'
    data['network']['position_based'] = {'anchor_range_m': 450, 'vehicle_range_m': 400,
                                         'anchors': {'auv_01': {}, 'auv_02': {'surveyed_position': [2, -1, -99]}}, **position_based}
    data['network']['routes'] = {'auv_01': {'auv_03': 'auv_02'}}
    return data


def test_render_gives_each_role_only_its_own_knowledge():
    text = render(Scenario.model_validate(scenario()).model_dump())
    assert 'set routing_adapter position_based' in text and 'libuwsmposition.so libuwposbasedrt.so' in text
    assert 'set pbr_parameters {anchor_range_m 450 vehicle_range_m 400}' in text
    assert 'set pbr_role(1) anchor' in text and 'set pbr_role(3) vehicle' in text
    # Anchors: surveyed position (default: the scenario position); vehicles: none at all.
    assert 'set pbr_survey(1) {-500 0 -100}' in text and 'set pbr_survey(2) {2 -1 -99}' in text and 'pbr_survey(3)' not in text
    # Complete anchor tables; a missing entry is direct; the vehicle has no table.
    assert 'set pbr_routes {{1 2 2 anchor} {1 3 2 vehicle} {2 1 1 anchor} {2 3 3 vehicle}}' in text


@pytest.mark.parametrize('change,match,builder', [
    (lambda d: d['network']['position_based'].update(anchors={}), 'anchor and one vehicle', 'anchor and one vehicle'),
    (lambda d: d['network']['position_based']['anchors'].update(auv_03={}), 'waypoints|anchor and one vehicle', 'static nodes|anchor and one vehicle'),
    (lambda d: d['network'].update(routes={'auv_03': {'auv_01': 'auv_02'}}), 'tables belong to anchors', 'tables belong to anchors'),
    (lambda d: d['network'].update(routes={'auv_02': {'auv_01': 'auv_03'}}), 'tables belong to anchors', 'tables belong to anchors'),
    (lambda d: d['network']['position_based'].update(anchor_range_m=0), 'greater than or equal to 0.001', 'bounds'),
    (lambda d: d['network']['mac'].update(protocol='tdma'), 'CSMA-ALOHA', 'CSMA-ALOHA'),
    (lambda d: d['network'].update(medium='optical'), 'CSMA-ALOHA|StaticRouting', 'CSMA-ALOHA')])
def test_invalid_position_based_configurations_are_rejected_by_schema_and_builder(change, match, builder):
    data = scenario()
    change(data)
    with pytest.raises(ValueError, match=match):
        Scenario.model_validate(data)
    with pytest.raises(ValueError, match=builder):
        render(data)


def test_route_display_lists_only_the_anchors_tables():
    from holo_desert.telemetry.collector import TelemetryCollector
    collector = TelemetryCollector(Scenario.model_validate(scenario()).model_dump())
    try:
        routes = collector.configured_routes()
        assert {r['source'] for r in routes} == {'auv_01', 'auv_02'}
        assert next(r for r in routes if r['source'] == 'auv_01' and r['destination'] == 'auv_03')['next_hop'] == 'auv_02'
    finally:
        collector.close()
