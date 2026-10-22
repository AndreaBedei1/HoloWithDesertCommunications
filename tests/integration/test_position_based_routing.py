"""Native Position-Based Routing through the real bridge, without global ground truth."""
import pytest

from holo_desert.common.models import Message, Pose
from holo_desert.desert_adapter.backend import DESERTAdapter
from holo_desert.scenarios.config import Scenario, ScenarioManager

pytestmark = pytest.mark.desert

# Anchors 1-3 on a line 500 m apart; the vehicle (4) travels 200 m off that line.
ANCHORS = {'auv_01': [-500, 0, -100], 'auv_02': [0, 0, -100], 'auv_03': [500, 0, -100]}


def scenario(**position_based):
    data = ScenarioManager().load('e01_chat').model_dump()
    data['nodes'] = [{'id': node, 'position': position} for node, position in ANCHORS.items()]
    data['nodes'].append({'id': 'auv_04', 'position': [-500, 200, -100]})
    data['flows'] = []
    data['network']['acoustic']['tx_power_db'] = 132
    data['network']['routing'] = 'position_based'
    data['network']['position_based'] = {'anchor_range_m': 450, 'vehicle_range_m': 450,
                                         'anchors': {node: {} for node in ANCHORS}, **position_based}
    data['network']['routes'] = {'auv_01': {'auv_03': 'auv_02', 'auv_04': 'auv_02'},
                                 'auv_02': {'auv_04': 'auv_03'}, 'auv_03': {'auv_01': 'auv_02'}}
    return Scenario.model_validate(data)


class Run:
    def __init__(self, scenario):
        self.backend = DESERTAdapter(manage_docker=False)
        self.backend.start(scenario)
        self.ids = scenario.node_map
        # The native estimator starts at timestamp 0 and accepts only newer headers: one stamped
        # t = 0 would leave the anchors' estimate at the origin.
        self.backend.advance(1)

    def place(self, x):
        for node, position in ANCHORS.items():
            self.backend.update_node_position(node, Pose(*position), self.backend.time)
        self.backend.update_node_position('auv_04', Pose(x, 200, -100), self.backend.time)

    def send(self, source, destination, seconds=10):
        message = Message(source, destination, b'position-based', self.backend.time)
        self.backend.send(message)
        events = self.backend.advance(self.backend.time + seconds)
        delivered = any(e['event'] == 'rx' and Message.decode(bytes.fromhex(e['wire_hex'])).id == message.id for e in events)
        forwards = [(e['node'], e['next_hop_address']) for e in events if e['event'] == 'forward']
        return delivered, forwards


def test_vehicle_and_anchors_route_by_position_as_the_vehicle_moves(engine):
    run = Run(scenario())
    try:
        uplink, downlink = {}, {}
        # The vehicle reports its own fix in each uplink header; anchors only estimate it from those.
        for x in (-500, -225, 275, 500):
            run.place(x)
            delivered, forwards = run.send('auv_04', 'auv_01')
            assert delivered, (x, forwards)
            uplink[x] = forwards[0]
            delivered, forwards = run.send('auv_01', 'auv_04')
            assert delivered, (x, forwards)
            downlink[x] = forwards
        # Uplink first hop: the anchor closest to the vehicle's own position.
        assert {x: hop for x, (node, hop) in uplink.items()} == {-500: 1, -225: 2, 275: 3, 500: 3}
        # Downlink: direct while the estimate is within 450 m of auv_01, then along the anchors' tables.
        assert downlink[-500] == [(1, 4)]
        assert downlink[500] == [(1, 2), (2, 3), (3, 4)]
    finally:
        run.backend.stop()


def test_vehicle_beyond_every_anchor_range_drops_natively(engine):
    run = Run(scenario(vehicle_range_m=100))
    try:
        run.place(-500)
        delivered, forwards = run.send('auv_04', 'auv_01')
        assert not delivered and forwards == []     # native no-next-hop drop before the MAC
    finally:
        run.backend.stop()


def test_bindings_report_ranges_and_roles(engine):
    run = Run(scenario())
    try:
        records = [e for e in run.backend.initial_events if e['event'] == 'native_bindings' and e['module'] == 'routing']
        classes = {r['node']: r['class'] for r in records}
        assert classes == {1: 'Module/UW/PosBasedRt', 2: 'Module/UW/PosBasedRt', 3: 'Module/UW/PosBasedRt', 4: 'Module/UW/PosBasedRt/ROV'}
        assert all(r['values']['maxTxRange_'] == 450 for r in records)
    finally:
        run.backend.stop()
