import pytest
from holo_desert.scenarios.config import Scenario, ScenarioManager
from holo_desert.telemetry.collector import TelemetryCollector


def test_native_generator_configuration_and_no_python_double_injection():
    from holo_desert.core.applications import TrafficApplication
    data=ScenarioManager().load('e01_chat').model_dump()
    data['flows'][0].update(generator='desert_cbr',native_packet_bytes=125,pattern='poisson',reply=False,message_type='data')
    scenario=Scenario.model_validate(data)
    class NoSend:
        def send(self,*args,**kwargs):raise AssertionError('Native timer must generate traffic')
    TrafficApplication(NoSend(),scenario.flows[:1]).update(2,None,[])
    data['flows'][0]['reply']=True
    with pytest.raises(ValueError,match='native|Native'):Scenario.model_validate(data)


def test_native_events_have_distinct_byte_semantics_and_no_python_ttl():
    collector=TelemetryCollector(ScenarioManager().load('e01_chat').model_dump())
    inverse={1:'auv_01',2:'auv_02'}
    try:
        event=dict(native_packet_id='native:0:1:1',flow_index=0,node=1,destination_address=2,
                   packet_bytes=125,ns_uid=1,generator='desert_cbr',creation_time=1)
        collector.engine_event(dict(event,event='native_app_tx',time=1),inverse)
        collector.engine_event(dict(event,event='native_app_tx',time=1),inverse)
        collector.sample(40)
        assert collector.snapshot()['counts']==dict(generated=1,received=0,timed_out=0,pending=1)
        collector.engine_event(dict(event,event='native_app_rx',time=41,node=2),inverse)
        collector.engine_event(dict(event,event='native_app_rx',time=41,node=2),inverse)
        state=collector.snapshot()
        assert state['counts']==dict(generated=1,received=1,timed_out=0,pending=0)
        row=state['packets'][0]
        assert row['deadline'] is None and row['wire_size'] is None
        assert collector.summary()['goodput_bps'] is None
        assert collector.summary()['native_application']['received_packet_bytes']==125
    finally:collector.close()
