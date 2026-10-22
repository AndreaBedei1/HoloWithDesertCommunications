"""Real DESERT packets and measurements; select an isolated engine with DESERT_PORT."""
import math

import pytest

from holo_desert.common.models import Message, Pose
from holo_desert.desert_adapter.backend import DESERTAdapter
from holo_desert.scenarios.config import Scenario, ScenarioManager

pytestmark = pytest.mark.desert


@pytest.mark.parametrize('protocol', ['csburst', 'tokenbus', 'ranging_tokenbus'])
@pytest.mark.parametrize('phy', ['bpsk_upstream', 'bpsk_corrected'])
def test_native_additional_mac_delivery_restart_and_queue(engine, protocol, phy):
    data = ScenarioManager().load('e01_chat').model_dump()
    data['network']['mac'].update(protocol=protocol, buffer_packets=1)
    data['network']['acoustic']['phy'] = phy
    scenario = Scenario.model_validate(data)
    for _ in range(2):
        backend = DESERTAdapter(manage_docker=False)
        try:
            backend.start(scenario)
            for i, node in enumerate(scenario.nodes):
                backend.update_node_position(node.id, Pose(i*20, 0, -20), 0)
            for t, src, dst in [(0, 'auv_01', 'auv_02'), (15, 'auv_02', 'auv_01')]:
                message = Message(src, dst, b'native-additional' * 16, t)
                backend.send(message)
                backend.request_stats()
                events = backend.advance(t+15)
                assert sum(e['event'] == 'rx' and Message.decode(bytes.fromhex(e['wire_hex'])).id == message.id for e in events) == 1
                assert any(e['event'] == 'mac_specific_stats' and e['values'] for e in events)
                if protocol != 'csburst':
                    assert any(e['event'].startswith('phy_control_') for e in events)
            messages = [Message('auv_01', 'auv_02', bytes([i]), 30) for i in range(6)]
            for message in messages:
                backend.send(message)
            backend.request_stats()
            events = backend.advance(50)
            queues = [e['mac_queue'] for e in events if e['event'] == 'stats']
            assert queues and max(queues) <= 1
            received = {Message.decode(bytes.fromhex(e['wire_hex'])).id for e in events if e['event'] == 'rx'}
            assert 0 < len(received & {m.id for m in messages}) < len(messages)
        finally:
            backend.stop()


@pytest.mark.parametrize('count', [2, 3, 5])
def test_native_ranging_missing_multinode_and_movement(engine, count):
    data = ScenarioManager().load('e01_chat').model_dump()
    data['network']['mac']['protocol'] = 'ranging_tokenbus'
    data['flows'] = []
    data['nodes'] = [dict(data['nodes'][0], id=f'auv_{i+1:02d}') for i in range(count)]
    scenario = Scenario.model_validate(data)
    backend = DESERTAdapter(manage_docker=False)
    try:
        backend.start(scenario)
        for i, node in enumerate(scenario.nodes):
            backend.update_node_position(node.id, Pose(i*20, 0, -20), 0)
        backend.request_stats()
        initial = backend.advance(.00001)
        missing = [e for e in initial if e['event'] == 'ranging_estimate']
        assert missing and all(not e['valid'] and e['distance_m'] is None for e in missing)
        backend.advance(120)
        backend.request_stats()
        events = backend.advance(121)
        estimates = [e for e in events if e['event'] == 'ranging_estimate' and e['valid']]
        assert {tuple(sorted((e['peer_a'], e['peer_b']))) for e in estimates} == {(a, b) for a in range(1, count+1) for b in range(a+1, count+1)}
        assert all(math.isfinite(e['distance_m']) and e['distance_m'] == pytest.approx((e['peer_b']-e['peer_a'])*20, abs=.1) for e in estimates)
        backend.update_node_position(scenario.nodes[-1].id, Pose((count-1)*20+15, 0, -20), 121)
        backend.advance(240)
        backend.request_stats()
        moved = [e for e in backend.advance(241) if e['event'] == 'ranging_estimate' and e['valid'] and e['peer_b'] == count]
        assert moved and all(e['distance_m'] == pytest.approx((count-e['peer_a'])*20+15, abs=.5) for e in moved)
        assert all(e['measurement_time'] is None for e in estimates + moved)
    finally:
        backend.stop()


