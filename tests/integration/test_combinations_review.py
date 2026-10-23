"""Combinations the schema accepts for Position-Based Routing and hybrid multi-PHY, each through real DESERT."""
import pytest

from holo_desert.common.models import Message, Pose
from holo_desert.desert_adapter.backend import DESERTAdapter
from holo_desert.scenarios.config import Scenario

import test_hybrid_multiphy_stack as hybrid
import test_position_based_routing as pbr

pytestmark = pytest.mark.desert


def delivered(backend, source, destination, seconds=10, **send):
    message = Message(source, destination, b'combination', backend.time)
    backend.send(message)
    events = backend.advance(backend.time + seconds)
    return any(e['event'] == 'rx' and Message.decode(bytes.fromhex(e['wire_hex'])).id == message.id for e in events)


@pytest.mark.parametrize('mac', [{'ack': True}, {'queue_mode': 'bounded', 'buffer_packets': 10}])
def test_position_based_routing_with_ack_or_bounded_queue(engine, mac):
    data = pbr.scenario().model_dump()
    data['network']['mac'].update(mac)
    run = pbr.Run(Scenario.model_validate(data))
    try:
        for x in (-500, 500):
            run.place(x)
            assert run.send('auv_04', 'auv_01')[0] and run.send('auv_01', 'auv_04')[0], (mac, x)
    finally:
        run.backend.stop()


def test_position_based_routing_between_two_vehicles_goes_through_anchors(engine):
    data = pbr.scenario().model_dump()
    data['nodes'].append({'id': 'auv_05', 'position': [500, 200, -100]})
    data['network']['routes'].update({'auv_01': {'auv_03': 'auv_02', 'auv_04': 'auv_02', 'auv_05': 'auv_02'},
                                      'auv_02': {'auv_04': 'auv_03', 'auv_05': 'auv_03'}})
    run = pbr.Run(Scenario.model_validate(data))
    try:
        for node, position in pbr.ANCHORS.items():
            run.backend.update_node_position(node, Pose(*position), run.backend.time)
        run.backend.update_node_position('auv_04', Pose(-500, 200, -100), run.backend.time)
        run.backend.update_node_position('auv_05', Pose(500, 200, -100), run.backend.time)
        # Each vehicle first reports its position along the anchors' path to auv_01 (an anchor that never
        # heard a vehicle estimates it at the origin), then the two vehicles exchange through the anchors.
        assert run.send('auv_04', 'auv_01')[0] and run.send('auv_05', 'auv_01')[0]
        ok, forwards = run.send('auv_04', 'auv_05')
        assert ok and forwards[0] == (4, 1) and forwards[-1][1] == 5, forwards
    finally:
        run.backend.stop()


def test_hybrid_with_three_interfaces_and_a_node_without_optical(engine):
    second = {'id': 'short', 'acoustic': {'frequency_hz': 50000, 'bandwidth_hz': 9000, 'bitrate_bps': 8800, 'tx_power_db': 150}}
    data = hybrid.scenario((hybrid.ACOUSTIC, second, hybrid.OPTICAL)).model_dump()
    backend = DESERTAdapter(manage_docker=False)
    try:
        backend.start(Scenario.model_validate(data))
        hybrid.place(backend, 8)
        for interface in ('acoustic', 'short', 'optical'):
            hybrid.select(backend, interface)
            ok, tx, _ = hybrid.exchange(backend)
            assert ok and tx[0]['interface_index'] == {'acoustic': 1, 'short': 2, 'optical': 3}[interface]
    finally:
        backend.stop()
    data['nodes'][1]['communication'] = {'interfaces': ['acoustic', 'short']}
    backend = DESERTAdapter(manage_docker=False)
    try:
        backend.start(Scenario.model_validate(data))
        hybrid.place(backend, 8)
        assert hybrid.exchange(backend)[0]
        backend.set_interface('auv_01', 'optical')
        assert not hybrid.exchange(backend)[0]           # auv_02 has no optical modem
    finally:
        backend.stop()


def test_hybrid_with_a_directional_optical_interface_follows_the_heading(engine):
    data = hybrid.scenario().model_dump()
    data['network']['optical']['directional'] = True
    backend = DESERTAdapter(manage_docker=False)
    try:
        backend.start(Scenario.model_validate(data))
        hybrid.select(backend, 'optical')
        for yaw, expected in ((0, True), (180, False)):
            backend.update_node_position('auv_01', Pose(0, 0, -10, yaw), backend.time)
            backend.update_node_position('auv_02', Pose(8, 0, -10, 180), backend.time)
            assert hybrid.exchange(backend)[0] is expected, yaw
    finally:
        backend.stop()


def test_hybrid_with_native_generators(engine):
    from holo_desert.core.orchestrator import SimulationOrchestrator
    data = hybrid.scenario().model_dump()
    data.update(duration=12, realtime=False)
    data['flows'] = [{'source': 'auv_01', 'destination': 'auv_02', 'start': 1, 'stop': 9, 'interval': 2,
                      'generator': 'desert_cbr', 'native_packet_bytes': 32}]
    run = SimulationOrchestrator(Scenario.model_validate(data), standalone=True, manage_docker=False)
    try:
        run.run()
        assert run.state == 'finished', run.error
        assert run.snapshot()['counts']['received'] >= 3
    finally:
        run.close()
