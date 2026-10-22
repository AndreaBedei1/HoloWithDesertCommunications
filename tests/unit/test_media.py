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


def power_scenario(medium,**event):
    data=ScenarioManager().load('e01_chat').model_dump()
    data['network']['medium']=medium
    data['power_events']=[{'time':5,'node':'auv_01',**event}]
    return data


@pytest.mark.parametrize('medium,event,value',[('em',{'tx_power_dbm':-20},-20),('optical',{'tx_power_w':1e-9},1e-9),('acoustic',{'tx_power_db':0},0)])
def test_power_event_value_is_in_the_medium_unit(medium,event,value):
    assert Scenario.model_validate(power_scenario(medium,**event)).power_events[0].value==value


@pytest.mark.parametrize('medium,event',[('em',{'tx_power_db':14}),('acoustic',{'tx_power_dbm':-20}),('optical',{'tx_power_dbm':10}),('em',{'tx_power_w':1})])
def test_power_event_unit_must_match_the_medium(medium,event):
    with pytest.raises(ValueError,match='power event'):Scenario.model_validate(power_scenario(medium,**event))


@pytest.mark.parametrize('event',[{},{'tx_power_dbm':10,'tx_power_w':1},{'tx_power_dbm':-101},{'tx_power_dbm':101},{'tx_power_w':0}])
def test_power_event_needs_exactly_one_value_within_native_bounds(event):
    medium='optical' if 'tx_power_w' in event and len(event)==1 else 'em'
    with pytest.raises(ValueError):Scenario.model_validate(power_scenario(medium,**event))


def test_orchestrator_applies_power_events_in_the_medium_unit():
    from holo_desert.common.models import Pose
    from holo_desert.core.orchestrator import SimulationOrchestrator
    data=power_scenario('em',tx_power_dbm=-20)
    data.update(duration=6,realtime=False,flows=[])
    scenario=Scenario.model_validate(data)
    applied=[]
    class Backend:
        time=0.0;versions={};pause_supported=True;initial_events=[]
        def start(self,scenario):pass
        def update_node_position(self,*args):pass
        def set_power(self,node,value,interface=None):applied.append((node,value))
        def request_stats(self):pass
        def advance(self,target):
            self.time=target
            return [dict(event='position_applied',time=target,node=n) for n in (1,2)]
        def stop(self):pass
    class Physics:
        def start(self):return {n.id:Pose(*n.position) for n in scenario.nodes}
        tick=start
        def stop(self):pass
    run=SimulationOrchestrator(scenario,backend=Backend(),physics=Physics(),standalone=True)
    try:
        run.run()
        assert run.error is None
        assert applied==[('auv_01',-20)]
    finally:run.close()


def test_optical_rejects_depth_beyond_pinned_noise_measurements():
    data=ScenarioManager().load('e01_chat').model_dump()
    data['network']['medium']='optical'
    data['nodes'][0]['position']=[0,0,-21]
    with pytest.raises(ValueError,match='noise LUT'):render(data)
