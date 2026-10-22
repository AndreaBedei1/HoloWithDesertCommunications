"""Native multi-PHY controller inside HoloOcean co-simulations."""
import io
import json
import zipfile

import pytest

from holo_desert import HoloOceanLink, ManagedSimulation, NetworkSession, Scenario, load_scenario
from holo_desert.holoocean_adapter.adapter import HoloOceanAdapter

pytestmark = [pytest.mark.desert, pytest.mark.holoocean]

INTERFACES = [{'id': 'long', 'acoustic': {'frequency_hz': 25000, 'bandwidth_hz': 5000, 'bitrate_bps': 4800, 'tx_power_db': 150}},
              {'id': 'short', 'acoustic': {'frequency_hz': 50000, 'bandwidth_hz': 9000, 'bitrate_bps': 8800, 'tx_power_db': 150}}]


def first_tx(packet, node):
    return next(e['interface_index'] for e in packet['events'] if e['event'] == 'phy_tx_start' and e.get('node_id') == node)


def test_received_power_controller_follows_holoocean_distance(engine):
    data = load_scenario('e01_chat').model_dump()
    data.update(duration=150, realtime=False)
    # auv_02 holds 30 m from the master, then HoloOcean's controller drives it outwards
    # (the hovering AUV covers about 120 m by the end, well past the 100 m switch-back range).
    data['nodes'][1]['waypoints'] = [[20, 30, 0, -20], [120, 230, 0, -20]]
    # Thresholds on the master's mean received power (linear PHY units, 10^(SPL/10)):
    # above 1e12 (about 45 m) move to "short", below 2e11 (about 100 m at 50 kHz) back to "long".
    data['network']['multiphy'] = {'interfaces': INTERFACES, 'initial_interface': 'long', 'policy': 'received_power',
                                   'master': 'auv_01',
                                   'thresholds': [{'from_interface': 'long', 'to_interface': 'short', 'power_linear': 1e12},
                                                  {'from_interface': 'short', 'to_interface': 'long', 'power_linear': 2e11}]}
    # The slave speaks first in every 4 s cycle, so the master always has a fresh power sample.
    data['flows'] = [{'source': 'auv_02', 'destination': 'auv_01', 'start': 1, 'interval': 4, 'stop': 149, 'ttl': 8},
                     {'source': 'auv_01', 'destination': 'auv_02', 'start': 3, 'interval': 4, 'stop': 149, 'ttl': 8}]
    with ManagedSimulation(Scenario.model_validate(data), realtime=False, manage_engine=False) as sim:
        summary = sim.run()
        state = sim.snapshot()
        master = {round(p['creation_time']): first_tx(p, 'auv_01') for p in state['packets']
                  if p['source'] == 'auv_01' and p['status'] == 'received'}
        near = [index for t, index in master.items() if t < 20]
        far = [index for t, index in master.items() if t > 125]
        assert near and set(near) == {2}, master
        assert far and set(far) == {1}, master
        assert summary['received'] >= 0.9 * summary['generated']
        assert state['fleet']['auv_02']['x'] > 120      # distance produced by HoloOcean physics
        events = [json.loads(line) for line in zipfile.ZipFile(io.BytesIO(sim.export_bytes())).read('events.jsonl').splitlines()]
        reported = {e['interface_index'] for e in events if e['event'] == 'interface_state' and e['node_id'] == 'auv_01'}
        assert reported == {1, 2}


def test_manual_interface_selection_in_attached_holoocean(engine):
    data = load_scenario('e01_chat').model_dump()
    data['flows'] = []
    data['network']['multiphy'] = {'interfaces': INTERFACES, 'initial_interface': 'long', 'policy': 'manual'}
    scenario = Scenario.model_validate(data)
    owner = HoloOceanAdapter(scenario, show_viewport=False)
    owner.start()
    env = owner.env
    try:
        net = NetworkSession(scenario, manage_engine=False)
        link = HoloOceanLink(net, ticks_per_sec=scenario.physics_hz)
        received, used = [], []
        with net:
            net.node('auv_02').on_receive(received.append)
            link.attach(env.reset())

            def exchange(label, seconds=4):
                net.node('auv_01').send_json('auv_02', {'via': label})
                for _ in range(seconds * scenario.physics_hz):
                    for agent, target in (('auv_01', [0, 0, -20]), ('auv_02', [30, 0, -20])):
                        env.act(agent, [*target, 0, 0, 0])
                    events = link.sync(env.tick(publish=False))
                    used.extend(e['interface_index'] for e in events if e['event'] == 'phy_tx_start')

            exchange('long')
            for node in ('auv_01', 'auv_02'):
                net.node(node).select_interface('short')
            exchange('short')
            # POWER acts on each node's first interface ("long") only.
            net.node('auv_01').set_tx_power(0)
            exchange('short at 0 dB on long')
            for node in ('auv_01', 'auv_02'):
                net.node(node).select_interface('long')
            exchange('long at 0 dB')
        assert [d.message.json()['via'] for d in received] == ['long', 'short', 'short at 0 dB on long']
        assert used == [1, 2, 2, 1]
    finally:
        owner.stop()
