"""Small real-physics checks, not a performance or multi-seed campaign."""
import json
import pytest
from holo_desert.core.orchestrator import SimulationOrchestrator
from holo_desert.scenarios.config import Scenario, ScenarioManager

pytestmark=[pytest.mark.desert,pytest.mark.holoocean]


@pytest.mark.parametrize('protocol,routing,phy',[
    ('tdma','static','bpsk_upstream'),
    ('tdma_frame','static','bpsk_upstream'),
    ('csma_ca','static','bpsk_upstream'),
    ('dacap','static','bpsk_upstream'),
    ('tdma','flooding','bpsk_upstream'),
    ('csma_aloha','static','bpsk_corrected')])
def test_real_holoocean_modular_stack(engine,protocol,routing,phy):
    data=ScenarioManager().load('e01_chat').model_dump()
    data.update(duration=24,realtime=False)
    data['network']['mac']['protocol']=protocol
    data['network']['routing']=routing
    data['network']['acoustic']['phy']=phy
    data['nodes'][0]['communication']={'acoustic':{'tx_power_db':132}}
    data['flows']=data['flows'][:1]
    data['flows'][0].update(start=1,stop=10,interval=6,ttl=30,reply=True)
    run=SimulationOrchestrator(Scenario.model_validate(data),manage_docker=False,show_viewport=False)
    try:
        run.run();state=run.snapshot()
        assert run.state=='finished',run.error
        assert state['counts']['received']>=2,state['counts']
        assert {p['type'] for p in state['packets'] if p['status']=='received'}>={'request','reply'}
        assert len(state['fleet'])==2
        assert run.clock.time==pytest.approx(24)
        events=[json.loads(line) for line in (run.telemetry.directory/'events.jsonl').read_text().splitlines()]
        info=next(e for e in events if e['event']=='engine_info')
        assert info['effective_nodes'][0]['acoustic']['tx_power_db']==132
        assert info['effective_nodes'][1]['acoustic']['tx_power_db']==135
        assert state['network_metrics']['data_tx_frames']>=2
        assert state['network_metrics']['data_airtime_s']>0
        assert any(e['event']=='phy_rx_end' and e['outcome']=='decoded' for e in events)
        if protocol in ('dacap','csma_ca'):
            assert state['network_metrics']['control_tx_frames']>0
        print(json.dumps({'mac':protocol,'routing':routing,'phy':phy,'counts':state['counts'],'network_metrics':state['network_metrics']}))
    finally:
        run.close()
