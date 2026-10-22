import pytest
from holo_desert.scenarios.config import Scenario, ScenarioManager, RESOURCE_ROOT
from holo_desert.core.orchestrator import SimulationOrchestrator

pytestmark=[pytest.mark.desert,pytest.mark.holoocean]


@pytest.mark.parametrize('feature',['csburst','tokenbus','ranging_tokenbus','ranging_tdma','sun','woss','desert_cbr','desert_vbr','optical','em'])
def test_real_physics_completed_laboratory_paths(engine,feature):
    data=ScenarioManager().load('e01_chat').model_dump()
    data.update(duration=24,realtime=False)
    data['flows']=data['flows'][:1]
    data['flows'][0].update(start=5,stop=13,interval=5,reply=False,message_type='data',ttl=30)
    if feature in ('csburst','tokenbus','ranging_tokenbus','ranging_tdma'):data['network']['mac']['protocol']=feature
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
        if feature in ('desert_cbr','desert_vbr'):
            # Native receptions are reported as native_app_rx on the packet row; the Python 'rx' path is unused.
            assert any(p['id'].startswith('native:') and p['status']=='received' for p in state['packets'])
        else:
            assert any(e['event']=='rx' for e in state['observations'])
        if feature not in ('optical','em'):
            # Optical/EM PHYs expose no per-reception outcome; none is invented.
            assert any(e['event']=='phy_rx_end' and e.get('outcome')=='decoded' for e in state['observations'])
        assert run.clock.time==pytest.approx(data['duration'])
        print(feature,state['counts'])
    finally:run.close()


@pytest.mark.parametrize('protocol',['ranging_tokenbus','ranging_tdma'])
def test_ranging_estimates_reach_the_dashboard_beside_holoocean_geometry(engine,protocol):
    from fastapi.testclient import TestClient
    from holo_desert import ManagedSimulation
    from holo_desert.dashboard.server import DashboardServer
    data=ScenarioManager().load('e01_chat').model_dump()
    data.update(duration=60,realtime=False,flows=[])
    data['network']['mac']['protocol']=protocol
    data['nodes']=[dict(data['nodes'][0],id='auv_01',position=[0,0,-20]),dict(data['nodes'][0],id='auv_02',position=[40,0,-20]),
                   dict(data['nodes'][0],id='auv_03',position=[0,30,-20])]
    run=ManagedSimulation(Scenario.model_validate(data),manage_engine=False)
    try:
        run.run()
        with TestClient(DashboardServer(initial_run=run,manage_docker=False).application()) as client:
            ranging=client.get('/api/state').json()['ranging']
        latest=[r for r in ranging['latest'] if r['valid']]
        assert {r['pair'] for r in latest}=={'auv_01>auv_02','auv_01>auv_03','auv_02>auv_03'}
        # Native estimates (travel time x sound speed) against the HoloOcean geometry of the hovering vehicles.
        assert all(abs(r['error_m'])<1 and r['protocol']==protocol for r in latest),latest
        assert all(len(points)>=10 for points in ranging['series'].values())
    finally:run.close()
