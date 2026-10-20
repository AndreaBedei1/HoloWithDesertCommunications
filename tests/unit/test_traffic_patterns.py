from holo_desert.core.applications import TrafficApplication
from holo_desert.scenarios.config import Flow
import pytest


def test_variable_interval_requires_an_end_time():
    with pytest.raises(ValueError,match='stop'):
        Flow(source='auv_01',destination='auv_02',final_interval=1)


class Sender:
    node='auv_01'
    def __init__(self):self.sent=[]
    def send(self,*args,**kwargs):self.sent.append((args,kwargs))


def times(pattern,**kwargs):
    sender=Sender();flow=Flow(source='auv_01',destination='auv_02',start=1,stop=10,pattern=pattern,**kwargs)
    app=TrafficApplication(sender,[flow],seed=7);sent=[]
    for tick in range(330):
        before=len(sender.sent);app.update(tick/30,None,[])
        sent.extend([tick/30]*(len(sender.sent)-before))
    return sent


def test_poisson_is_repeatable_without_changing_periodic_schedule():
    assert times('poisson',interval=1)==times('poisson',interval=1)
    assert times('poisson',interval=1)!=times('periodic',interval=1)
    assert times('periodic',interval=2)==[1,3,5,7,9]


def test_burst_and_event_schedules_are_app_injection_only():
    assert times('burst',burst_count=3,burst_interval_s=.5,burst_period_s=4)==[1,1.5,2,5,5.5,6,9,9.5]
    assert times('events',events=[1,2,4.5])==[1,2,4.5]
