import pytest
from holo_desert.common.models import Pose
from holo_desert.common.coordinates import CoordinateConverter
from holo_desert.holoocean_adapter.vehicles import HoveringAUVProfile


def test_measured_roll_pitch_survive_sensor_and_network_conversion():
    data=[0.]*18
    data[6:9]=[1,2,-10];data[15:18]=[20,30,40]
    measured=HoveringAUVProfile().pose({'DynamicsSensor':data})
    assert measured==Pose(1,2,-10,40,30,20)
    translated=CoordinateConverter((1,1,0)).to_network(measured)
    assert translated==Pose(0,1,-10,40,30,20)
    with pytest.raises(ValueError):Pose(0,0,-1,pitch=float('nan'))
