import pytest
from holo_desert.scenarios.config import Scenario, ScenarioManager, RESOURCE_ROOT
from holo_desert.core.orchestrator import SimulationOrchestrator

pytestmark=[pytest.mark.desert,pytest.mark.holoocean]


@pytest.mark.parametrize('feature',['csburst','tokenbus','ranging_tokenbus','sun','woss','desert_cbr','desert_vbr','optical','em'])
def test_real_physics_completed_laboratory_paths(engine,feature):
    data=ScenarioManager().load('e01_chat').model_dump()
    data.update(duration=24,realtime=False)
    data['flows']=data['flows'][:1]
    data['flows'][0].update(start=5,stop=13,interval=5,reply=False,message_type='data',ttl=30)
    if feature in ('csburst','tokenbus','ranging_tokenbus'):data['network']['mac']['protocol']=feature
    elif feature=='sun':data['network']['routing']='sun'
    elif feature=='woss':
        data=ScenarioManager().load(str(RESOURCE_ROOT/'demos/e08_woss/scenario.yaml')).model_dump()
    elif feature in ('desert_cbr','desert_vbr'):data['flows'][0]['generator']=feature
    else:
        data['network']['medium']=feature
        # Default 868 MHz EM decodes only up to about 2 m in fresh water in the
        # native model (3 m gives ~5e-15 mW, below the LUT); optical uses 3 m.
        data['nodes'][1]['position']=[2 if feature=='em' else 3,0,-10]
        data['nodes'][0]['position']=[0,0,-10]
        if feature=='em':data['network']['em']['salinity_ppt']=0
    run=SimulationOrchestrator(Scenario.model_validate(data),manage_docker=False,show_viewport=False)
    try:
        run.run();state=run.snapshot()
        assert run.state=='finished',run.error
        assert state['counts']['generated']>=1
        assert state['counts']['received']>=1,(feature,state['counts'])
        assert len(state['fleet'])==2
        assert any(e['event']=='rx' for e in state['observations'])
        if feature not in ('optical','em'):
            # Optical/EM PHYs expose no per-reception outcome; none is invented.
            assert any(e['event']=='phy_rx_end' and e.get('outcome')=='decoded' for e in state['observations'])
        assert run.clock.time==pytest.approx(data['duration'])
        print(feature,state['counts'])
    finally:run.close()
