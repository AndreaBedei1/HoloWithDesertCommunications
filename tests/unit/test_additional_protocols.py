import pytest
from holo_desert.scenarios.config import Scenario, ScenarioManager
from holo_desert.resources.docker.stack_builder import render

@pytest.mark.parametrize('protocol,cls',[('csburst','CSBURST'),('tokenbus','TOKENBUS'),('ranging_tokenbus','RANGING_TOKENBUS')])
def test_additional_protocol_typed_render_and_unsupported_options(protocol,cls):
    data=ScenarioManager().load('e01_chat').model_dump()
    data['network']['mac']['protocol']=protocol
    model=Scenario.model_validate(data)
    text=render(model.model_dump())
    assert 'Module/UW/'+cls in text
    assert 'set mac_adapter '+protocol in text
    data['network']['mac']['ack']=True
    with pytest.raises(ValueError,match='ACK'):Scenario.model_validate(data)
    with pytest.raises(ValueError,match='ACK'):render(data)

@pytest.mark.parametrize('protocol,params',[('csburst',{'max_packets_per_burst':0}),('tokenbus',{'slot_time_s':0}),('ranging_tokenbus',{'min_token_hold_s':-1})])
def test_additional_protocol_rejects_invalid_parameters_at_both_boundaries(protocol,params):
    data=ScenarioManager().load('e01_chat').model_dump()
    data['network']['mac'].update(protocol=protocol,**{protocol:params})
    with pytest.raises(ValueError):Scenario.model_validate(data)
    with pytest.raises(ValueError):render(data)

@pytest.mark.parametrize('protocol',['csburst','tokenbus','ranging_tokenbus'])
def test_additional_protocol_only_verified_routing(protocol):
    data=ScenarioManager().load('e01_chat').model_dump()
    data['network']['mac']['protocol']=protocol
    data['network']['routing']='flooding'
    with pytest.raises(ValueError,match='Static'):Scenario.model_validate(data)
    with pytest.raises(ValueError,match='Static'):render(data)


@pytest.mark.parametrize('protocol', ['tokenbus', 'ranging_tokenbus'])
def test_token_holding_time_must_fit_serialized_flow(protocol):
    data = ScenarioManager().load('e01_chat').model_dump()
    data['network']['mac'].update(protocol=protocol, **{protocol: {'max_token_hold_s': .1}})
    with pytest.raises(ValueError, match='token holding'):
        Scenario.model_validate(data)
    with pytest.raises(ValueError, match='token holding'):
        render(data)


def test_token_startup_timeout_must_cover_serialized_flow():
    data = ScenarioManager().load('e01_chat').model_dump()
    data['network']['mac'].update(protocol='tokenbus', tokenbus={'slot_time_s': .1})
    data['flows'][0]['payload_bytes'] = 512
    with pytest.raises(ValueError, match='startup'):
        Scenario.model_validate(data)
    with pytest.raises(ValueError, match='startup'):
        render(data)


def test_token_rejects_zero_bitrate_before_computing_airtime():
    data = ScenarioManager().load('e01_chat').model_dump()
    data['network']['mac']['protocol'] = 'tokenbus'
    data['network']['acoustic']['bitrate_bps'] = 0
    with pytest.raises(ValueError):
        render(data)


def test_sun_roles_render_and_convergecast_validation():
    data = ScenarioManager().load('e01_chat').model_dump()
    data['network'].update(routing='sun', sun={'sink': 'auv_02'})
    data['network']['mac']['protocol'] = 'csma_aloha'
    data['flows'] = [f for f in data['flows'] if f['destination'] == 'auv_02']
    for flow in data['flows']:
        flow['reply'] = False
    model = Scenario.model_validate(data)
    text = render(model.model_dump())
    assert 'set routing_adapter sun' in text
    assert 'sink 2' in text
    for patch, match in [({'sink': 'auv_99'}, 'sink'), ({'max_ack_errors': 0}, 'greater|bounds')]:
        invalid = dict(data, network=dict(data['network'], sun=dict(data['network']['sun'], **patch)))
        with pytest.raises(ValueError, match=match):
            Scenario.model_validate(invalid)
        with pytest.raises(ValueError):
            render(invalid)
    data['flows'][0]['destination'] = 'auv_01'
    with pytest.raises(ValueError):
        Scenario.model_validate(data)
    with pytest.raises(ValueError, match='sink'):
        render(data)
