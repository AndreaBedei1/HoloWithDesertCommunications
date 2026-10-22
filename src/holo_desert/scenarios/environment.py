"""Typed inputs for native environmental models."""
from pydantic import BaseModel, ConfigDict, Field, model_validator
from ..resources.docker.environment_config import WOSS_DEFAULTS, validate_woss


class SoundSpeedPoint(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    depth_m: float = Field(ge=0)
    speed_mps: float = Field(ge=1000,le=2000)


class Woss(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    origin_latitude_deg: float = 42.59
    origin_longitude_deg: float = 10.125
    x_bearing_deg: float = 90
    water_depth_m: float = 100
    ssp: list[SoundSpeedPoint] = Field(default_factory=lambda: [SoundSpeedPoint(**p) for p in WOSS_DEFAULTS['ssp']])
    sediment_speed_mps: float = 1560
    sediment_density_g_cm3: float = 1.5
    sediment_attenuation_db_lambda: float = .9

    @model_validator(mode='after')
    def environment(self):
        validate_woss(self.model_dump())
        return self
