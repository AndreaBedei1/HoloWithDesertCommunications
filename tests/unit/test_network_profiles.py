from fastapi.testclient import TestClient
from holo_desert.dashboard.server import DashboardServer
from holo_desert.scenarios.config import ScenarioManager
from holo_desert.scenarios.network import CommunicationProfile
import pytest


def test_profile_rejects_unsupported_tdma_ack_and_negative_slot():
    data={'name':'Invalid','network':ScenarioManager().load('e01_chat').network.model_dump()}
    data['network']['mac']['protocol']='tdma';data['network']['mac']['ack']=True
    with pytest.raises(ValueError):CommunicationProfile.model_validate(data)
    data['network']['mac']['ack']=False;data['network']['mac']['tdma']['slot_assignment']={'auv_01':-1}
    with pytest.raises(ValueError):CommunicationProfile.model_validate(data)


def test_profiles_persist_revision_export_and_do_not_modify_examples(tmp_path):
    server=DashboardServer(manage_docker=False,scenario_directory=tmp_path)
    network=ScenarioManager().load('e01_chat').network.model_dump()
    with TestClient(server.application()) as client:
        catalog=client.get('/api/network-catalog');assert catalog.status_code==200
        assert any(m['id']=='tdma' for m in catalog.json()['modules'])
        response=client.post('/api/network-profiles',json={'name':'Il mio TDMA','description':'Test','network':network})
        assert response.status_code==200
        profile=response.json();identifier=profile['id']
        payload={'name':'Rete rinominata','description':'Test','network':network,'revision':profile['revision']}
        assert client.put('/api/network-profiles/'+identifier,json=payload).status_code==200
        assert client.put('/api/network-profiles/'+identifier,json=payload).status_code==409
        yaml=client.get('/api/network-profiles/'+identifier+'/yaml');assert yaml.status_code==200
        draft=client.post('/api/network-profiles/import',json={'yaml':yaml.text}).json()
        assert draft['network']==network
        assert client.delete('/api/network-profiles/../README.md?revision=x').status_code!=200
    with TestClient(DashboardServer(manage_docker=False,scenario_directory=tmp_path).application()) as client:
        saved=client.get('/api/network-profiles').json()['personal'];assert len(saved)==1
        assert client.delete('/api/network-profiles/'+identifier+'?revision='+saved[0]['revision']).status_code==200
        assert len(client.get('/api/scenarios').json())==9


def test_builtins_are_renderable_and_provenance_is_not_tcl():
    from holo_desert.scenarios.profiles import builtin_profiles
    from holo_desert.resources.docker.stack_builder import render
    from holo_desert.scenarios.config import Scenario
    for profile in builtin_profiles():
        data=ScenarioManager().load('e01_chat').model_dump()
        data['network']={**profile['network'],'profile_id':profile['id']}
        scenario=Scenario.model_validate(data)
        assert profile['id'] not in render(scenario.model_dump())
        assert scenario.network.profile_id==profile['id']
    data['network']['profile_id']='evil; exec calc'
    with pytest.raises(ValueError):Scenario.model_validate(data)
