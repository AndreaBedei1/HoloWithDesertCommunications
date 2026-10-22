import pytest
from holo_desert.scenarios.config import ScenarioManager, Scenario
from holo_desert.resources.docker.stack_builder import render


def test_woss_environment_reaches_native_stack_and_preserves_default():
    data=ScenarioManager().load('e01_chat').model_dump()
    assert 'set environment_adapter underwater' in render(data)
    data['network']['acoustic']['propagation']='woss'
    scenario=Scenario.model_validate(data)
    text=render(scenario.model_dump())
    assert 'set environment_adapter woss' in text
    assert 'WOSS/Module/MPhy/BPSK/HOLO' in text
    assert 'set woss_parameters {' in text
    assert '1500' in text


@pytest.mark.parametrize('change',[
    {'origin_latitude_deg':91}, {'water_depth_m':-1},
    {'ssp':[{'depth_m':0,'speed_mps':1500},{'depth_m':0,'speed_mps':1490}]},
    {'ssp':[{'depth_m':0,'speed_mps':1500},{'depth_m':10,'speed_mps':1490}]},
    {'ssp_path':'/etc/passwd'},
])
def test_invalid_woss_rejected_at_typed_and_socket_boundaries(change):
    data=ScenarioManager().load('e01_chat').model_dump()
    data['network']['acoustic']['propagation']='woss'
    data['network']['woss']=change
    with pytest.raises(ValueError):Scenario.model_validate(data)
    with pytest.raises(ValueError):render(data)


@pytest.mark.parametrize('position',[(0,0,0),(0,0,-100),(0,0,-.01),(100001,0,-20)])
def test_woss_rejects_out_of_water_or_remote_positions(position):
    data=ScenarioManager().load('e01_chat').model_dump()
    data['network']['acoustic']['propagation']='woss'
    data['nodes'][0]['position']=position
    with pytest.raises(ValueError,match='WOSS'):Scenario.model_validate(data)
    with pytest.raises(ValueError,match='WOSS'):render(data)


def test_woss_rejects_corrected_phy():
    data=ScenarioManager().load('e01_chat').model_dump()
    data['network']['acoustic'].update(propagation='woss',phy='bpsk_corrected')
    with pytest.raises(ValueError,match='WOSS'):Scenario.model_validate(data)


def test_woss_rejects_vertical_links_before_native_bellhop_assertion():
    data=ScenarioManager().load('e01_chat').model_dump()
    data['network']['acoustic']['propagation']='woss'
    data['nodes'][1]['position']=[*data['nodes'][0]['position'][:2],-40]
    with pytest.raises(ValueError,match='horizontal'):Scenario.model_validate(data)
