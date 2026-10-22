import pytest
from holo_desert.scenarios.config import Scenario,ScenarioManager
from holo_desert.core.orchestrator import SimulationOrchestrator

pytestmark=pytest.mark.desert


@pytest.mark.parametrize('generator,pattern',[('desert_cbr','periodic'),('desert_cbr','poisson'),('desert_vbr','periodic')])
def test_native_timers_generate_deliver_and_restart_without_python_envelope(engine,generator,pattern):
    data=ScenarioManager().load('e01_chat').model_dump()
    data.update(duration=10,realtime=False)
    data['flows']=data['flows'][:1]
    data['flows'][0].update(generator=generator,pattern=pattern,start=0,stop=8,interval=2,
                            native_packet_bytes=125,reply=False,message_type='data')
    for cycle in range(2):
        run=SimulationOrchestrator(Scenario.model_validate(data),standalone=True,manage_docker=False)
        try:
            run.run();state=run.snapshot()
            assert run.state=='finished',run.error
            assert state['counts']['generated']>=2,state['counts']
            assert state['counts']['received']>=2,state['counts']
            assert state['counts']['timed_out']==0
            assert all(p['generator']==generator and p['wire_size'] is None for p in state['packets'])
            assert all(e['phy_bits']==(125+4)*8 for e in state['observations'] if e['event']=='phy_tx_start')
            assert any(e['event']=='phy_rx_end' and e['outcome']=='decoded' for e in state['observations'])
            assert state['network_metrics']['control_tx_frames']==0
        finally:run.close()
