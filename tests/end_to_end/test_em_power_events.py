"""EM transmit-power events in dBm (negative values included) inside HoloOcean."""
import pytest

from holo_desert import ManagedSimulation, Scenario, load_scenario

pytestmark = [pytest.mark.desert, pytest.mark.holoocean]


def test_negative_dbm_power_event_interrupts_and_restores_em_link(engine):
    data = load_scenario('e01_chat').model_dump()
    data.update(duration=24, realtime=False,
                power_events=[{'time': 8, 'node': 'auv_01', 'tx_power_dbm': -20},
                              {'time': 16, 'node': 'auv_01', 'tx_power_dbm': 20}])
    data['network'].update(medium='em')
    data['network']['em'].update(tx_power_dbm=20, salinity_ppt=0)
    # Fresh water at 868 MHz: 20 dBm decodes over 2 m, -20 dBm does not (native LUT).
    data['nodes'][0]['position'], data['nodes'][1]['position'] = [0, 0, -10], [2, 0, -10]
    data['flows'] = [{'source': 'auv_01', 'destination': 'auv_02', 'start': 2, 'interval': 2, 'stop': 23,
                      'ttl': 3, 'payload_bytes': 8}]
    with ManagedSimulation(Scenario.model_validate(data), realtime=False, manage_engine=False) as sim:
        sim.run()
        state = sim.snapshot()
        assert [e['tx_power_dbm'] for e in state['transitions'] if e['event'] == 'power_applied'] == [-20, 20]
        outcome = {round(p['creation_time']): p['status'] for p in state['packets']}
        assert {t for t, s in outcome.items() if s == 'received'} == {2, 4, 6, 16, 18, 20, 22}
        assert {t for t, s in outcome.items() if s != 'received'} == {8, 10, 12, 14}
        assert state['services']['holoocean'] == 'stopped' and len(state['fleet']) == 2
