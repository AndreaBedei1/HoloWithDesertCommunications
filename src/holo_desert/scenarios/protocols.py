"""Parameters bound by the additional native DESERT MAC adapters."""
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProtocolParameters(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)


class CsBurst(ProtocolParameters):
    max_packets_per_burst: int = Field(default=3,ge=1,le=10000)
    fixed_sensing_s: float = Field(default=.1,gt=0)
    random_sensing_s: float = Field(default=.1,ge=0)


class TokenBus(ProtocolParameters):
    slot_time_s: float = Field(default=10,gt=0)
    min_token_hold_s: float = Field(default=.1,gt=0)
    max_token_hold_s: float = Field(default=10,gt=0)

    @model_validator(mode='after')
    def holding_times(self):
        if self.max_token_hold_s<self.min_token_hold_s:
            raise ValueError('Maximum token holding time must cover minimum holding time')
        return self


class Sun(ProtocolParameters):
    sink: str = Field(default='auv_02', pattern=r'^auv_[0-9]{2}$')
    probe_interval_s: float = Field(default=2, gt=0)
    buffer_interval_s: float = Field(default=1, gt=0)
    data_interval_s: float = Field(default=1, gt=0)
    status_interval_s: float = Field(default=1, gt=0)
    poisson_timing: bool = True
    max_ack_errors: int = Field(default=3, ge=1, le=100)
    max_retransmissions: int = Field(default=3, ge=0, le=100)
    buffer_packets: int = Field(default=5, ge=1, le=10000)
    probe_min_snr_db: float = Field(default=0)
