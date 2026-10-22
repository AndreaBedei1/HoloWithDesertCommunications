"""The values held by the native DESERT objects, read back at t=0, match the request."""
import pytest

from holo_desert.desert_adapter.backend import DESERTAdapter
from holo_desert.scenarios.config import Scenario, ScenarioManager

pytestmark = pytest.mark.desert


def applied(data):
    backend = DESERTAdapter(manage_docker=False)
    try:
        backend.start(Scenario.model_validate(data))
        records = [e for e in backend.initial_events if e['event'] == 'native_bindings']
    finally:
        backend.stop()
    def pick(module, node=None, **match):
        found = [r for r in records if r['module'] == module and r.get('node') == node and all(r.get(k) == v for k, v in match.items())]
        assert len(found) == 1, (module, node, match, records)
        return found[0]
    return pick


def e01(**network):
    data = ScenarioManager().load('e01_chat').model_dump()
    for key, value in network.items():
        current = data['network'].get(key)
        if isinstance(value, dict) and isinstance(current, dict):
            current.update(value)
        else:
            data['network'][key] = value
    return data


def test_acoustic_phy_mac_channel_and_node_overrides_reach_native_objects(engine):
    data = e01(acoustic={'tx_power_db': 140, 'bitrate_bps': 2400, 'frequency_hz': 26000, 'bandwidth_hz': 4000,
                         'sound_speed_mps': 1490, 'rx_snr_penalty_db': -7})
    data['network']['mac'].update(max_tx_tries=5, ack=True)
    data['nodes'][1]['communication'] = {'acoustic': {'tx_power_db': 120, 'phy': 'bpsk_corrected'}}
    pick = applied(data)
    one, two = pick('phy', 1), pick('phy', 2)
    assert one['class'] == 'Module/MPhy/BPSK/Underwater/HOLO' and two['class'] == 'Module/MPhy/BPSK/Underwater/HOLO/Corrected'
    assert one['values']['MaxTxSPL_dB_'] == 140 and two['values']['MaxTxSPL_dB_'] == 120
    assert one['values']['BitRate_'] == 2400 and one['values']['RxSnrPenalty_dB_'] == -7
    assert pick('mask', 1)['values'] == {'frequency_hz': 26000, 'bandwidth_hz': 4000}
    assert pick('channel')['values']['propSpeed_'] == 1490
    assert pick('mac', 1)['class'] == 'Module/UW/CSMA_ALOHA' and pick('mac', 1)['values']['max_tx_tries_'] == 5
    assert pick('routing', 2)['class'] == 'Module/UW/StaticRouting'


@pytest.mark.parametrize('protocol,section,expected', [
    ('tdma', {'frame_duration_s': 4, 'guard_time_s': .2}, {'frame_duration': 4, 'guard_time': .2, 'tot_slots': 2, 'max_packet_per_slot': 1}),
    ('ranging_tdma', {'frame_duration_s': 4, 'guard_time_s': .2, 'max_packets_per_slot': 3}, {'frame_duration': 4, 'guard_time': .2, 'tot_slots': 2, 'max_packet_per_slot': 3}),
    ('tokenbus', {'slot_time_s': 7, 'max_token_hold_s': 6}, {'n_nodes_': 2, 'slot_time_': 7, 'max_token_hold_time_': 6}),
    ('csburst', {'max_packets_per_burst': 4, 'fixed_sensing_s': .3}, {'max_packet_per_burst': 4, 'fix_sens_time': .3}),
    ('dacap', {'delta_d': 900, 't_min': 1.5}, {'delta_D': 900, 't_min': 1.5})])
def test_mac_parameters_reach_native_objects(engine, protocol, section, expected):
    data = e01()
    data['flows'] = []
    data['network']['mac'].update(protocol=protocol, **{protocol: section})
    values = applied(data)('mac', 2)['values']
    assert {k: values[k] for k in expected} == pytest.approx(expected)


def test_sun_roles_and_parameters_reach_native_objects(engine):
    data = e01(routing='sun', sun={'sink': 'auv_02', 'probe_interval_s': 3, 'max_retransmissions': 4})
    data['flows'] = []
    pick = applied(data)
    assert pick('routing', 2)['class'] == 'Module/UW/SUNSink' and pick('routing', 2)['values']['t_probe'] == 3
    assert pick('routing', 1)['class'] == 'Module/UW/SUNNode' and pick('routing', 1)['values']['max_retx_'] == 4


@pytest.mark.parametrize('medium,settings,phy,propagation', [
    ('optical', {'tx_power_w': 20, 'attenuation_per_m': .05, 'beam_angle_rad': .8},
     {'TxPower_': 20, 'BitRate_': 1000000}, {'c_': .05, 'theta_': .8}),
    ('em', {'tx_power_dbm': -5, 'salinity_ppt': 3, 'temperature_c': 12},
     {'TxPower_': -5, 'BitRate_': 27000}, {'S_': 3, 'T_': 12})])
def test_media_parameters_reach_native_objects(engine, medium, settings, phy, propagation):
    data = e01(medium=medium)
    data['network'][medium].update(settings)
    for i, node in enumerate(data['nodes']):
        node['position'] = [i, 0, -10]
    pick = applied(data)
    values = pick('phy', 1)['values']
    assert {k: values[k] for k in phy} == pytest.approx(phy)
    values = pick('propagation', 1)['values']
    assert {k: values[k] for k in propagation} == pytest.approx(propagation)


def test_multiphy_interfaces_and_controller_reach_native_objects(engine):
    data = e01(multiphy={'interfaces': [
        {'id': 'long', 'acoustic': {'frequency_hz': 25000, 'bandwidth_hz': 5000, 'bitrate_bps': 4800, 'tx_power_db': 150}},
        {'id': 'short', 'acoustic': {'frequency_hz': 50000, 'bandwidth_hz': 9000, 'bitrate_bps': 8800, 'tx_power_db': 145}}],
        'initial_interface': 'long', 'policy': 'received_power', 'alpha': .3,
        'thresholds': [{'from_interface': 'long', 'to_interface': 'short', 'power_linear': 1e12},
                       {'from_interface': 'short', 'to_interface': 'long', 'power_linear': 2e11}]})
    pick = applied(data)
    assert pick('phy', 1, interface_index=2)['values']['MaxTxSPL_dB_'] == 145
    assert pick('phy', 1, interface_index=2)['values']['BitRate_'] == 8800
    assert pick('mask', 2, interface_index=1)['values'] == {'frequency_hz': 25000, 'bandwidth_hz': 5000}
    assert pick('controller', 1)['class'] == 'Module/UW/MULTI_STACK_CONTROLLER_PHY_MASTER'
    assert pick('controller', 1)['values']['alpha_'] == pytest.approx(.3)
    assert pick('controller', 2)['class'] == 'Module/UW/MULTI_STACK_CONTROLLER_PHY_SLAVE'


@pytest.mark.parametrize('generator,expected', [
    ('desert_cbr', {'period_': 4, 'packetSize_': 64, 'PoissonTraffic_': 0}),
    ('desert_vbr', {'period1_': 4, 'period2_': 1.5, 'timer_switch_1_': 6, 'timer_switch_2_': 7, 'packetSize_': 64})])
def test_native_generator_timers_reach_native_objects(engine, generator, expected):
    data = e01()
    data['flows'][0].update(generator=generator, reply=False, interval=4, native_packet_bytes=64,
                            native_period2_s=1.5, native_duration1_s=6, native_duration2_s=7)
    values = applied(data)('application', 1, flow_index=0)['values']
    assert {k: values[k] for k in expected} == pytest.approx(expected)
