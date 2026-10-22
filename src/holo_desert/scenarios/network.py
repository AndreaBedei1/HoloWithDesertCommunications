"""Typed selections of actual DESERT modules; no network model lives here."""
from typing import Literal
from .protocols import CsBurst, TokenBus, Sun
from .environment import Woss
from .media import Optical, Electromagnetic
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Acoustic(Strict):
    bitrate_bps: float = Field(default=4800, gt=0)
    tx_power_db: float = Field(default=135, ge=0, le=200)
    frequency_hz: float = Field(default=25000, gt=0)
    bandwidth_hz: float = Field(default=5000, gt=0)
    propagation: Literal['underwater','woss'] = 'underwater'
    interference: Literal['miv'] = 'miv'
    phy: Literal['bpsk_upstream','bpsk_corrected'] = 'bpsk_upstream'
    spreading: float = Field(default=1.75, gt=0, le=3)
    shipping: float = Field(default=.5, ge=0, le=1)
    wind_speed_mps: float = Field(default=0, ge=0)
    sound_speed_mps: float = Field(default=1500, gt=0)
    rx_snr_penalty_db: float = -10
    acquisition_threshold_db: float = 0

    @model_validator(mode='after')
    def band(self):
        if self.bandwidth_hz>=2*self.frequency_hz:raise ValueError('Acoustic band must stay above zero Hz')
        return self


class AcousticOverride(Strict):
    bitrate_bps: float | None = Field(default=None,gt=0)
    tx_power_db: float | None = Field(default=None,ge=0,le=200)
    frequency_hz: float | None = Field(default=None,gt=0)
    bandwidth_hz: float | None = Field(default=None,gt=0)
    phy: Literal['bpsk_upstream','bpsk_corrected'] | None = None
    spreading: float | None = Field(default=None,gt=0,le=3)
    shipping: float | None = Field(default=None,ge=0,le=1)
    wind_speed_mps: float | None = Field(default=None,ge=0)
    rx_snr_penalty_db: float | None = None
    acquisition_threshold_db: float | None = None


class NodeCommunication(Strict):
    acoustic: AcousticOverride = Field(default_factory=AcousticOverride)
    interfaces: list[str] | None = None
    interface_overrides: dict[str,AcousticOverride] = Field(default_factory=dict)


class PhyInterface(Strict):
    id: str = Field(pattern=r'^[a-z][a-z0-9_]{0,15}$')
    acoustic: AcousticOverride = Field(default_factory=AcousticOverride)


class InterfaceThreshold(Strict):
    from_interface: str
    to_interface: str
    power_linear: float = Field(gt=0)


class MultiPhy(Strict):
    interfaces: list[PhyInterface] = Field(min_length=2,max_length=3)
    policy: Literal['manual','received_power'] = 'manual'
    initial_interface: str
    master: str = 'auv_01'
    thresholds: list[InterfaceThreshold] = Field(default_factory=list)
    alpha: float = Field(default=.5,ge=0,le=1)


class Tdma(Strict):
    frame_duration_s: float = Field(default=3,gt=0)
    guard_time_s: float = Field(default=.1,ge=0)
    max_packets_per_slot: int = Field(default=1,ge=1)
    slot_assignment: dict[str,int] = Field(default_factory=dict)

    @model_validator(mode='after')
    def slots(self):
        values=list(self.slot_assignment.values())
        if any(v<0 or v>=32 for v in values) or len(set(values))!=len(values):
            raise ValueError('TDMA slot assignments must be unique in 0..31')
        return self


class RangingTdma(Strict):
    frame_duration_s: float = Field(default=3,gt=0)
    guard_time_s: float = Field(default=.1,ge=0)
    # The native ranging frame is the first transmission of every own slot.
    max_packets_per_slot: int = Field(default=2,ge=2,le=10000)


class CsmaCa(Strict):
    queue_size: int = Field(default=10,ge=1)
    backoff_delta_s: int = Field(default=1,ge=1)
    backoff_max: int = Field(default=20,ge=1)
    cts_wait_s: int = Field(default=10,gt=0)
    data_wait_s: int = Field(default=10,gt=0)
    ack_wait_s: int = Field(default=10,gt=0)


