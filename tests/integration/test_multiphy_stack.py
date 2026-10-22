import pytest
from holo_desert.common.models import Message, Pose
from holo_desert.desert_adapter.backend import DESERTAdapter
from holo_desert.scenarios.config import ScenarioManager, Scenario

pytestmark=pytest.mark.desert


def scenario(policy='manual'):
    data=ScenarioManager().load('e01_chat').model_dump()
    data['network']['multiphy']={'interfaces':[
        {'id':'long','acoustic':{'frequency_hz':25000,'bandwidth_hz':5000,'bitrate_bps':4800,'tx_power_db':150}},
        {'id':'short','acoustic':{'frequency_hz':50000,'bandwidth_hz':9000,'bitrate_bps':8800,'tx_power_db':150}}],
        'initial_interface':'long','policy':policy}
    if policy=='received_power':data['network']['multiphy']['thresholds']=[
        {'from_interface':'long','to_interface':'short','power_linear':1},
        {'from_interface':'short','to_interface':'long','power_linear':1e-6}]
    return Scenario.model_validate(data)


def test_native_multiphysical_manual_switch_delivers_and_reports_interface(engine):
    backend=DESERTAdapter(manage_docker=False)
    try:
        backend.start(scenario())
        for i,node in enumerate(('auv_01','auv_02')):backend.update_node_position(node,Pose(i*30,0,-20),0)
        for index,interface,bitrate in [(1,'long',4800),(2,'short',8800)]:
            backend.set_interface('auv_01',interface)
            message=Message('auv_01','auv_02',b'native-interface',backend.time)
            backend.send(message);events=backend.advance(backend.time+5)
            assert any(e['event']=='rx' and Message.decode(bytes.fromhex(e['wire_hex'])).id==message.id for e in events)
            tx=next(e for e in events if e['event']=='phy_tx_start')
            assert tx['interface_index']==index
            assert tx['duration_s']==pytest.approx(tx['phy_bits']/bitrate)
    finally:backend.stop()


def test_native_received_power_controller_switches_after_peer_packet(engine):
    backend=DESERTAdapter(manage_docker=False)
    try:
        backend.start(scenario('received_power'))
        for i,node in enumerate(('auv_01','auv_02')):backend.update_node_position(node,Pose(i*30,0,-20),0)
        backend.send(Message('auv_02','auv_01',b'observed-power',0));first=backend.advance(5)
        assert any(e['event']=='rx' for e in first)
        backend.send(Message('auv_01','auv_02',b'controller-selected',5));events=backend.advance(10)
        tx=next(e for e in events if e['event']=='phy_tx_start')
        assert tx['interface_index']==2
        assert any(e['event']=='rx' for e in events)
    finally:backend.stop()


def test_native_power_command_changes_only_the_first_interface(engine):
    backend=DESERTAdapter(manage_docker=False)
    try:
        backend.start(scenario())
        for i,node in enumerate(('auv_01','auv_02')):backend.update_node_position(node,Pose(i*30,0,-20),0)
        backend.set_power('auv_01',0)
        delivered={}
        for interface in ('short','long'):
            backend.set_interface('auv_01',interface)
            message=Message('auv_01','auv_02',interface.encode(),backend.time)
            backend.send(message);events=backend.advance(backend.time+5)
            delivered[interface]=any(e['event']=='rx' and Message.decode(bytes.fromhex(e['wire_hex'])).id==message.id for e in events)
        # POWER sets the source level of the node's first interface ("long") only.
        assert delivered=={'short':True,'long':False}
    finally:backend.stop()
