"""Real Bellhop channel, geographic placement and movement through the bridge."""
import pytest
from holo_desert.common.models import Message, Pose
from holo_desert.desert_adapter.backend import DESERTAdapter, BackendError
from holo_desert.scenarios.config import ScenarioManager, Scenario

pytestmark=pytest.mark.desert


def test_woss_native_delivery_georeference_and_movement(engine):
    data=ScenarioManager().load('e01_chat').model_dump()
    data['network']['acoustic'].update(propagation='woss',tx_power_db=150)
    data['network']['woss']['x_bearing_deg']=0
    backend=DESERTAdapter(manage_docker=False)
    try:
        backend.start(Scenario.model_validate(data))
        for i,node in enumerate(data['nodes']):backend.update_node_position(node['id'],Pose(i*100,0,-20),0)
        message=Message('auv_01','auv_02',b'Bellhop-native',0)
        backend.send(message)
        events=backend.advance(5)
        assert any(e['event']=='rx' and Message.decode(bytes.fromhex(e['wire_hex'])).id==message.id for e in events)
        positions=[e for e in events if e['event']=='position_applied']
        assert positions[-1]['latitude_deg']>positions[0]['latitude_deg']
        assert positions[-1]['longitude_deg']==pytest.approx(positions[0]['longitude_deg'])
        first=next(e for e in events if e['event']=='phy_rx_end')
        backend.update_node_position('auv_02',Pose(500,0,-60),5)
        backend.send(Message('auv_01','auv_02',b'Bellhop-native',5))
        moved=backend.advance(10)
        second=next(e for e in moved if e['event']=='phy_rx_end')
        assert second['pr']!=pytest.approx(first['pr'])
        assert second['phy_rx_time']-second['phy_tx_time']>first['phy_rx_time']-first['phy_tx_time']
        assert second['phy_patch_id']=='woss-native-bpsk'
        with pytest.raises(ValueError,match='WOSS'):backend.update_node_position('auv_02',Pose(0,0,0),10)
        backend.update_node_position('auv_02',Pose(0,0,-50),10)
        with pytest.raises(ValueError,match='horizontal'):backend.advance(11)
        backend.update_node_position('auv_02',Pose(500,0,-50),10)
        backend.advance(11)
        assert backend.time==11
    finally:backend.stop()


def test_woss_nonuniform_ssp_changes_native_channel_and_restart(engine):
    results=[]
    for speed in (1500,1450):
        data=ScenarioManager().load('e01_chat').model_dump()
        data['network']['acoustic'].update(propagation='woss',tx_power_db=150)
        data['network']['woss']['ssp']=[{'depth_m':0,'speed_mps':1500},{'depth_m':50,'speed_mps':speed},{'depth_m':100,'speed_mps':1500}]
        backend=DESERTAdapter(manage_docker=False)
        try:
            backend.start(Scenario.model_validate(data))
            for i,node in enumerate(data['nodes']):backend.update_node_position(node['id'],Pose(0,i*500,-20-i*30),0)
            backend.send(Message('auv_01','auv_02',b'Bellhop-SSP',0))
            events=backend.advance(5)
            p=next(e for e in events if e['event']=='position_applied' and e['node']==2)
            assert p['latitude_deg']>42.59 # +Y is north when +X points east.
            assert p['longitude_deg']==pytest.approx(10.125)
            results.append(next(e for e in events if e['event']=='phy_rx_end'))
        finally:backend.stop()
    assert results[0]['pr']!=pytest.approx(results[1]['pr'])
    delay=lambda e:e['phy_rx_time']-e['phy_tx_time']
    assert delay(results[0])!=pytest.approx(delay(results[1]))


def test_woss_raw_socket_geometry_guard_avoids_native_abort(engine):
    data=ScenarioManager().load('e01_chat').model_dump()
    data['network']['acoustic']['propagation']='woss'
    backend=DESERTAdapter(manage_docker=False)
    try:
        backend.start(Scenario.model_validate(data))
        backend.update_node_position('auv_01',Pose(0,0,-20),0)
        backend.update_node_position('auv_02',Pose(100,0,-50),0)
        # Bypass host validation to exercise the native transport trust boundary.
        backend._command('POSITION 2 0 0 -50 0')
        backend.send(Message('auv_01','auv_02',b'invalid-vertical-link',0))
        with pytest.raises(BackendError,match='invalid bridge command'):backend.advance(1)
    finally:backend.stop()


@pytest.mark.parametrize('x,z',[(1,-20),(50,-.11),(50,-99.89)])
def test_woss_supported_geometry_edges_native(engine,x,z):
    data=ScenarioManager().load('e01_chat').model_dump()
    data['network']['acoustic'].update(propagation='woss',tx_power_db=150)
    backend=DESERTAdapter(manage_docker=False)
    try:
        backend.start(Scenario.model_validate(data))
        backend.update_node_position('auv_01',Pose(0,0,-20),0)
        backend.update_node_position('auv_02',Pose(x,0,z),0)
        message=Message('auv_01','auv_02',b'geometry-edge',0)
        backend.send(message)
        assert any(e['event']=='rx' and Message.decode(bytes.fromhex(e['wire_hex'])).id==message.id for e in backend.advance(3))
    finally:backend.stop()
