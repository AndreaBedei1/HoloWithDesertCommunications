"""Mixed acoustic/optical multi-PHY driven by HoloOcean vehicle motion."""
import io
import json
import zipfile

import pytest

from holo_desert import ManagedSimulation, Scenario, load_scenario

pytestmark = [pytest.mark.desert, pytest.mark.holoocean]


def first_tx(packet, node):
    return next(e for e in packet['events'] if e['event'] == 'phy_tx_start' and e.get('node_id') == node)


def test_received_power_master_uses_optical_near_and_acoustic_once_holoocean_separates_the_drones(engine):
    data = load_scenario('e01_chat').model_dump()
    data.update(duration=120, realtime=False)
    # Both drones stay inside the 0-20 m depth band of the optical noise table. auv_02 holds 8 m
    # from the master, then HoloOcean's controller drives it outwards past the optical range.
    data['nodes'][0]['position'] = [0, 0, -10]
    data['nodes'][1]['position'] = [8, 0, -10]
    data['nodes'][1]['waypoints'] = [[30, 8, 0, -10], [110, 90, 0, -10]]
    # Above 1e13 (acoustic linear power, about 14 m) the master moves to optical; below 3e-8 W
    # (about 28 m, before the optical receiver stops synchronising near 38 m) it returns to acoustic.
    data['network']['multiphy'] = {
        'interfaces': [{'id': 'acoustic', 'acoustic': {'frequency_hz': 25000, 'bandwidth_hz': 5000, 'bitrate_bps': 4800, 'tx_power_db': 150}},
                       {'id': 'optical', 'medium': 'optical', 'optical': {'bitrate_bps': 1000000}}],
        'initial_interface': 'acoustic', 'policy': 'received_power', 'master': 'auv_01',
        'thresholds': [{'from_interface': 'acoustic', 'to_interface': 'optical', 'power_linear': 1e13},
                       {'from_interface': 'optical', 'to_interface': 'acoustic', 'power_linear': 3e-8}]}
    # The slave speaks first in every 4 s cycle, so the master always has a fresh power sample.
    data['flows'] = [{'source': 'auv_02', 'destination': 'auv_01', 'start': 1, 'interval': 4, 'stop': 119, 'ttl': 8},
                     {'source': 'auv_01', 'destination': 'auv_02', 'start': 3, 'interval': 4, 'stop': 119, 'ttl': 8}]
    with ManagedSimulation(Scenario.model_validate(data), realtime=False, manage_engine=False) as sim:
        summary = sim.run()
        state = sim.snapshot()
        master = {round(p['creation_time']): first_tx(p, 'auv_01') for p in state['packets']
                  if p['source'] == 'auv_01' and p['status'] == 'received'}
        near = {tx['interface_index'] for t, tx in master.items() if t < 28}
        far = {tx['interface_index'] for t, tx in master.items() if t > 90}
        assert near == {2} and far == {1}, {t: tx['interface_index'] for t, tx in master.items()}
        assert all(tx['medium'] == 'optical' for t, tx in master.items() if tx['interface_index'] == 2)
        assert summary['received'] >= 0.85 * summary['generated'], summary
        fleet = state['fleet']['auv_02']
        assert fleet['x'] > 40 and -20 <= fleet['z'] < 0      # separation produced by HoloOcean physics
        events = [json.loads(line) for line in zipfile.ZipFile(io.BytesIO(sim.export_bytes())).read('events.jsonl').splitlines()]
        assert {e['interface_index'] for e in events if e['event'] == 'interface_state' and e['node_id'] == 'auv_01'} == {1, 2}
        assert any(e['event'] == 'phy_rx_end' and e.get('medium') == 'optical' and e.get('outcome') == 'decoded' for e in events)
