"""Mixed acoustic/optical multi-PHY: schema, builder rules and rendered Tcl."""
import pytest

from holo_desert.resources.docker.multiphy_config import effective_interfaces
from holo_desert.resources.docker.stack_builder import render
from holo_desert.scenarios.config import Scenario, ScenarioManager


def hybrid(policy='manual', **extra):
    data = ScenarioManager().load('e01_chat').model_dump()
    for i, node in enumerate(data['nodes']):
        node['position'] = [i * 8, 0, -10]
    data['network']['multiphy'] = {'interfaces': [
        {'id': 'acoustic', 'acoustic': {'frequency_hz': 25000, 'bandwidth_hz': 5000, 'tx_power_db': 150}},
        {'id': 'optical', 'medium': 'optical', 'optical': {'tx_power_w': 20, 'bitrate_bps': 500000}}],
        'initial_interface': 'acoustic', 'policy': policy, **extra}
    return data


def test_optical_interface_inherits_network_optical_and_its_overrides():
    data = hybrid()
    data['network']['optical'] = {'attenuation_per_m': .08}
    interfaces = effective_interfaces(Scenario.model_validate(data).model_dump())[0]['interfaces']
    assert [(i['id'], i['medium']) for i in interfaces] == [('acoustic', 'acoustic'), ('optical', 'optical')]
    optical = interfaces[1]['optical']
    assert (optical['tx_power_w'], optical['bitrate_bps'], optical['attenuation_per_m']) == (20, 500000, .08)
    assert 'optical' not in interfaces[0] and interfaces[0]['acoustic']['tx_power_db'] == 150


def test_hybrid_renders_one_channel_per_medium_and_medium_specific_settings():
    text = render(Scenario.model_validate(hybrid()).model_dump())
    assert 'set multi_optical 1' in text
    assert 'set multi_medium(1,2) optical' in text and 'set multi_medium(2,1) acoustic' in text
    assert 'set multi_phy_class(1,2) Module/UW/OPTICAL/PHY/HOLO' in text
    assert 'tx_power_w 20' in text and 'bitrate_bps 500000' in text


def test_optical_first_interface_sets_the_node_phy_class():
    data = hybrid()
    data['network']['multiphy']['interfaces'].reverse()
    data['network']['multiphy']['initial_interface'] = 'optical'
    text = render(Scenario.model_validate(data).model_dump())
    assert 'set phy_class(1) Module/UW/OPTICAL/PHY/HOLO' in text


@pytest.mark.parametrize('change,match', [
    (lambda d: d['network']['multiphy']['interfaces'][1].update(acoustic={'tx_power_db': 140}), 'optical interface'),
    (lambda d: d['network']['multiphy']['interfaces'][0].update(optical={'tx_power_w': 1}), 'acoustic interface'),
    (lambda d: d['nodes'][1].update(position=[8, 0, -25]), 'noise LUT'),
    (lambda d: d['nodes'][1].update(communication={'interfaces': ['acoustic', 'optical'], 'interface_overrides': {'optical': {'tx_power_db': 120}}}), 'optical'),
    (lambda d: d['network']['multiphy']['interfaces'][1].update(medium='em'), 'medium|literal')])
def test_hybrid_rejects_settings_of_the_wrong_medium_and_unsupported_depths(change, match):
    data = hybrid()
    change(data)
    with pytest.raises(ValueError, match=match):
        Scenario.model_validate(data)
    with pytest.raises(ValueError):
        render(data)


def test_acoustic_bands_must_stay_disjoint_but_optical_uses_its_own_channel():
    data = hybrid()
    data['network']['multiphy']['interfaces'][1]['optical'].update(frequency_hz=25000, bandwidth_hz=5000)
    Scenario.model_validate(data)  # optical overlap with the acoustic band is irrelevant: separate channel
    data['network']['multiphy']['interfaces'].append({'id': 'second', 'acoustic': {'frequency_hz': 26000, 'bandwidth_hz': 5000}})
    with pytest.raises(ValueError, match='disjoint'):
        Scenario.model_validate(data)