@pytest.mark.parametrize('phy', ['bpsk_upstream', 'bpsk_corrected'])
@pytest.mark.parametrize('restart', [0, 1])
def test_sun_native_repeated_convergecast(engine, phy, restart):
    data = ScenarioManager().load('e01_chat').model_dump()
    data['network'].update(routing='sun', sun={'sink': 'auv_02'})
    data['network']['mac']['protocol'] = 'csma_aloha'
    data['network']['acoustic']['phy'] = phy
    data['flows'] = []
    backend = DESERTAdapter(manage_docker=False)
    try:
        backend.start(Scenario.model_validate(data))
        for i, node in enumerate(data['nodes']):
            backend.update_node_position(node['id'], Pose(i*20, 0, -20), 0)
        backend.advance(5)
        for t in (5, 15, 25):
            message = Message('auv_01', 'auv_02', b'sun-repeat', t)
            backend.send(message)
            events = backend.advance(t+10)
            assert any(e['event'] == 'rx' and Message.decode(bytes.fromhex(e['wire_hex'])).id == message.id for e in events), events
        backend.request_stats()
        events = backend.advance(36)
        stats = [e for e in events if e['event'] == 'routing_stats']
        assert {e['role'] for e in stats} == {'node', 'sink'}
        assert next(e['class_values']['acks'] for e in stats if e['role'] == 'sink') >= 3
        messages = [Message('auv_01', 'auv_02', bytes([i]), 36) for i in range(3)]
        for message in messages:
            backend.send(message)
        events = backend.advance(60)
        received = {Message.decode(bytes.fromhex(e['wire_hex'])).id for e in events if e['event'] == 'rx'}
        assert {m.id for m in messages} <= received
    finally:
        backend.stop()


def test_sun_native_multihop_with_two_available_paths(engine):
    data = ScenarioManager().load('e01_chat').model_dump()
    data['network'].update(routing='sun', sun={'sink': 'auv_05', 'probe_interval_s': 10,
        'probe_min_snr_db': 20, 'buffer_interval_s': 5, 'max_ack_errors': 10})
    data['network']['mac']['protocol'] = 'csma_aloha'
    data['network']['acoustic']['tx_power_db'] = 132
    data['flows'] = []
    positions = [(0, 0), (450, 150), (450, -150), (900, 0), (1350, 0)]
    data['nodes'] = [dict(data['nodes'][0], id=f'auv_{i+1:02d}') for i in range(5)]
    backend = DESERTAdapter(manage_docker=False)
    try:
        backend.start(Scenario.model_validate(data))
        for node, (x, y) in zip(data['nodes'], positions):
            backend.update_node_position(node['id'], Pose(x, y, -20), 0)
        backend.advance(15)
        message = Message('auv_01', 'auv_05', b'native-sun-multihop', 15, ttl=300)
        backend.send(message)
        events = backend.advance(240)
        backend.request_stats()
        events += backend.advance(241)
        rx = [e for e in events if e['event'] == 'rx' and Message.decode(bytes.fromhex(e['wire_hex'])).id == message.id]
        assert any(e['node'] == 5 for e in rx), [e for e in events if e['event'] in ('routing_stats', 'error')]
        forwarded = {e['node'] for e in events if e['event'] == 'forward' and e['source_address'] == 1 and e['destination_address'] == 5}
        assert 4 in forwarded and forwarded & {2, 3}, forwarded
        stats = [e for e in events if e['event'] == 'routing_stats' and e['role'] == 'node']
        assert any(e['values']['paths_established'] > 0 for e in stats)
    finally:
        backend.stop()


@pytest.mark.parametrize('generator', ['desert_cbr', 'desert_vbr'])
def test_sun_native_generators_ack_and_delivery(engine, generator):
    data = ScenarioManager().load('e01_chat').model_dump()
    data['network']['routing'] = 'sun'
    data['flows'] = [dict(data['flows'][0], generator=generator, reply=False,
        source='auv_01', destination='auv_02', start=5, stop=20, interval=5,
        native_period2_s=5, native_packet_bytes=125)]
    backend = DESERTAdapter(manage_docker=False)
    try:
        backend.start(Scenario.model_validate(data))
        for i, node in enumerate(data['nodes']):
            backend.update_node_position(node['id'], Pose(i*20, 0, -20), 0)
        events = backend.advance(60)
        sent = {e['native_packet_id'] for e in events if e['event'] == 'native_app_tx'}
        received = {e['native_packet_id'] for e in events if e['event'] == 'native_app_rx'}
        assert len(sent) >= 2 and sent <= received
        backend.request_stats()
        events = backend.advance(61)
        assert next(e['values']['queue'] for e in events if e['event'] == 'routing_stats' and e['role'] == 'node') == 0
    finally:
        backend.stop()
