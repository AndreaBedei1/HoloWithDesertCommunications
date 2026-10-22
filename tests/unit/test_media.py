import pytest
from holo_desert.scenarios.config import ScenarioManager, Scenario
from holo_desert.resources.docker.stack_builder import render


@pytest.mark.parametrize('medium,unit', [('optical','tx_power_w'),('em','tx_power_dbm')])
def test_native_medium_configuration_reaches_tcl(medium,unit):
    data=ScenarioManager().load('e01_chat').model_dump()
    data['network']['medium']=medium
    scenario=Scenario.model_validate(data)
    text=render(scenario.model_dump())
    assert 'set environment_adapter '+medium in text
    assert unit in text


@pytest.mark.parametrize('medium,settings', [('optical',{'tx_power_w':-1}),('optical',{'noise_lut':'/etc/passwd'}),('em',{'salinity_ppt':-1}),('em',{'per_lut':'untrusted'})])
def test_media_reject_invalid_values_at_both_boundaries(medium,settings):
    data=ScenarioManager().load('e01_chat').model_dump()
    data['network'].update(medium=medium)
    data['network'][medium]=settings
    with pytest.raises(ValueError):Scenario.model_validate(data)
    with pytest.raises(ValueError):render(data)


def test_nonacoustic_rejects_acoustic_overrides_and_unverified_mac():
    data=ScenarioManager().load('e01_chat').model_dump()
    data['network']['medium']='optical'
    data['nodes'][0]['communication']={'acoustic':{'tx_power_db':150}}
    with pytest.raises(ValueError,match='override'):render(data)
    data['nodes'][0]['communication']={}
    data['network']['mac']['protocol']='dacap'
    with pytest.raises(ValueError,match='medium'):Scenario.model_validate(data)


def test_optical_directional_is_explicit_and_boolean():
    data=ScenarioManager().load('e01_chat').model_dump()
    data['network'].update(medium='optical',optical={'directional':True})
    assert 'directional 1' in render(Scenario.model_validate(data).model_dump())
    data['network']['optical']['directional']='yes'
    with pytest.raises(ValueError):render(data)


def test_optical_rejects_depth_beyond_pinned_noise_measurements():
    data=ScenarioManager().load('e01_chat').model_dump()
    data['network']['medium']='optical'
    data['nodes'][0]['position']=[0,0,-21]
    with pytest.raises(ValueError,match='noise LUT'):render(data)
