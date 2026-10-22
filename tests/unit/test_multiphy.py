import pytest
from holo_desert.scenarios.config import Scenario, ScenarioManager
from holo_desert.resources.docker.stack_builder import render


def multiphy_data():
    data=ScenarioManager().load('e01_chat').model_dump()
    data['network']['multiphy']={'interfaces':[
        {'id':'long','acoustic':{'frequency_hz':25000,'bandwidth_hz':5000,'bitrate_bps':4800}},
        {'id':'short','acoustic':{'frequency_hz':50000,'bandwidth_hz':9000,'bitrate_bps':8800}}],
        'initial_interface':'long'}
    return data


def test_multiphy_typed_and_raw_render_native_controller():
    data=multiphy_data()
    text=render(Scenario.model_validate(data).model_dump())
    assert 'set multiphy_enabled 1' in text
    assert 'libuwmulti_stack_controller.so' in text
    assert 'set multi_interface_ids {long short}' in text
    assert 'bitrate_bps 8800' in text


@pytest.mark.parametrize('change',[
    {'initial_interface':'unknown'}, {'policy':'fake'},
    {'interfaces':[{'id':'bad;exit'}]},
    {'thresholds':[{'from_interface':'long','to_interface':'short','power_linear':float('nan')}]},
])
def test_multiphy_invalid_inputs_rejected(change):
    data=multiphy_data();data['network']['multiphy'].update(change)
    with pytest.raises(ValueError):Scenario.model_validate(data)
    with pytest.raises(ValueError):render(data)


def test_multiphy_node_subset_and_interface_override():
    data=multiphy_data()
    data['nodes'][1]['communication']={'interfaces':['long'],'interface_overrides':{'long':{'tx_power_db':145}}}
    text=render(Scenario.model_validate(data).model_dump())
    assert 'set multi_indices(2) {1}' in text
    assert 'set multi_settings(2,1) {tx_power_db 145' in text
