"""Real optical/EM PHY, propagation, antenna/LUT and scheduler integration."""
import pytest
from holo_desert.common.models import Message, Pose
from holo_desert.desert_adapter.backend import DESERTAdapter
from holo_desert.scenarios.config import ScenarioManager, Scenario

pytestmark=pytest.mark.desert


def run_medium(medium,settings,distance=1,receiver_yaw=0):
    data=ScenarioManager().load('e01_chat').model_dump()
    data['network']['medium']=medium
    data['network'][medium].update(settings)
    for i,node in enumerate(data['nodes']):node['position']=[i*distance,0,-10]
    backend=DESERTAdapter(manage_docker=False)
    try:
        backend.start(Scenario.model_validate(data))
        for i,node in enumerate(data['nodes']):backend.update_node_position(node['id'],Pose(i*distance,0,-10,receiver_yaw if i else 0),0)
        message=Message('auv_01','auv_02',b'native-medium',0)
        backend.send(message)
        events=backend.advance(2)
        assert any(e['event']=='phy_tx_start' and e['medium']==medium for e in events)
        assert any(e['event']=='position_applied' and e['time']==0 for e in events)
        return any(e['event']=='rx' and Message.decode(bytes.fromhex(e['wire_hex'])).id==message.id for e in events),events
    finally:backend.stop()


def test_optical_native_power_attenuation_distance_and_restart(engine):
    good,events=run_medium('optical',{})
    assert good
    assert next(e for e in events if e['event']=='phy_tx_start')['power_unit']=='W'
    assert not run_medium('optical',{'tx_power_w':1e-15},50)[0]
    assert not run_medium('optical',{'attenuation_per_m':100},10)[0]
    assert run_medium('optical',{})[0]


def test_em_native_salinity_antenna_lut_and_restart(engine):
    good,events=run_medium('em',{})
    assert good
    assert next(e for e in events if e['event']=='phy_tx_start')['phy_patch_id']=='em-power-lut-v1'
    assert not run_medium('em',{'salinity_ppt':35})[0]
    assert not run_medium('em',{'antenna_gain_db':-50})[0]
    assert not run_medium('em',{},100)[0]
    assert run_medium('em',{})[0]


def test_optical_native_body_orientation_and_mount_alignment(engine):
    data=ScenarioManager().load('e01_chat').model_dump()
    data['network'].update(medium='optical')
    data['network']['optical']['directional']=True
    for i,node in enumerate(data['nodes']):node['position']=[i*10,0,-10]
    backend=DESERTAdapter(manage_docker=False)
    try:
        backend.start(Scenario.model_validate(data))
        backend.update_node_position('auv_01',Pose(0,0,-10),0)
        backend.update_node_position('auv_02',Pose(10,0,-10),0)
        backend.send(Message('auv_01','auv_02',b'aligned',0))
        assert any(e['event']=='rx' for e in backend.advance(2))
        backend.update_node_position('auv_01',Pose(0,0,-10,180),2)
        backend.send(Message('auv_01','auv_02',b'yaw-away',2))
        assert not any(e['event']=='rx' for e in backend.advance(4))
        backend.update_node_position('auv_01',Pose(0,0,-10,0,180),4)
        backend.send(Message('auv_01','auv_02',b'pitch-away',4))
        assert not any(e['event']=='rx' for e in backend.advance(6))
        backend.update_node_position('auv_01',Pose(0,0,-10),6)
        backend.update_node_position('auv_02',Pose(-10,0,-10),6)
        backend.send(Message('auv_01','auv_02',b'moved-behind',6))
        assert not any(e['event']=='rx' for e in backend.advance(8))
    finally:backend.stop()
    assert not run_medium('optical',{'directional':True,'mount_yaw_deg':180},10)[0]


def test_optical_native_rotated_body_offset_changes_received_gain(engine):
    _,baseline=run_medium('optical',{},10,180)
    _,offset=run_medium('optical',{'offset_x_m':2},10,180)
    power=lambda events:next(e['pr'] for e in events if e['event']=='phy_rx_start')
    assert power(offset)>power(baseline)


@pytest.mark.parametrize('medium,power,key',[('optical',1e-15,'tx_power_w'),('em',-100,'tx_power_dbm')])
def test_native_medium_power_command_preserves_units(engine,medium,power,key):
    data=ScenarioManager().load('e01_chat').model_dump()
    data['network']['medium']=medium
    for i,node in enumerate(data['nodes']):node['position']=[i,0,-10]
    backend=DESERTAdapter(manage_docker=False)
    try:
        backend.start(Scenario.model_validate(data))
        for i,node in enumerate(data['nodes']):backend.update_node_position(node['id'],Pose(i,0,-10),0)
        backend.set_power('auv_01',power)
        backend.send(Message('auv_01','auv_02',b'power-units',0))
        events=backend.advance(2)
        assert next(e for e in events if e['event']=='power_applied')[key]==power
        assert not any(e['event']=='rx' for e in events)
        with pytest.raises(ValueError):backend.set_power('auv_01',-101)
    finally:backend.stop()
