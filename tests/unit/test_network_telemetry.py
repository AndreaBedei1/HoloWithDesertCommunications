from holo_desert.telemetry.collector import TelemetryCollector
from holo_desert.scenarios.config import ScenarioManager
from holo_desert.common.models import Message


def test_control_frames_and_late_arrivals_are_separate_from_data():
    collector=TelemetryCollector(ScenarioManager().load('e01_chat').model_dump())
    try:
        collector.engine_event({'event':'phy_control_tx_start','time':1,'node':1,'phy_bits':80,'duration_s':.1}, {1:'auv_01'})
        collector.engine_event({'event':'phy_control_tx_end','time':1.1,'node':1,'phy_bits':80,'duration_s':.1}, {1:'auv_01'})
        collector.emit('late_receive',5,packet_id='late')
        assert collector.snapshot()['network_metrics']=={'data_tx_frames':0,'control_tx_frames':1,'data_tx_bits':0,'control_tx_bits':80,'data_airtime_s':0,'control_airtime_s':.1,'late_received':1}
        assert collector.summary()['network_metrics']['control_tx_frames']==1
        assert collector.snapshot()['counts']['generated']==0
    finally:collector.close()


def test_late_arrival_is_visible_without_counting_a_valid_delivery():
    collector=TelemetryCollector(ScenarioManager().load('e01_chat').model_dump())
    try:
        message=Message('auv_01','auv_02',b'late',0,ttl=1)
        collector.generated(message);collector.sample(2)
        collector.emit('late_receive',5,packet_id=message.id)
        row=collector.snapshot()['packets'][0]
        assert row['late_receive_time']==5 and row['status']=='timeout_unknown_cause'
        assert any(e['event']=='late_receive' for e in row['events'])
        assert collector.snapshot()['counts']=={'generated':1,'received':0,'timed_out':1,'pending':0}
    finally:collector.close()