def test_received_power_thresholds_and_power_events_follow_the_interface_medium():
    data = hybrid('received_power', thresholds=[
        {'from_interface': 'acoustic', 'to_interface': 'optical', 'power_linear': 1e13},
        {'from_interface': 'optical', 'to_interface': 'acoustic', 'power_linear': 1e-9}])
    data['power_events'] = [{'time': 2, 'node': 'auv_01', 'interface': 'optical', 'tx_power_w': 1e-12},
                            {'time': 3, 'node': 'auv_02', 'interface': 'acoustic', 'tx_power_db': 0}]
    scenario = Scenario.model_validate(data)
    assert [e.interface for e in scenario.power_events] == ['optical', 'acoustic']
    data['power_events'] = [{'time': 2, 'node': 'auv_01', 'interface': 'optical', 'tx_power_db': 100}]
    with pytest.raises(ValueError, match='tx_power_w'):
        Scenario.model_validate(data)
    data['power_events'] = [{'time': 2, 'node': 'auv_01', 'interface': 'missing', 'tx_power_w': 1}]
    with pytest.raises(ValueError, match='interface'):
        Scenario.model_validate(data)


def test_automatic_switching_needs_acoustic_before_optical():
    data = hybrid('received_power', thresholds=[
        {'from_interface': 'optical', 'to_interface': 'acoustic', 'power_linear': 1e-9},
        {'from_interface': 'acoustic', 'to_interface': 'optical', 'power_linear': 1e13}])
    data['network']['multiphy']['interfaces'].reverse()
    data['network']['multiphy']['initial_interface'] = 'optical'
    with pytest.raises(ValueError, match='acoustic before optical'):
        Scenario.model_validate(data)
    data['network']['multiphy']['policy'], data['network']['multiphy']['thresholds'] = 'manual', []
    Scenario.model_validate(data)  # any order works when the application selects the interface


def adapter(data):
    from holo_desert.desert_adapter.backend import DESERTAdapter
    from holo_desert.resources.docker.multiphy_config import effective_interfaces
    scenario = Scenario.model_validate(data)
    backend, sent = DESERTAdapter(manage_docker=False), []
    effective = effective_interfaces(scenario.model_dump())
    backend.nodes, backend.medium, backend.time, backend.positions = scenario.node_map, 'acoustic', 0.0, {}
    backend.multi_interfaces = {n['id']: {p['id']: p['index'] for p in n['interfaces']} for n in effective}
    backend.multi_media = {n['id']: {p['id']: p['medium'] for p in n['interfaces']} for n in effective}
    backend.optical_nodes = {n for n, media in backend.multi_media.items() if 'optical' in media.values()}
    backend._command = sent.append
    return backend, sent


def test_power_and_positions_follow_the_interface_medium():
    from holo_desert.common.models import Pose
    data = hybrid()
    data['nodes'][1]['communication'] = {'interfaces': ['acoustic']}
    backend, sent = adapter(data)
    backend.set_power('auv_01', 1e-3, 'optical')
    backend.set_power('auv_01', 140)                      # first interface: acoustic, dB re uPa
    with pytest.raises(ValueError, match='W'):
        backend.set_power('auv_01', 20000, 'optical')
    with pytest.raises(ValueError, match='Unknown'):
        backend.set_power('auv_02', 1e-3, 'optical')       # this drone has no optical modem
    assert sent == ['POWER 1 0.001 2', 'POWER 1 140 1']
    backend.update_node_position('auv_01', Pose(0, 0, -10, 90), 0)
    backend.update_node_position('auv_02', Pose(8, 0, -30), 0)  # acoustic only: no depth limit, no angles
    assert sent[2].startswith('POSITION 1 0 0 -10 0 1.57') and sent[3] == 'POSITION 2 8 0 -30 0'
    with pytest.raises(ValueError, match='20 m'):
        backend.update_node_position('auv_01', Pose(0, 0, -25), 0)
