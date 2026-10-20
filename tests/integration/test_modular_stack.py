import pytest
from holo_desert.common.models import Message, Pose
from holo_desert.desert_adapter.backend import DESERTAdapter
from holo_desert.scenarios.config import ScenarioManager, Scenario

pytestmark=pytest.mark.desert


@pytest.mark.parametrize('protocol',['tdma','tdma_frame','csma_ca','dacap'])
def test_new_mac_native_delivery_restart_and_observed_access(engine,protocol):
    data=ScenarioManager().load('e01_chat').model_dump()
    data['network']['mac']['protocol']=protocol
    scenario=Scenario.model_validate(data)
    for cycle in range(2):
        backend=DESERTAdapter(manage_docker=False)
        try:
            backend.start(scenario)
            for index,node in enumerate(scenario.nodes):backend.update_node_position(node.id,Pose(index*30,0,-20),0)
            message=Message('auv_01','auv_02',b'new-native-stack',0)
            backend.send(message);backend.request_stats();events=backend.advance(30)
            received=[e for e in events if e['event']=='rx' and Message.decode(bytes.fromhex(e['wire_hex'])).id==message.id]
            assert len(received)==1,(protocol,events)
            assert any(e['event']=='stats' and e.get('mac_queue') is not None for e in events)
            assert any(e['event']=='mac_specific_stats' and e['values'] for e in events)
            tx=[e for e in events if e['event']=='phy_tx_start']
            assert tx
            ends=[e for e in events if e['event']=='phy_tx_end']
            assert any(e['wire_hex']==tx[0]['wire_hex'] and e['time']==pytest.approx(tx[0]['time']+tx[0]['duration_s']) for e in ends)
            if protocol=='tdma':
                assert all(e['time']%3<1.4 for e in tx)
            if protocol in ('csma_ca','dacap'):
                assert any(e['event'].startswith('phy_control_') for e in events)
        finally:backend.stop()


def test_flooding_real_broadcast_forwarding_not_python_copies(engine):
    data=ScenarioManager().load('e05_multihop').model_dump()
    data['network']['routing']='flooding';data['network']['routes']={}
    data['network']['acoustic']['tx_power_db']=132
    data['network']['mac']['protocol']='tdma'
    data['network']['mac']['tdma']['frame_duration_s']=6
    data['flows']=[]
    scenario=Scenario.model_validate(data);backend=DESERTAdapter(manage_docker=False)
    try:
        backend.start(scenario)
        for index,node in enumerate(scenario.nodes):backend.update_node_position(node.id,Pose(index*500,0,-20),0)
        message=Message('auv_01','auv_03',b'actual flooding route',0,ttl=60)
        backend.send(message);events=backend.advance(40)
        received=[e for e in events if e['event']=='rx' and Message.decode(bytes.fromhex(e['wire_hex'])).id==message.id]
        assert any(e['node']==3 for e in received),events
        assert any(e['event']=='forward' and e['node']==2 for e in events)
    finally:backend.stop()


@pytest.mark.parametrize('protocol,offset',[('tdma',0),('tdma_frame',1)])
def test_slot_assignments_use_native_phase_and_both_nodes(engine,protocol,offset):
    scenario=ScenarioManager().load('e01_chat')
    scenario.network.mac.protocol=protocol
    scenario.network.mac.tdma.slot_assignment={'auv_01':1,'auv_02':0}
    backend=DESERTAdapter(manage_docker=False)
    try:
        backend.start(scenario)
        for i,n in enumerate(scenario.nodes):backend.update_node_position(n.id,Pose(i*30,0,-20),0)
        for src,dst in [('auv_01','auv_02'),('auv_02','auv_01')]:backend.send(Message(src,dst,b'slot-proof',0))
        tx=[e for e in backend.advance(12) if e['event']=='phy_tx_start']
        assert {e['node'] for e in tx}=={1,2}
        for e in tx:
            slot=1 if e['node']==1 else 0
            assert e['time']%3==pytest.approx(((slot+offset)%2)*1.5,abs=1e-6)
    finally:backend.stop()


def test_node_phy_overrides_change_actual_power_and_frame_duration(engine):
    data=ScenarioManager().load('e01_chat').model_dump()
    data['nodes'][0]['communication']={'acoustic':{'bitrate_bps':2400,'tx_power_db':132,'phy':'bpsk_corrected'}}
    backend=DESERTAdapter(manage_docker=False)
    try:
        backend.start(Scenario.model_validate(data))
        for i,n in enumerate(data['nodes']):backend.update_node_position(n['id'],Pose(i*30,0,-20),0)
        for t,src,dst,bitrate,power,patch in [(0,'auv_01','auv_02',2400,132,'conditional-bpsk-v1'),(5,'auv_02','auv_01',4800,135,'upstream')]:
            backend.send(Message(src,dst,b'instance-proof',t))
            tx=next(e for e in backend.advance(t+5) if e['event']=='phy_tx_start')
            assert tx['pt']==pytest.approx(10**(power/10),rel=1e-8)
            assert tx['duration_s']==pytest.approx(tx['phy_bits']/bitrate)
            assert tx['phy_patch_id']==patch
    finally:backend.stop()


@pytest.mark.parametrize('protocol',['aloha','csma_aloha','tdma','tdma_frame','csma_ca','dacap'])
@pytest.mark.parametrize('routing',['static','flooding'])
@pytest.mark.parametrize('phy',['bpsk_upstream','bpsk_corrected'])
def test_supported_stack_combinations_native(engine,protocol,routing,phy):
    data=ScenarioManager().load('e01_chat').model_dump()
    data['network']['mac']['protocol']=protocol
    data['network']['routing']=routing;data['network']['acoustic']['phy']=phy
    if routing=='flooding' and protocol in ('csma_ca','dacap'):
        with pytest.raises(ValueError,match='Flooding'):Scenario.model_validate(data)
        from holo_desert.resources.docker.stack_builder import render
        with pytest.raises(ValueError,match='Flooding'):render(data)
        return
    scenario=Scenario.model_validate(data);backend=DESERTAdapter(manage_docker=False)
    try:
        backend.start(scenario)
        for i,n in enumerate(scenario.nodes):backend.update_node_position(n.id,Pose(i*30,0,-20),0)
        for t,src,dst in [(0,'auv_01','auv_02'),(20,'auv_02','auv_01')]:
            message=Message(src,dst,b'compatibility-check',t,ttl=30)
            backend.send(message);events=backend.advance(t+20)
            assert any(e['event']=='rx' and Message.decode(bytes.fromhex(e['wire_hex'])).id==message.id for e in events)
    finally:backend.stop()
