"""Power units deliberately differ for the two native nonacoustic PHYs."""
from pydantic import BaseModel, ConfigDict, model_validator
from ..resources.docker.medium_config import validate_medium


class Optical(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    tx_power_w: float=50
    bitrate_bps: float=1000000
    frequency_hz: float=10000000
    bandwidth_hz: float=100000
    attenuation_per_m: float=.043
    temperature_k: float=293.15
    receiver_area_m2: float=.0000011
    transmitter_area_m2: float=.00001
    beam_angle_rad: float=1
    dark_current_a: float=1e-9
    shunt_resistance_ohm: float=1.49e9
    responsivity_a_w: float=.26
    acquisition_threshold_db: float=10
    directional: bool=False
    mount_yaw_deg: float=0
    mount_pitch_deg: float=0
    mount_roll_deg: float=0
    offset_x_m: float=0
    offset_y_m: float=0
    offset_z_m: float=0

    @model_validator(mode='after')
    def native_bounds(self):
        validate_medium('optical',self.model_dump());return self


class Electromagnetic(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    tx_power_dbm: float=14
    bitrate_bps: float=27000
    frequency_hz: float=868000000
    bandwidth_hz: float=125000
    temperature_c: float=20
    salinity_ppt: float=0
    antenna_gain_db: float=2

    @model_validator(mode='after')
    def native_bounds(self):
        validate_medium('em',self.model_dump());return self