class Dacap(Strict):
    max_prop_delay_s: float = Field(default=2,gt=0)
    wait_costant_s: float = Field(default=.2,gt=0)
    delta_d: float = Field(default=1500,ge=0)
    t_min: float = Field(default=2,ge=0)
    tw_min: float = Field(default=0,ge=0)


class Mac(Strict):
    protocol: Literal['csma_aloha','aloha','tdma','tdma_frame','csma_ca','dacap','csburst','tokenbus','ranging_tokenbus','ranging_tdma'] = 'csma_aloha'
    ack: bool = False
    max_tx_tries: int = Field(default=3,ge=1,le=20)
    buffer_packets: int = Field(default=100,ge=1,le=10000)
    queue_mode: Literal['legacy','bounded'] = 'legacy'
    tdma: Tdma = Field(default_factory=Tdma)
    csma_ca: CsmaCa = Field(default_factory=CsmaCa)
    dacap: Dacap = Field(default_factory=Dacap)
    csburst: CsBurst = Field(default_factory=CsBurst)
    tokenbus: TokenBus = Field(default_factory=TokenBus)
    ranging_tokenbus: TokenBus = Field(default_factory=TokenBus)
    ranging_tdma: RangingTdma = Field(default_factory=RangingTdma)


class Flooding(Strict):
    ttl: int = Field(default=10,ge=1,le=255)
    maximum_cache_time_s: float = Field(default=60,gt=0)
    optimize: bool = True


class Network(Strict):
    profile_id: str | None = Field(default=None,pattern=r'^(builtin_[a-z_]+|profile_[0-9a-f]{32})$')
    backend: Literal['desert'] = 'desert'
    medium: Literal['acoustic','optical','em'] = 'acoustic'
    multiphy: MultiPhy | None = None
    optical: Optical = Field(default_factory=Optical)
    em: Electromagnetic = Field(default_factory=Electromagnetic)
    acoustic: Acoustic = Field(default_factory=Acoustic)
    woss: Woss = Field(default_factory=Woss)
    mac: Mac = Field(default_factory=Mac)
    routing: Literal['static','flooding','sun'] = 'static'
    sun: Sun = Field(default_factory=Sun)
    flooding: Flooding = Field(default_factory=Flooding)
    max_wire_bytes: int = Field(default=4096,ge=256,le=4096)
    seed: int = Field(default=1,ge=1,le=100000)
    routes: dict[str,dict[str,str]] = Field(default_factory=dict)

    @model_validator(mode='after')
    def supported_stack(self):
        if self.medium!='acoustic':
            if self.mac.protocol!='csma_aloha' or self.routing!='static':raise ValueError('This medium currently requires verified CSMA-ALOHA and StaticRouting')
            if self.acoustic.propagation!='underwater':raise ValueError('Nonacoustic medium cannot use WOSS')
        if self.routing=='sun' and (self.mac.protocol!='csma_aloha' or self.mac.ack):
            raise ValueError('SUN requires the verified CSMA-ALOHA stack without MAC ACK')
        if self.mac.protocol in ('csburst','tokenbus','ranging_tokenbus','ranging_tdma'):
            if self.mac.ack:raise ValueError('This native MAC has no ALOHA ACK option')
            if self.routing!='static':raise ValueError('Additional MACs currently require verified StaticRouting')
        if self.routing=='flooding' and self.mac.protocol in ('csma_ca','dacap'):
            raise ValueError('Flooding broadcast is not supported by the verified CSMA/CA or DACAP handshake stack')
        if self.mac.protocol in ('tdma','tdma_frame') and self.mac.ack:
            raise ValueError('TDMA does not support the ALOHA ACK option')
        if self.routing!='static' and self.routes:
            raise ValueError('Static routes cannot be used with Flooding')
        if self.mac.protocol=='csma_ca' and (self.acoustic.bitrate_bps%1 or self.acoustic.bitrate_bps<1 or self.acoustic.bitrate_bps>2147483647):
            raise ValueError('CSMA-CA requires integer bitrate in 1..2147483647')
        return self


class CommunicationProfile(Strict):
    name: str
    description: str = ''
    network: Network
