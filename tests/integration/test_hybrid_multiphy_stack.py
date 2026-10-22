"""Mixed acoustic/optical multi-PHY through the real bridge: one MAC, native controllers, two channels."""
import pytest

from holo_desert.common.models import Message, Pose
from holo_desert.desert_adapter.backend import DESERTAdapter
from holo_desert.scenarios.config import Scenario, ScenarioManager

pytestmark = pytest.mark.desert

ACOUSTIC = {'id': 'acoustic', 'acoustic': {'frequency_hz': 25000, 'bandwidth_hz': 5000, 'bitrate_bps': 4800, 'tx_power_db': 150}}
OPTICAL = {'id': 'optical', 'medium': 'optical', 'optical': {'bitrate_bps': 1000000}}


def scenario(interfaces=(ACOUSTIC, OPTICAL), policy='manual', **multi):
    data = ScenarioManager().load('e01_chat').model_dump()
    for i, node in enumerate(data['nodes']):
        node['position'] = [i * 10, 0, -10]
    data['network']['multiphy'] = {'interfaces': list(interfaces), 'initial_interface': interfaces[0]['id'],
                                   'policy': policy, **multi}
    return Scenario.model_validate(data)


def place(backend, distance):
    for i, node in enumerate(('auv_01', 'auv_02')):
        backend.update_node_position(node, Pose(i * distance, 0, -10), backend.time)


def exchange(backend, source='auv_01', destination='auv_02', seconds=5):
    message = Message(source, destination, b'hybrid', backend.time)
    backend.send(message)
    events = backend.advance(backend.time + seconds)
    delivered = any(e['event'] == 'rx' and Message.decode(bytes.fromhex(e['wire_hex'])).id == message.id for e in events)
    tx = [e for e in events if e['event'] == 'phy_tx_start' and e['node'] == backend.nodes[source]]
    return delivered, tx, events


def select(backend, interface):
    for node in ('auv_01', 'auv_02'):
        backend.set_interface(node, interface)


def test_manual_hybrid_delivers_on_each_medium_within_its_own_range(engine):
    backend = DESERTAdapter(manage_docker=False)
    try:
        backend.start(scenario())
        place(backend, 10)
        delivered, tx, _ = exchange(backend)
        assert delivered and tx[0]['interface_index'] == 1 and tx[0].get('medium') is None
        select(backend, 'optical')
        delivered, tx, events = exchange(backend)
        assert delivered and tx[0]['interface_index'] == 2 and tx[0]['medium'] == 'optical' and tx[0]['power_unit'] == 'W'
        assert any(e['event'] == 'phy_rx_end' and e.get('medium') == 'optical' and e['outcome'] == 'decoded' for e in events)
        # 100 m is far beyond the optical link and well inside the acoustic one.
        place(backend, 100)
        delivered, tx, events = exchange(backend)
        assert not delivered and tx[0]['medium'] == 'optical'
        assert any(e['event'] == 'phy_rx_start' and e.get('medium') == 'optical' and e['outcome'] == 'below_acquisition_threshold'
                   for e in events)
        select(backend, 'acoustic')
        delivered, tx, _ = exchange(backend)
        assert delivered and tx[0]['interface_index'] == 1
    finally:
        backend.stop()


def test_optical_first_interface_is_the_node_phy(engine):
    backend = DESERTAdapter(manage_docker=False)
    try:
        backend.start(scenario((OPTICAL, ACOUSTIC)))
        place(backend, 10)
        delivered, tx, _ = exchange(backend)
        assert delivered and tx[0]['interface_index'] == 1 and tx[0]['medium'] == 'optical'
    finally:
        backend.stop()


def test_power_on_the_optical_interface_is_in_watts_and_leaves_the_acoustic_one(engine):
    backend = DESERTAdapter(manage_docker=False)
    try:
        backend.start(scenario())
        place(backend, 10)
        backend.set_power('auv_01', 1e-15, 'optical')
        select(backend, 'optical')
        delivered, _, events = exchange(backend)
        applied = next(e for e in events if e['event'] == 'power_applied')
        assert applied['tx_power_w'] == 1e-15 and applied['interface_index'] == 2 and not delivered
        select(backend, 'acoustic')
        assert exchange(backend)[0]
    finally:
        backend.stop()


def test_each_interface_reports_its_own_native_objects(engine):
    backend = DESERTAdapter(manage_docker=False)
    try:
        data = scenario().model_dump()
        data['network']['optical']['attenuation_per_m'] = .08
        backend.start(Scenario.model_validate(data))
        records = [e for e in backend.initial_events if e['event'] == 'native_bindings' and e.get('node') == 1]
        pick = lambda module, index: next(r for r in records if r['module'] == module and r.get('interface_index') == index)
        assert pick('phy', 1)['class'] == 'Module/MPhy/BPSK/Underwater/HOLO' and pick('phy', 1)['values']['MaxTxSPL_dB_'] == 150
        optical = pick('phy', 2)
        assert optical['class'] == 'Module/UW/OPTICAL/PHY/HOLO' and optical['medium'] == 'optical'
        assert optical['values']['BitRate_'] == 1000000
        assert pick('propagation', 2)['class'] == 'Module/UW/OPTICAL/Propagation/HOLO'
        assert pick('propagation', 2)['values']['c_'] == pytest.approx(.08)
    finally:
        backend.stop()


def test_received_power_master_uses_optical_near_and_acoustic_far(engine):
    # Above 1e13 (acoustic linear power, about 14 m) the master moves to optical; below 3e-8 W
    # (about 28 m, before the optical receiver stops synchronising near 38 m) it returns to acoustic.
    backend = DESERTAdapter(manage_docker=False)
    try:
        backend.start(scenario(policy='received_power', master='auv_01', thresholds=[
            {'from_interface': 'acoustic', 'to_interface': 'optical', 'power_linear': 1e13},
            {'from_interface': 'optical', 'to_interface': 'acoustic', 'power_linear': 3e-8}]))
        slave, master = [], []
        for distance in (8, 8, 20, 50, 100, 8, 8):
            place(backend, distance)
            for source, destination, record in (('auv_02', 'auv_01', slave), ('auv_01', 'auv_02', master)):
                delivered, tx, _ = exchange(backend, source, destination)
                record.append((distance, delivered, tx[0]['interface_index']))
        assert master == [(8, True, 2), (8, True, 2), (20, True, 2), (50, True, 1), (100, True, 1), (8, True, 2), (8, True, 2)]
        # The slave follows the last interface it heard; its first packet beyond optical range is lost.
        assert slave == [(8, True, 1), (8, True, 2), (20, True, 2), (50, False, 2), (100, True, 1), (8, True, 1), (8, True, 2)]
    finally:
        backend.stop()
