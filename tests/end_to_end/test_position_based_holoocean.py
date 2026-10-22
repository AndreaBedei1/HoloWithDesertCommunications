"""Native Position-Based Routing while HoloOcean moves the vehicle between static anchors."""
import pytest

from holo_desert import ManagedSimulation, Scenario, load_scenario

pytestmark = [pytest.mark.desert, pytest.mark.holoocean]


def first_hop(packet):
    return next(e['next_hop_id'] for e in packet['events'] if e['event'] == 'forward' and e.get('node_id') == packet['source'])


def test_routes_follow_the_vehicle_from_its_own_fixes_and_header_estimates(engine):
    data = load_scenario('e01_chat').model_dump()
    data.update(duration=130, realtime=False)
    # Anchors auv_01 and auv_02 hold station 60 m apart; auv_03 starts next to auv_01 and HoloOcean's
    # controller drives it past auv_02. Routing gates: 70 m for anchors and for the vehicle.
    data['nodes'] = [{'id': 'auv_01', 'position': [0, 0, -20]}, {'id': 'auv_02', 'position': [60, 0, -20]},
                     {'id': 'auv_03', 'position': [10, 10, -20], 'waypoints': [[20, 10, 10, -20], [120, 130, 10, -20]]}]
    data['network']['routing'] = 'position_based'
    data['network']['position_based'] = {'anchor_range_m': 70, 'vehicle_range_m': 70, 'anchors': {'auv_01': {}, 'auv_02': {}}}
    data['network']['routes'] = {'auv_01': {'auv_03': 'auv_02'}}
    data['flows'] = [{'source': 'auv_03', 'destination': 'auv_01', 'start': 1, 'interval': 4, 'stop': 129, 'ttl': 8},
                     {'source': 'auv_01', 'destination': 'auv_03', 'start': 3, 'interval': 4, 'stop': 129, 'ttl': 8}]
    with ManagedSimulation(Scenario.model_validate(data), realtime=False, manage_engine=False) as sim:
        summary = sim.run()
        state = sim.snapshot()
        received = [p for p in state['packets'] if p['status'] == 'received']
        uplink = {round(p['creation_time']): first_hop(p) for p in received if p['source'] == 'auv_03'}
        downlink = {round(p['creation_time']): first_hop(p) for p in received if p['source'] == 'auv_01'}
        # Near auv_01 both directions are direct; once the vehicle is far from it, both go through auv_02.
        assert {hop for t, hop in uplink.items() if t < 20} == {'auv_01'}, uplink
        assert {hop for t, hop in downlink.items() if t < 20} == {'auv_03'}, downlink
        assert {hop for t, hop in uplink.items() if t > 110} == {'auv_02'}, uplink
        assert {hop for t, hop in downlink.items() if t > 110} == {'auv_02'}, downlink
        assert summary['received'] >= 0.85 * summary['generated'], summary
        assert state['fleet']['auv_03']['x'] > 75        # separation produced by HoloOcean physics
