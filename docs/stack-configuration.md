# Scenario and stack configuration

A scenario is one YAML (or JSON) document validated by the pydantic model
`holo_desert.Scenario` (`src/holo_desert/scenarios/config.py`). The `network`
section selects real DESERT modules (`scenarios/network.py`, `protocols.py`,
`media.py`, `environment.py`). The same document is validated a second time by
the stdlib-only stack builder (`resources/docker/stack_builder.py`), both on the
host and inside the engine container, before any Tcl is generated. Unknown
fields, non-finite numbers and incompatible combinations are rejected; nothing
is silently translated into another module.

Python only validates and serialises configuration. Channel access, routing,
propagation, interference and packet reception are executed by DESERT /
NS-MIRACLE (see [developer-guide.md](developer-guide.md) for the data path).

Contents:

- [Status vocabulary](#status-vocabulary)
- [Scenario document](#scenario-document)
- [Nodes](#nodes)
- [Traffic flows](#traffic-flows)
- [Power events and coordination](#power-events-and-coordination)
- [Network section](#network-section)
- [Acoustic PHY and analytic propagation](#acoustic-phy-and-analytic-propagation)
- [Per-node overrides](#per-node-overrides)
- [Protocol catalogue](#protocol-catalogue) (MAC, routing)
- [WOSS / Bellhop](#woss--bellhop)
- [Optical and electromagnetic media](#optical-and-electromagnetic-media)
- [Multi-PHY and interface switching](#multi-phy-and-interface-switching)
- [Ranging (Ranging-TokenBus)](#ranging-ranging-tokenbus)
- [Native applications (UW/CBR, UW/VBR)](#native-applications-uwcbr-uwvbr)
- [Modules installed but not integrated](#modules-installed-but-not-integrated)
- [Communication profiles](#communication-profiles)

Every YAML example in this document was validated with
`Scenario.model_validate(yaml.safe_load(...))` (profiles with `Network` /
`CommunicationProfile`). Validation proves that the configuration is accepted;
it does not prove that a given geometry delivers packets.

## Status vocabulary

| Status | Meaning | Modules |
|---|---|---|
| **Operational** | Native bridge tests and HoloOcean end-to-end runs; selectable in the Network Designer | MAC: ALOHA, CSMA-ALOHA, TDMA, TDMA Frame, CSMA/CA, DACAP, CS-Burst, TokenBus, Ranging-TokenBus. Routing: StaticRouting (direct and multi-hop), Flooding, SUN. PHY: upstream BPSK with analytic `Underwater` propagation (Thorp), MIV interference |
| **Operational, YAML/API only** | Native bridge tests and HoloOcean end-to-end runs; not yet exposed in the Designer | WOSS/Bellhop with a synthetic environment, native UW/CBR and UW/VBR generators |
| **Experimental patch** | Same evidence, but a project-specific class with its own patch identifier (YAML/API only except corrected BPSK) | Corrected BPSK (`conditional-bpsk-v1`), optical medium with body-frame Lambert-Beer gain adapter (`native-optical-lambert-beer-body-frame-v1`), EM medium with patched PHY (`em-power-lut-v1`) |
| **Native-verified only** | Real packets through the bridge in the native test suite; no HoloOcean end-to-end test yet | Multi-PHY (manual and received-power controller) |
| **Not integrated** | Installed in the DESERT image; a documented blocker prevents use | See [Modules installed but not integrated](#modules-installed-but-not-integrated) |

The machine-readable catalogue is
`src/holo_desert/resources/docker/communication-catalog.json` (served at
`/api/network-catalog`); the full audit of the image (116 libraries, 102 source
modules, 181 `TclClass` declarations, 85 official examples) is
`desert-inventory.json` (`/api/network-inventory`). 181 declarations are not
181 verified constructors. The dashboard Network Designer offers, for the MAC,
PHY and routing selectors, exactly the modules whose catalogue entry has
`operational: true`; media, WOSS, multi-PHY and native generators have no
Designer controls and are configured in YAML or through the API.

## Scenario document

```yaml
name: two_node_example
description: Two stationary vehicles exchange periodic messages.
duration: 30
physics_hz: 30
realtime: true
world: OpenWater
nodes:
  - {id: auv_01, position: [0, 0, -20]}
  - {id: auv_02, position: [30, 0, -20]}
flows:
  - {source: auv_01, destination: auv_02, interval: 3, payload_bytes: 32, ttl: 20}
```

| Field | Type / default | Constraints and meaning |
|---|---|---|
| `name`, `description` | string, required | |
| `duration` | float, `30` s | > 0; logical simulated time |
| `physics_hz` | int, `30` | 1–240; one tick is `1/physics_hz` s and is also the network barrier step |
| `realtime` | bool, `true` | wall-clock pacing only; `--fast` / `realtime: false` keeps the same logical timeline |
| `world` | string, `OpenWater` | HoloOcean world; the dashboard editor offers only `OpenWater` |
| `nodes` | list, 2–32 | see [Nodes](#nodes) |
| `network` | object | see [Network section](#network-section); all fields have defaults |
| `flows` | list, `[]` | see [Traffic flows](#traffic-flows) |
| `power_events` | list, `[]` | see [Power events](#power-events-and-coordination) |
| `coordination` | bool, `false` | built-in heartbeat leader/follower demo (E06) |

Bundled examples: `src/holo_desert/resources/examples/<id>/scenario.yaml`
(`e01_chat` … `e06_coordination`, listed by `holo-desert examples`). Additional
demonstrations live in `src/holo_desert/resources/demos/` (for example
`e08_woss`); pass their path to `holo-desert run` or import them in the
dashboard.

## Nodes

```yaml
name: moving_pair
description: auv_02 moves away and returns; positions come from HoloOcean sensors.
duration: 60
nodes:
  - {id: auv_01, position: [0, 0, -20]}
  - id: auv_02
    position: [20, 0, -20]
    yaw: 0
    vehicle: HoveringAUV
    waypoints: [[20, 60, 0, -20], [45, 20, 0, -20]]
flows:
  - {source: auv_01, destination: auv_02, interval: 2, stop: 55, payload_bytes: 16, ttl: 8}
```

| Field | Default | Meaning |
|---|---|---|
| `id` | required | `auv_NN` (two digits), unique |
| `position` | required | initial `[x, y, z]` in metres; HoloOcean frame X forward, Y left, Z up, so underwater depth is `-z` |
| `yaw` | `0` | initial yaw in degrees |
| `vehicle` | `HoveringAUV` | the only accepted and validated vehicle |
| `waypoints` | `[]` | `[t, x, y, z]`; times unique, increasing, ≥ 0 |
| `communication` | `null` | per-node acoustic overrides and multi-PHY interfaces ([Per-node overrides](#per-node-overrides)) |

Waypoints are targets for HoloOcean's built-in pose controller, interpolated
piecewise-linearly in time; they are not imposed positions. DESERT always
receives the poses measured by the HoloOcean `DynamicsSensor` (COM, metres)
at every tick. Nodes are mapped to DESERT addresses `1..N` in file order.

`--standalone` (CLI) or "DESERT only" (dashboard) uses the configured fixed
positions without HoloOcean; it rejects scenarios with waypoints or
`coordination: true`.

## Traffic flows

A flow describes traffic from `source` to `destination` (distinct configured
nodes; unicast only, broadcast is rejected by the application API).

| Field | Default | Constraints and meaning |
|---|---|---|
| `start` | `1` s | ≥ 0 |
| `stop` | `null` | > `start`; no generation at or after `stop` |
| `generator` | `python` | `python`, `desert_cbr`, `desert_vbr` |
| `pattern` | `periodic` | `periodic`, `poisson`, `burst`, `events` |
| `interval` | `3` s | period, or mean inter-arrival time for `poisson` |
| `final_interval` | `null` | linear change of the interval from `interval` (at `start`) to `final_interval` (at `stop`); requires `stop` |
| `payload_bytes` | `32` | 1–2048 user payload bytes (Python generator) |
| `ttl` | `20` s | application validity; does not cancel frames already queued in DESERT |
| `reply` | `false` | sends `message_type: request`; the receiver answers with a `reply` carrying `ack:` + payload and the same TTL |
| `message_type` | `data` | free label carried in the envelope |
| `burst_count`, `burst_interval_s`, `burst_period_s` | `3`, `0.25` s, `5` s | `burst`: `burst_count` messages spaced `burst_interval_s`, repeated every `burst_period_s`; `(burst_count-1)·burst_interval_s < burst_period_s` |
| `events` | `[]` | `events`: explicit generation times, unique, increasing, within `[start, stop)` |
| `native_packet_bytes` | `125` | 16–2048; packet size for native generators |
| `native_period2_s`, `native_duration1_s`, `native_duration2_s` | `2`, `5`, `5` s | UW/VBR timers |
| `interface` | `inherit` | must be `inherit` or equal to `network.medium` |

At most 64 flows are accepted.

**Python generators** (`generator: python`) are application injectors: at each
physics tick they may create at most one message per flow and pass it to the
DESERT application module of the source node. Generation times are therefore
quantised to ticks; missed ticks are not caught up. `poisson` draws exponential
intervals from a per-flow `random.Random` seeded from `network.seed`, the node
number and the flow index, so it is reproducible. The payload is the byte `x`
repeated `payload_bytes` times inside a JSON envelope (see
[telemetry-and-reproducibility.md](telemetry-and-reproducibility.md#message-sizes)).

```yaml
name: traffic_patterns
description: Python generators with different timing patterns.
duration: 40
nodes:
  - {id: auv_01, position: [0, 0, -20]}
  - {id: auv_02, position: [30, 0, -20]}
  - {id: auv_03, position: [0, 30, -20]}
flows:
  - {source: auv_01, destination: auv_02, pattern: poisson, interval: 4, stop: 35, payload_bytes: 32}
  - {source: auv_02, destination: auv_03, pattern: burst, burst_count: 3, burst_interval_s: 0.5, burst_period_s: 10, stop: 35}
  - {source: auv_03, destination: auv_01, pattern: events, events: [2, 7.5, 12], stop: 20}
  - {source: auv_01, destination: auv_03, interval: 3, final_interval: 1, start: 5, stop: 30, reply: true, ttl: 12}
```

**Native generators** (`desert_cbr`, `desert_vbr`) are described in
[Native applications](#native-applications-uwcbr-uwvbr).

## Power events and coordination

```yaml
name: outage_demo
description: auv_01 source level is reduced and restored inside DESERT.
duration: 30
nodes:
  - {id: auv_01, position: [0, 0, -20]}
  - {id: auv_02, position: [30, 0, -20]}
flows:
  - {source: auv_01, destination: auv_02, interval: 1, ttl: 3}
power_events:
  - {time: 8, node: auv_01, tx_power_db: 0}
  - {time: 18, node: auv_01, tx_power_db: 135}
```

A power event sends a `POWER` command at the first tick with `time ≤ now`; the
engine changes the transmit power of that node's PHY and emits
`power_applied`. Outages are produced by the DESERT power model; messages are
never dropped in Python. Each event carries exactly one value, in the native
unit of the configured `network.medium`; a field of another medium is
rejected:

| Medium | Field | Unit | Range | Native binding |
|---|---|---|---|---|
| `acoustic` | `tx_power_db` | dB re 1 µPa (source level) | 0–200 | `MaxTxSPL_dB_` = `MinTxSPL_dB_` |
| `optical` | `tx_power_w` | W | 1e-15–10000 | `TxPower_` |
| `em` | `tx_power_dbm` | dBm (negative values allowed) | −100–100 | `TxPower_` |

```yaml
network: {medium: em, em: {tx_power_dbm: 20}}
power_events:
  - {time: 8, node: auv_01, tx_power_dbm: -20}   # 2 m apart in fresh water: no longer decoded
  - {time: 16, node: auv_01, tx_power_dbm: 20}
```

With multi-PHY the `POWER` command changes the first interface of the node
only; per-interface power is set in the interface definition.

`coordination: true` replaces flows with the built-in heartbeat demo (exactly
two nodes, no other flows): the leader sends a 5-byte heartbeat every second
(TTL 3 s); the follower proceeds while the last heartbeat arrived within 3 s
and holds its position otherwise. This is a didactic example of reacting to
message freshness, not a safety system.

## Network section

| Field | Default | Meaning |
|---|---|---|
| `backend` | `desert` | only value |
| `medium` | `acoustic` | `acoustic`, `optical`, `em` (single interface per node) |
| `acoustic` | see below | acoustic PHY and analytic propagation |
| `mac` | `csma_aloha` | [MAC catalogue](#mac-protocols) |
| `routing` | `static` | `static`, `flooding`, `sun` |
| `routes` | `{}` | static routes `{source: {destination: next_hop}}` |
| `flooding`, `sun` | defaults | routing parameters |
| `woss`, `optical`, `em` | defaults | used only when selected |
| `multiphy` | `null` | 2–3 acoustic interfaces per node |
| `max_wire_bytes` | `4096` | 256–4096; limit on the serialised application envelope |
| `seed` | `1` | 1–100000; NS-2 RNG substream index (the bridge advances `defaultRNG` by `seed` substreams, as `rngstream` in the official samples). Also seeds the Python Poisson generators and the WOSS random generator. Recorded as `rng_substream` |
| `profile_id` | `null` | provenance of a communication profile; not used by the engine |

Combinations rejected by both validators:

- `medium: optical` or `em` requires `mac.protocol: csma_aloha`, `routing: static`,
  analytic propagation and no acoustic per-node overrides;
- `routing: sun` requires `csma_aloha` with `ack: false`;
- `csburst`, `tokenbus`, `ranging_tokenbus` require `routing: static` and `ack: false`;
- `routing: flooding` with `csma_ca` or `dacap`;
- `tdma` or `tdma_frame` with `ack: true`;
- static `routes` with any routing other than `static`;
- `csma_ca` with a non-integer bitrate (must be 1–2147483647 bit/s);
- `multiphy` with anything other than analytic acoustic BPSK, `csma_aloha`
  without ACK and `static` routing.

## Acoustic PHY and analytic propagation

Each node has one PHY instance with its own `MPropagation/Underwater`,
`MSpectralMask/Rect` and `MInterference/MIV` objects, connected to a single
shared `Module/UnderwaterChannel`. SPL/frequency/bandwidth optimisations of
the PHY are disabled so that the configured values are used as given.

| Field | Default | Unit | Constraints | DESERT binding |
|---|---|---|---|---|
| `phy` | `bpsk_upstream` | | `bpsk_upstream`, `bpsk_corrected` | PHY class (below) |
| `bitrate_bps` | `4800` | bit/s | > 0 | `BitRate_`; frame duration = PHY bits / bitrate |
| `tx_power_db` | `135` | dB re 1 µPa (SPL) | 0–200 | `MaxTxSPL_dB_` = `MinTxSPL_dB_` |
| `frequency_hz` | `25000` | Hz | > 0 | `MSpectralMask/Rect setFreq` |
| `bandwidth_hz` | `5000` | Hz | > 0 and `< 2·frequency_hz` | `setBandwidth` |
| `spreading` | `1.75` | – | (0, 3] | `practicalSpreading_` (k in 10·k·log10(d)) |
| `shipping` | `0.5` | – | [0, 1] | `shipping_` (ambient-noise term) |
| `wind_speed_mps` | `0` | m/s | ≥ 0 | `windspeed_` (ambient-noise term) |
| `sound_speed_mps` | `1500` | m/s | > 0 | `Module/UnderwaterChannel propSpeed_`; shared, not overridable per node |
| `rx_snr_penalty_db` | `-10` | dB | – | `RxSnrPenalty_dB_`, added before the BER |
| `acquisition_threshold_db` | `0` | dB | – | `AcquisitionThreshold_dB_`; raw SNR must exceed it strictly |
| `propagation` | `underwater` | | `underwater`, `woss` | analytic model or [WOSS](#woss--bellhop) |
| `interference` | `miv` | | `miv` only | `MInterference/MIV` |

Units and model notes:

- The source level is an acoustic SPL in dB re 1 µPa. The PHY uses
  `Pt = 10^(SPL/10)` in normalised acoustic units; it is not electrical power,
  dBm or dBW.
- The analytic propagation delay is distance / `sound_speed_mps`. Attenuation
  (Thorp) and ambient noise depend on frequency; the noise density at the
  centre frequency is multiplied by the bandwidth.
- The BER is not an independent parameter: it follows from SNR, penalty and
  the BPSK model.
- The defaults (25 kHz, 5 kHz, 4800 bit/s, 135 dB SPL, spreading 1.75,
  shipping 0.5, wind 0, 1500 m/s, penalty −10 dB, acquisition 0 dB) are the
  bridge profile taken from the official examples, not recommendations for a
  real modem. E03 uses 105 dB SPL.

### BPSK variants

| `phy` | Tcl class | Patch id | Status |
|---|---|---|---|
| `bpsk_upstream` | `Module/MPhy/BPSK/Underwater/HOLO` | `upstream-original` | Operational |
| `bpsk_corrected` | `Module/MPhy/BPSK/Underwater/HOLO/Corrected` | `conditional-bpsk-v1` | Experimental patch |

Both are subclasses of the upstream `UnderwaterMPhyBpsk` that add observation
events (`phy_tx_start`, `phy_rx_start`, `phy_rx_end`, …) and delegate TX/RX,
synchronisation and error decisions to the upstream code.

The upstream `endRx` tests noise and then, in its "interference" branch,
tests the noise again even when the interference power is zero. The corrected
class keeps that model for acquisition, bitrate, SNR penalty, propagation and
MIV, and replaces only the second test. With `Pn` the packet error probability
from noise alone and `Pt` the total for noise plus interference, the residual
risk after a passed noise test is `q = (Pt − Pn) / (1 − Pn)`, so that
`Pn + (1 − Pn)·q = Pt`. The success ratio is computed in the log domain
(`log1p`/`expm1`); for time-varying interference the MIV chunks are weighted
by their fractional bit duration. With zero interference `q = 0` and no second
draw is made. Because the number of RNG draws changes, compare statistics, not
individual outcomes. It is a patch of the idealised BPSK model, not a
calibration against a modem or sea measurements. The controlled test that
motivated it is recorded in [evidence/desert-laboratory.md](evidence/desert-laboratory.md)
(two fixed nodes at 40 m, 105 dB SPL, 24 frames per variant: upstream 3/24
decoded, corrected 11/24; empirical frequencies, not PER estimates).

## Per-node overrides

```yaml
name: heterogeneous_acoustic
description: auv_02 uses a lower bitrate, higher source level and the corrected PHY.
duration: 30
nodes:
  - {id: auv_01, position: [0, 0, -20]}
  - id: auv_02
    position: [40, 0, -20]
    communication:
      acoustic: {bitrate_bps: 2400, tx_power_db: 140, phy: bpsk_corrected}
network:
  acoustic: {tx_power_db: 130}
flows:
  - {source: auv_01, destination: auv_02, interval: 4, payload_bytes: 32}
```

`communication.acoustic` may override `bitrate_bps`, `tx_power_db`,
`frequency_hz`, `bandwidth_hz`, `phy`, `spreading`, `shipping`,
`wind_speed_mps`, `rx_snr_penalty_db` and `acquisition_threshold_db`. Empty
(`null`) fields inherit the global value. Sound speed, propagation type and
interference model stay global. Overrides are rejected for optical/EM media.
The engine reports the resolved per-node values in `engine_info.effective_nodes`.
Per-node MAC or routing selection is not available.

## Protocol catalogue

### MAC protocols

Common MAC fields (`network.mac`):

| Field | Default | Constraints | Used by |
|---|---|---|---|
| `protocol` | `csma_aloha` | see table below | all |
| `ack` | `false` | | ALOHA, CSMA-ALOHA, CSMA/CA, DACAP (`setAckMode`/`setNoAckMode`); rejected for TDMA, TDMA Frame, CS-Burst, TokenBus, Ranging-TokenBus |
| `max_tx_tries` | `3` | 1–20 | ALOHA/CSMA-ALOHA (`max_tx_tries_`, after construction), DACAP (`max_tx_tries`, before construction); not used by CSMA/CA. Meaningful only with ACK |
| `buffer_packets` | `100` | 1–10000 | queue limit; binding per protocol below |
| `queue_mode` | `legacy` | `legacy`, `bounded` | CSMA-ALOHA only |

Overview:

| `protocol` | DESERT class / libraries | Status | Routing | Queue counter |
|---|---|---|---|---|
| `aloha` | `Module/UW/ALOHA`, `libuwaloha.so` | Operational | static, flooding | `getQueueSize` |
| `csma_aloha` | `Module/UW/CSMA_ALOHA`, `libuwcsmaaloha.so` | Operational | static, flooding, sun | `getQueueSize` |
| `tdma` | `Module/UW/TDMA`, `libuwtdma.so` | Operational | static, flooding | `get_buffer_size` |
| `tdma_frame` | `Module/UW/TDMA_FRAME`, `libuwtdma.so` + `libuwtdma_frame.so` | Operational | static, flooding | `get_buffer_size` |
| `csma_ca` | `Module/UW/CSMA_CA`, `libuwcsmaca.so` | Operational | static | `getQueueSize` |
| `dacap` | `Module/UW/DACAP`, `libuwdacap.so` | Operational | static | `getQueueSize` |
| `csburst` | `Module/UW/CSBURST`, `libuwcsburst.so` | Operational | static | `get_buffer_size` |
| `tokenbus` | `Module/UW/TOKENBUS`, `libuwcbr.so` + `libuwtokenbus.so` | Operational | static | `get_buffer_size` |
| `ranging_tokenbus` | `Module/UW/RANGING_TOKENBUS`, + `libuwranging_tokenbus.so` | Operational | static | `get_buffer_size` |

All MACs work with both acoustic BPSK variants. Only CSMA-ALOHA is accepted
for the optical, EM and multi-PHY stacks. The CLI option `--mac <protocol>`
changes only the MAC of a scenario, for example
`holo-desert run e01_chat --mac tdma --headless`.

The defaults below are the **bridge initialisation profile**, verified on the
native bindings of the pinned image (DESERT source commit
`12203f3cdba7d85bac78074d1f2ccfddbfb08021`). They are neither deployment
recommendations nor necessarily the raw upstream defaults.

#### ALOHA (`aloha`)

Transmits without carrier sensing; reference for random access. The adapter
(`mac_aloha.tcl`) creates the module, sets `max_tx_tries_`, `buffer_pkts_`
(from `buffer_packets`) and `max_payload_ 4096` on the instance, selects ACK
mode and calls `initialize`. ALOHA enables its queue in the constructor, so
`buffer_packets` is an active limit. Collisions are possible by design.

```yaml
name: aloha_ack
description: ALOHA with MAC acknowledgements.
duration: 30
nodes:
  - {id: auv_01, position: [0, 0, -20]}
  - {id: auv_02, position: [30, 0, -20]}
network:
  mac: {protocol: aloha, ack: true, max_tx_tries: 3, buffer_packets: 50}
flows:
  - {source: auv_01, destination: auv_02, interval: 3}
```

#### CSMA-ALOHA (`csma_aloha`, default)

Senses the channel and waits a random time before data. Same adapter and
fields as ALOHA, plus `queue_mode`:

- `legacy` (default): the class binding `buffer_pkts_` is `-1` before the
  constructor, so the native `has_buffer_queue` flag stays false and the queue
  has **no native limit**; `buffer_packets` is still written to the instance
  but does not bound the queue. This reproduces E01–E06 without changing their
  YAML.
- `bounded`: `buffer_pkts_ = buffer_packets` is set on the class before
  construction, enabling the native limit; bursts can then cause MAC discards
  (`mac_discarded_tx`).

```yaml
name: csma_bounded
description: CSMA-ALOHA with an active native queue limit.
duration: 30
nodes:
  - {id: auv_01, position: [0, 0, -20]}
  - {id: auv_02, position: [30, 0, -20]}
network:
  mac: {protocol: csma_aloha, queue_mode: bounded, buffer_packets: 5}
flows:
  - {source: auv_01, destination: auv_02, pattern: burst, burst_count: 8, burst_interval_s: 0.1, burst_period_s: 10}
```

#### TDMA (`tdma`)

Scheduled access in fixed slots. Before the constructor the adapter sets class
defaults (`debug_ 0`, `HDR_size_ 0`, `wait_constant_ 0.1`, `MAC_addr_ 0`,
`sea_trial_ 0`, `fair_mode 1`, `drop_old_ 0`, `checkPriority_ 0`,
`mac2phy_delay_ 1e-9`), `queue_size_ = buffer_packets`, `tot_slots = N` and the
three parameters below; each node then gets `setMacAddr` and `setSlotNumber`;
all MACs are started at `t = 0`.

| Field (`network.mac.tdma`) | Default | Unit | Constraints |
|---|---|---|---|
| `frame_duration_s` | `3` | s | > 0; slot length = frame / N |
| `guard_time_s` | `0.1` | s | ≥ 0 and shorter than a slot |
| `max_packets_per_slot` | `1` | packets | ≥ 1 |
| `slot_assignment` | `{}` | slot index | empty = file order; otherwise every node, indices 0..N−1 each used once |

The builder rejects frames that cannot fit a slot: the serialised envelope
(conservatively sized with a maximal float timestamp, request overhead, 4 UDP
bytes and 1 Flooding byte when applicable) at the slowest configured bitrate
must last no longer than `slot − guard`. This is a conservative check, not a
guarantee of collision freedom in every geometry; propagation and
synchronisation remain in the model.

```yaml
name: tdma_three_nodes
description: TDMA with explicit slots.
duration: 40
nodes:
  - {id: auv_01, position: [0, 0, -20]}
  - {id: auv_02, position: [30, 0, -20]}
  - {id: auv_03, position: [0, 30, -20]}
network:
  mac:
    protocol: tdma
    tdma: {frame_duration_s: 6, guard_time_s: 0.2, slot_assignment: {auv_01: 2, auv_02: 0, auv_03: 1}}
flows:
  - {source: auv_01, destination: auv_02, interval: 6, payload_bytes: 32}
```

#### TDMA Frame (`tdma_frame`)

Slots defined by a native topology matrix. It uses the same `network.mac.tdma`
fields and class defaults. The adapter generates a one-hot matrix from the slot
assignment in the session's temporary directory (never a user path), sets the
space separator explicitly (the native default comma separator with
space-separated rows caused SIGFPE), and passes the 1-based topology index.
With two nodes and a 3 s frame, TDMA transmits at phases 0 and 1.5 s while
TDMA Frame, with the same one-hot matrix, uses 1.5 and 0 s; this native phase
difference is observed and tested, not rewritten.

#### CSMA/CA (`csma_ca`)

RTS/CTS handshake before data. All bindings are integers set on the class
before construction (`debug_ 0`, `bitrate_`, and the fields below); each
instance then receives its own integer `bitrate_` (the node's PHY bitrate),
`setMacAddr`, ACK mode and `initialize`.

| Field (`network.mac.csma_ca`) | Default | Unit | Binding |
|---|---|---|---|
| `queue_size` | `10` | packets | `queue_size_`; this replaces `buffer_packets` for CSMA/CA |
| `backoff_delta_s` | `1` | s (integer) | `backoff_delta_` |
| `backoff_max` | `20` | – | `backoff_max` |
| `cts_wait_s` | `10` | s (integer) | `cts_wait_val_` |
| `data_wait_s` | `10` | s (integer) | `data_wait_val_` |
| `ack_wait_s` | `10` | s (integer) | `ack_wait_val_` (with ACK) |

The native queue test is inclusive (`getQueueSize() <= queue_size`): up to
`queue_size + 1` packets can be queued in addition to the frame in service.
This is documented, not patched. `max_tx_tries` is not used. Flooding is
rejected: CSMA/CA drops broadcast RTS in `uw-csma-ca.cpp` (`stateRxRTS`), and
the native matrix showed no delivery for Flooding with CSMA/CA or DACAP.
Additional counters: `rts_rx`, `cts_rx`, `rts_dropped`, `cts_dropped`,
`data_dropped`, `upper_data_rx`.

```yaml
name: csma_ca_pair
description: CSMA/CA with ACK.
duration: 60
nodes:
  - {id: auv_01, position: [0, 0, -20]}
  - {id: auv_02, position: [30, 0, -20]}
network:
  mac:
    protocol: csma_ca
    ack: true
    csma_ca: {queue_size: 10, backoff_delta_s: 1, backoff_max: 20, cts_wait_s: 10, data_wait_s: 10, ack_wait_s: 10}
flows:
  - {source: auv_01, destination: auv_02, interval: 10}
```

#### DACAP (`dacap`)

Handshake with waiting times tied to acoustic delays. Bindings without
underscores are set on the class before construction (`debug_ 0`,
`max_tx_tries`, `buffer_pkts = buffer_packets`, `max_payload 4096` and the
fields below); each instance gets `setMacAddr` and ACK mode; ALOHA's
`initialize` is not called.

| Field (`network.mac.dacap`) | Default | Unit | Binding |
|---|---|---|---|
| `max_prop_delay_s` | `2` | s | `max_prop_delay` (handshake timing, not an imposed range) |
| `wait_costant_s` | `0.2` | s | `wait_costant` (upstream spelling) |
| `delta_d` | `1500` | m | `delta_D`; not fed with HoloOcean distances |
| `t_min` | `2` | s | `t_min` |
| `tw_min` | `0` | s | `T_W_min` |

DACAP changes the packet type of data frames; telemetry recognises its DATA
frames through the native header (`orig_type`) and separates them from control
frames. Additional counters: `mean_defer_time_s`, `defer_count`, `warning_tx`,
`warning_rx`, `rts_tx`, `rts_rx`, `cts_tx`, `cts_rx`, `upper_data_rx`. Flooding
is rejected as for CSMA/CA.

#### CS-Burst (`csburst`) — operational

Carrier sensing followed by a native burst of queued frames; no ALOHA ACK.
Class bindings before construction: `queue_size = buffer_packets`,
`max_packet_per_burst`, `fix_sens_time`, `rv_sens_time`; each instance gets
`setMacAddr`.

| Field (`network.mac.csburst`) | Default | Unit | Constraints |
|---|---|---|---|
| `max_packets_per_burst` | `3` | packets | 1–10000 |
| `fixed_sensing_s` | `0.1` | s | > 0 |
| `random_sensing_s` | `0.1` | s | ≥ 0 |

#### TokenBus (`tokenbus`) — operational

Logical ring with a token and timeout-based recovery. Class bindings before
construction: `debug_ 0`, `debug_tb 0`, `drop_old_ 0`, `checkPriority_ 0`,
`mac2phy_delay_ 1e-9`, `n_nodes_ = N`, `queue_size_ = buffer_packets` and the
fields below. Ring membership and timers are captured and started by the
native constructor.

| Field (`network.mac.tokenbus`) | Default | Unit | Meaning |
|---|---|---|---|
| `slot_time_s` | `10` | s | native token-wait timeout (`slot_time_`); not a TDMA slot |
| `min_token_hold_s` | `0.1` | s | `min_token_hold_time_` |
| `max_token_hold_s` | `10` | s | `max_token_hold_time_`; ≥ `min_token_hold_s` |

The defaults are the upstream 10 s slot and maximum holding time. The builder
rejects flows whose frame airtime, `(frame bytes + 6) · 8 / slowest bitrate`
(4 UDP bytes and a 2-byte TokenBus header), is not shorter than
`max_token_hold_s` or than the initial idle timeout
`3 · (slot_time_s + min_token_hold_s)`; short initial idle timers can regenerate
the token while a large frame is still being received. Additional counters:
`token_resends`, `token_regenerations`, `invalid_tokens`,
`bus_idle_expirations`, `token_pass_expirations`.

```yaml
name: tokenbus_ring
description: Native TokenBus ring with static routing.
duration: 120
physics_hz: 10
nodes:
  - {id: auv_01, position: [0, 0, -30]}
  - {id: auv_02, position: [40, 0, -30]}
  - {id: auv_03, position: [0, 60, -30]}
network:
  mac:
    protocol: tokenbus
    tokenbus: {slot_time_s: 10, min_token_hold_s: 0.1, max_token_hold_s: 10}
flows:
  - {source: auv_01, destination: auv_03, start: 5, interval: 20, payload_bytes: 16, ttl: 60}
```

#### Ranging-TokenBus (`ranging_tokenbus`) — operational

TokenBus with native ranging. Same fields under `network.mac.ranging_tokenbus`.
See [Ranging](#ranging-ranging-tokenbus).

### Routing protocols

#### StaticRouting (`routing: static`, default) — operational

`Module/UW/StaticRouting`, `libuwstaticrouting.so`. For every ordered node pair
the adapter calls the native `addRoute destination next_hop`; a destination
without an explicit entry is routed directly. Validation rejects unknown nodes,
routes to or through the source itself and loops. A configured route does not
guarantee reception.

```yaml
name: relay_chain
description: A-B-C static relay as in E05.
duration: 30
nodes:
  - {id: auv_01, position: [-500, 0, -100]}
  - {id: auv_02, position: [0, 0, -100]}
  - {id: auv_03, position: [500, 0, -100]}
network:
  acoustic: {tx_power_db: 132}
  routes:
    auv_01: {auv_03: auv_02}
    auv_03: {auv_01: auv_02}
flows:
  - {source: auv_01, destination: auv_03, start: 1, stop: 12, interval: 5, payload_bytes: 16, ttl: 16}
```

#### Flooding (`routing: flooding`) — operational

`Module/UW/FLOODING`, `libuwflooding.so`. Native broadcast forwarding with a
duplicate cache, for unicast application destinations; no `addRoute`. Class
bindings `ttl_`, `maximum_cache_time_`, `optimize_`; per node `addr`.

| Field (`network.flooding`) | Default | Unit | Constraints |
|---|---|---|---|
| `ttl` | `10` | hops | 1–255; distinct from the application TTL in seconds |
| `maximum_cache_time_s` | `60` | s | > 0; duplicate-suppression memory |
| `optimize` | `true` | – | native optimisation |

Compatible MACs: ALOHA, CSMA-ALOHA, TDMA, TDMA Frame.

```yaml
name: flooding_tdma
description: Native Flooding over TDMA.
duration: 40
nodes:
  - {id: auv_01, position: [0, 0, -20]}
  - {id: auv_02, position: [30, 0, -20]}
  - {id: auv_03, position: [60, 0, -20]}
network:
  mac: {protocol: tdma, tdma: {frame_duration_s: 6}}
  routing: flooding
  flooding: {ttl: 4, maximum_cache_time_s: 60, optimize: true}
flows:
  - {source: auv_01, destination: auv_03, interval: 6, payload_bytes: 16}
```

#### SUN (`routing: sun`) — operational

`Module/UW/SUNNode` and `Module/UW/SUNSink`, `libsun.so` (with `libuwcbr.so`).
Convergecast to one sink: native probes and path establishment choose the
route. Requires CSMA-ALOHA without MAC ACK; every flow must end at the sink,
must not start at the sink and must not request replies; static routes and
`coordination` are rejected. All nodes are initialised and the sink is started
at `t = 0.1 s`.

| Field (`network.sun`) | Default | Unit | Binding |
|---|---|---|---|
| `sink` | `auv_02` | node id | `SUNSink` on that node, `SUNNode` elsewhere |
| `probe_interval_s` | `2` | s | `SUNSink t_probe` |
| `buffer_interval_s` | `1` | s | `timer_buffer_` |
| `data_interval_s` | `1` | s | `period_data_` |
| `status_interval_s` | `1` | s | `period_status_` |
| `poisson_timing` | `true` | – | `SUNNode PoissonTraffic_` (sink: 0) |
| `max_ack_errors` | `3` | errors | `max_ack_error_`, 1–100 |
| `max_retransmissions` | `3` | attempts | `max_retx_`, 0–100 |
| `buffer_packets` | `5` | packets | `buffer_max_size_`, 1–10000 |
| `probe_min_snr_db` | `0` | dB | `probe_min_snr_`; minimum SNR to accept a probe |

Probe reception is distinct from reliable data reception: set
`probe_min_snr_db` for the payload and geometry (the five-node native test uses
20 dB to avoid selecting a weak direct link). SUN's cumulative counters are
static members of its node/sink classes; the `routing_stats` event therefore
reports class totals in `class_values` (do not sum them across nodes) and only
local queue and path counters in `values`.

```yaml
name: sun_convergecast
description: SUN dynamic routing towards a sink.
duration: 90
physics_hz: 10
nodes:
  - {id: auv_01, position: [0, 0, -40]}
  - {id: auv_02, position: [400, 0, -40]}
  - {id: auv_03, position: [800, 0, -40]}
network:
  mac: {protocol: csma_aloha}
  routing: sun
  sun: {sink: auv_03, probe_min_snr_db: 20}
  acoustic: {tx_power_db: 140}
flows:
  - {source: auv_01, destination: auv_03, start: 20, stop: 80, interval: 10, payload_bytes: 16, ttl: 40}
```

## WOSS / Bellhop

Status: operational (native and HoloOcean end-to-end tests, `demos/e08_woss`), YAML/API only, synthetic environment only.

Select `network.acoustic.propagation: woss` with `phy: bpsk_upstream` (the
corrected analytic BPSK is rejected). The bridge uses `WOSS/Module/Channel`,
`WOSS/MPropagation` and a transparent observer subclass of
`WOSS/Module/MPhy/BPSK` (`WOSS/Module/MPhy/BPSK/HOLO`, patch id
`woss-native-bpsk`). Transmission, received power, delay, interference and
reception decisions remain in DESERT/WOSS; Bellhop (`bellhop.exe`) computes
the channel from the configured environment.

`network.woss` defines an explicitly synthetic environment: flat sea surface,
flat seabed, one sediment and a depth-dependent sound speed profile (SSP). It
does not import the Unreal seabed or geographic databases (GEBCO, WOA, DECK41).

| Field | Default | Unit | Constraints |
|---|---|---|---|
| `origin_latitude_deg` | `42.59` | ° | −85..85 |
| `origin_longitude_deg` | `10.125` | ° | −180..180 |
| `x_bearing_deg` | `90` | ° | 0..360; clockwise bearing of HoloOcean +X from north |
| `water_depth_m` | `100` | m | 1..11000 |
| `ssp` | `[{0, 1500}, {100, 1500}]` | m, m/s | 2–256 points; depth positive downwards, strictly increasing from 0 to `water_depth_m`; speeds 1000–2000 m/s |
| `sediment_speed_mps` | `1560` | m/s | 100..10000 |
| `sediment_density_g_cm3` | `1.5` | g/cm³ | 0.1..20 |
| `sediment_attenuation_db_lambda` | `0.9` | dB/λ | 0..100 |

Shear speed, shear attenuation and layer depth keep the pinned no-database
sample values 200 m/s, 0.8 dB/λ and 1 m.

Geometry: positive Y points left of X, so with a 90° (east) X bearing positive
Y points north. Native WOSS geodesic utilities convert the local horizontal
vector to latitude/longitude; local Z is altitude relative to the sea surface.
The local frame extends 100 km from the origin. Every node (initial position,
waypoints and every measured update) needs more than 0.1 m clearance from the
surface and the seabed (the Bellhop receiver samples span ±0.1 m), and every
pair needs at least 1 m horizontal separation: in the pinned native code a
vertically aligned link aborts in `bellhop-woss.cpp:946`, so configuration and
runtime guards reject it before propagation. These are model constraints, not
artificial link losses.

Each session owns its SSP file, Bellhop working directory and results database
in a new temporary directory; space sampling is fixed at zero; `STOP` closes
the database connections. The environment is stationary; vehicle movement
changes the native geometry; vehicle attitude does not steer this
omnidirectional model. Analytic `spreading` and `sound_speed_mps` do not control
WOSS. Source level remains dB re 1 µPa; `position_applied` events add
`latitude_deg`, `longitude_deg`, `altitude_m`.

```yaml
name: woss_synthetic
description: Bellhop with a nonuniform synthetic sound speed profile.
duration: 18
nodes:
  - {id: auv_01, position: [0, 0, -20]}
  - {id: auv_02, position: [30, 0, -40], waypoints: [[4, 100, 0, -60], [12, 40, 20, -30]]}
network:
  acoustic: {propagation: woss, tx_power_db: 150}
  woss:
    origin_latitude_deg: 42.59
    origin_longitude_deg: 10.125
    x_bearing_deg: 90
    water_depth_m: 100
    ssp:
      - {depth_m: 0, speed_mps: 1500}
      - {depth_m: 50, speed_mps: 1480}
      - {depth_m: 100, speed_mps: 1510}
flows:
  - {source: auv_01, destination: auv_02, start: 1, stop: 16, interval: 5, payload_bytes: 16, ttl: 10}
```

The bundled demo is `src/holo_desert/resources/demos/e08_woss/scenario.yaml`;
it requires HoloOcean (the standalone fixture does not fabricate trajectories).

## Optical and electromagnetic media

`network.medium` selects one native chain per node. `optical` and `em`
currently require CSMA-ALOHA, StaticRouting and analytic propagation, and
reject acoustic per-node overrides. A flow inherits the network medium. Power
units differ deliberately between media.

### Optical (`medium: optical`) — experimental adapter, native and end-to-end verified

Chain: `Module/UW/Optical/Channel`, `Module/UW/OPTICAL/Propagation/HOLO`
(a subclass of the native `UwOpticalMPropagation`), `Module/UW/OPTICAL/PHY/HOLO`
(observer of `UwOpticalPhy`), native interference and the installed optical
ambient-noise LUT (`optical_noise/LUT.txt`, read with a space separator).
Attenuation is a fixed constant `c` (`setFixedC`); no oceanographic profile is
selected implicitly. The native model takes the acquisition decision from the
squared photodetector-current SNR and rejects receptions with positive
interference; no additional Python BER curve exists.

| Field (`network.optical`) | Default | Unit | Range | Binding |
|---|---|---|---|---|
| `tx_power_w` | `50` | W | 1e-15..10000 | PHY `TxPower_` |
| `bitrate_bps` | `1000000` | bit/s | 1..1e9 | `BitRate_` |
| `frequency_hz` | `10000000` | Hz | 1..1e15 | mask centre (not converted to a new wavelength calibration) |
| `bandwidth_hz` | `100000` | Hz | 1..1e12, `< 2·frequency_hz` | mask bandwidth |
| `attenuation_per_m` | `0.043` | m⁻¹ | 0..100 | propagation `c_` |
| `temperature_k` | `293.15` | K | 250..350 | PHY `T_` |
| `receiver_area_m2` | `1.1e-6` | m² | 1e-12..10 | `Ar_` |
| `transmitter_area_m2` | `1e-5` | m² | 1e-12..10 | `At_` |
| `beam_angle_rad` | `1` | rad | 0..1.56 | `theta_` |
| `dark_current_a` | `1e-9` | A | 0..1 | `Id_` |
| `shunt_resistance_ohm` | `1.49e9` | Ω | 1..1e15 | `R_` |
| `responsivity_a_w` | `0.26` | A/W | 1e-12..100 | `S_` |
| `acquisition_threshold_db` | `10` | dB | −100..100 | `AcquisitionThreshold_dB_` |
| `directional` | `false` | – | bool | enables the body-frame gain adapter |
| `mount_yaw_deg`, `mount_pitch_deg`, `mount_roll_deg` | `0` | ° | −360..360 | transducer mount |
| `offset_x_m`, `offset_y_m`, `offset_z_m` | `0` | m | −100..100 | transducer offset in body coordinates |

`directional: false` keeps the native omnidirectional gain. With
`directional: true`, the project adapter `native-optical-lambert-beer-body-frame-v1`
supplies the transmitter angle to the unchanged native
`getLambertBeerGain(distance, beta)`: the transducer forward axis is rotated by
the mount and then by the measured body attitude (right-handed
`Rz(yaw)·Ry(pitch)·Rx(roll)`); backward-facing transmitters have zero gain.
HoloOcean roll, pitch and yaw are transported with every synchronised
`POSITION` command. Limits: receiver optics remain omnidirectional; no
receiver field of view or occlusion model; offsets affect the native gain
distance and angle, while propagation delay and ambient-noise depth use the
vehicle COM. It is an experimental gain adapter, not a calibrated optical
modem. The pinned noise LUT covers 0–20 m depth, so initial positions,
waypoints and measured updates outside `-20 <= z < 0` are rejected (no
extrapolation to zero noise).

```yaml
name: optical_pair
description: Short-range optical link with the directional gain adapter.
duration: 20
nodes:
  - {id: auv_01, position: [0, 0, -10]}
  - {id: auv_02, position: [5, 0, -10], yaw: 180}
network:
  medium: optical
  optical: {tx_power_w: 50, attenuation_per_m: 0.043, directional: true, mount_yaw_deg: 0}
flows:
  - {source: auv_01, destination: auv_02, interval: 2, payload_bytes: 32}
```

### Electromagnetic (`medium: em`) — experimental patch, native and end-to-end verified

Chain: `Module/UW/ElectroMagnetic/Channel`, `…/Propagation`, `…/Antenna` and
the project PHY `Module/UW/ElectroMagnetic/PHY/HOLO` built from a separately
named copy of the native EM PHY (`em-power-lut-v1`). The PER comes from the
pinned DESERT table `em_attenuation/CR_4-5/SF_7.csv`, an empirical SF7 CR4/5
RSSI/PER table, not a calibration for every bitrate, frequency or device.
Arbitrary user paths or Tcl are never accepted.

| Field (`network.em`) | Default | Unit | Range | Binding |
|---|---|---|---|---|
| `tx_power_dbm` | `14` | dBm | −100..100 | PHY `TxPower_` |
| `bitrate_bps` | `27000` | bit/s | 1..1e9 | `BitRate_` |
| `frequency_hz` | `868000000` | Hz | 1..1e15 | mask centre |
| `bandwidth_hz` | `125000` | Hz | 1..1e12, `< 2·frequency_hz` | mask bandwidth |
| `temperature_c` | `20` | °C | 0..40 | propagation `T_` |
| `salinity_ppt` | `0` | ppt | 0..40 | propagation `S_` |
| `antenna_gain_db` | `2` | dB | −100..100 | `Antenna setGain` (constant; does not respond to vehicle pointing) |

The patch fixes the upstream end-iterator dereference above the maximum RSSI,
normalises exact table hits from percent to probability (the supplied values
6.5 and 2.5 percent were returned directly as probabilities by the upstream
exact-match branch), stores positive linear mW in the packet header and uses
the actual source power in the received-power equation (upstream stores dBm in
a header asserted positive and uses the receiver's own transmitter power, so
negative powers crash and heterogeneous transmitters are ignored). The user API
keeps dBm. Source-pattern assertions reject a different upstream
implementation at build time; the installed library and original class are
untouched. The surface is local `z = 0`.

```yaml
name: em_freshwater
description: EM link in fresh water.
duration: 20
nodes:
  - {id: auv_01, position: [0, 0, -2]}
  - {id: auv_02, position: [3, 0, -2]}
network:
  medium: em
  em: {tx_power_dbm: 14, salinity_ppt: 0, temperature_c: 20}
flows:
  - {source: auv_01, destination: auv_02, interval: 2, payload_bytes: 16}
```

Telemetry separates optical TX/RX power in W and noise in A² from EM TX power
in dBm and RX power in mW (`power_unit`, `received_power_unit`, `noise_unit`
fields). Optical/EM PHY events carry no per-packet `outcome`; application `rx`
events establish delivery.

## Multi-PHY and interface switching

Status: native-verified through the bridge (manual and received-power
controller).

`network.multiphy` gives every node 2–3 acoustic BPSK interfaces, each with its
own PHY, propagation, spectral mask and MIV object on the shared channel, under
DESERT's multi-stack controller (`libuwmulti_stack_controller.so`). One MAC
(CSMA-ALOHA without ACK) and static routing are shared above the controller.

| Field | Default | Meaning |
|---|---|---|
| `interfaces` | required | 2–3 items `{id, acoustic}`; `id` matches `[a-z][a-z0-9_]{0,15}`; `acoustic` overrides as in [Per-node overrides](#per-node-overrides) |
| `initial_interface` | required | must exist and be available on every node |
| `policy` | `manual` | `manual` (`Module/UW/MULTI_STACK_CONTROLLER_PHY`) or `received_power` (`…_MASTER` on the master node, `…_SLAVE` elsewhere) |
| `master` | `auv_01` | master node for `received_power` |
| `thresholds` | `[]` | `{from_interface, to_interface, power_linear}`; only for `received_power`, between adjacent interfaces in list order, both directions required; `power_linear > 0` in native linear received-power units |
| `alpha` | `0.5` | 0..1, `setAlpha` on the master |

Rules: interface bands must be disjoint
(`|f1 − f2| > (b1 + b2)/2`); per node, `communication.interfaces` may list a
subset (manual policy only; it must include the initial interface) and
`communication.interface_overrides` may override settings per interface.
Override order: global `acoustic` < node `communication.acoustic` < interface
`acoustic` < node `interface_overrides`. Flows cannot select an interface
(`flow.interface` must be `inherit`).

With `manual`, the interface is changed at run time through the bridge command
`INTERFACE` (Python API `NetworkNode.select_interface`, see [api.md](api.md)); the
switch requires an idle controller and an empty MAC queue and emits
`interface_selected`. With `received_power`, the native controller switches
automatically according to the thresholds. Each `phy_*` event carries
`interface_index`; `STATS` emits `interface_state`.

```yaml
name: multiphy_received_power
description: Two acoustic interfaces switched by the native received-power controller.
duration: 30
nodes:
  - {id: auv_01, position: [0, 0, -20]}
  - {id: auv_02, position: [30, 0, -20]}
network:
  multiphy:
    policy: received_power
    initial_interface: long
    master: auv_01
    interfaces:
      - {id: long, acoustic: {frequency_hz: 25000, bandwidth_hz: 5000, bitrate_bps: 4800, tx_power_db: 150}}
      - {id: short, acoustic: {frequency_hz: 50000, bandwidth_hz: 9000, bitrate_bps: 8800, tx_power_db: 150}}
    thresholds:
      - {from_interface: long, to_interface: short, power_linear: 1}
      - {from_interface: short, to_interface: long, power_linear: 1.0e-6}
flows:
  - {source: auv_01, destination: auv_02, interval: 5, payload_bytes: 16}
```

## Ranging (Ranging-TokenBus)

Status: operational (native, HoloOcean end-to-end and `demos/e07_ranging_tokenbus`).

`mac.protocol: ranging_tokenbus` loads `libuwranging_tokenbus.so` on top of
TokenBus. At every `STATS` command (once per simulated second in the
orchestrator and in `NetworkSession.step`) each observer node runs the native
`calc_distances` and, for every node pair, `get_distance`. The native value is
a one-way travel time in seconds; the adapter multiplies it by
`acoustic.sound_speed_mps` to report metres. Each estimate is emitted as

```json
{"event":"ranging_estimate","time":12.0,"node":1,"peer_a":2,"peer_b":3,
 "travel_time_s":0.0267,"distance_m":40.0,"valid":true,"measurement_time":null,
 "protocol":"ranging_tokenbus"}
```

(the numbers above only illustrate the format). `node`, `peer_a` and `peer_b`
are DESERT addresses (1-based, file order). Unavailable measurements are
`null` with `valid: false`. The native API does not expose the age of a
measurement, so `measurement_time` is always `null` and a retained valid
estimate must not be read as a fresh measurement. HoloOcean distances remain
ground truth and are never reported as ranging. A demo scenario is provided in
`src/holo_desert/resources/demos/e07_ranging_tokenbus/scenario.yaml`.

```yaml
name: ranging_three_nodes
description: Ranging-TokenBus with three static nodes.
duration: 150
physics_hz: 10
nodes:
  - {id: auv_01, position: [0, 0, -30]}
  - {id: auv_02, position: [40, 0, -30]}
  - {id: auv_03, position: [0, 60, -30]}
network:
  mac: {protocol: ranging_tokenbus}
flows:
  - {source: auv_01, destination: auv_03, start: 5, stop: 120, interval: 20, payload_bytes: 16, ttl: 60}
```

Ranging TDMA and TDOA are not integrated (see below).

## Native applications (UW/CBR, UW/VBR)

Status: operational (native and HoloOcean end-to-end tests), YAML/API only.

`generator: desert_cbr` or `desert_vbr` makes DESERT's own timers generate the
packets. The bridge creates, on every node, one project subclass
(`Module/UW/CBR/HOLO` or `Module/UW/VBR/HOLO`) per flow on its own UDP port,
sharing the existing UDP/routing/IP/MAC/PHY stack; it starts the source
instance at `start` and stops it at `stop` (default: scenario `duration`).

| Flow field | Native binding |
|---|---|
| `interval` | CBR `period_`; VBR `period1_` |
| `native_packet_bytes` (16–2048) | `packetSize_` |
| `pattern: poisson` | `PoissonTraffic_ 1` (`periodic`: 0) |
| `native_period2_s` | VBR `period2_` |
| `native_duration1_s`, `native_duration2_s` | VBR `timer_switch_1_`, `timer_switch_2_` |

Restrictions: `message_type: data`, no `reply`, `pattern` `periodic` or
`poisson`, no `final_interval`. Native packets carry no JSON envelope and no
Python TTL (`python_ttl_applies: false`): they never time out in Python, and
the run summary leaves goodput/envelope throughput empty (`null`) when native
flows are present (`native_application.packet_throughput_bps` is reported
instead). Events:
`native_app_tx`, `native_app_rx` with `native_packet_id` (`native:<flow>:<source>:<serial>`).

```yaml
name: native_generators
description: Native CBR and VBR timers in DESERT.
duration: 60
nodes:
  - {id: auv_01, position: [0, 0, -20]}
  - {id: auv_02, position: [30, 0, -20]}
flows:
  - {source: auv_01, destination: auv_02, generator: desert_cbr, interval: 4, native_packet_bytes: 64, start: 2, stop: 50}
  - {source: auv_02, destination: auv_01, generator: desert_vbr, pattern: poisson, interval: 5, native_packet_bytes: 64, native_period2_s: 2, native_duration1_s: 10, native_duration2_s: 10, start: 2, stop: 50}
```

## Modules installed but not integrated

These modules are present in the pinned image (source and compiled library)
but cannot be selected. "Not integrated" does not mean impossible: each needs a
dedicated adapter and validation. Load failures do not prove that a library is
missing: the installed Tcl loads plugins with `RTLD_LOCAL` and some plugins do
not declare required siblings in `DT_NEEDED`. No library was modified or
recompiled.

| Module | Blocker |
|---|---|
| Polling (`libuwpolling.so`) | Requires coordinator (AUV/sink) and node roles, specific formats and the polling cycle; not adapted to the bridge |
| T-LOHI (`libuwtlohi.so`) | Requires tone handling with PHY/MIV wake-up and dedicated access control; not verified with the bridge PHY. `libuwtlohi.so` loads in isolation, its tracer `libuwtlohiTracer.so` does not (undefined `hdr_tlohi::offset_`) |
| ALOHA-Q, ALOHA-Q-Sync (`libuwalohaq.so`, `libuwalohaqsync.so`) | Learning state, updates, roles and synchronisation not integrated |
| UFetch (`libuwufetch.so`) | Isolated load fails (undefined `hdr_uwcbr::offset_`); roles and native dependencies need a specific adapter |
| ICRP (`libuwicrp.so`) | Load fails: `UWIP_CLMSG_SEND_ADDR` is present but not exported under `RTLD_LOCAL` loading |
| Position-Based routing (`libuwposbasedrt.so`) | `Module/UW/PosBasedRt` loads, but no protocol-admissible distribution of position knowledge is integrated; global ground truth must not be supplied |
| OFDM (`libuwofdmphy.so`) | Dedicated access and framing modules not verified with the bridge envelope |
| HMM (`libuwhmmphysical.so`) | Requires states/tables and a specific PHY; not tested with this bridge |
| Ranging TDMA / TDOA | Need dedicated messages, clocks, initialisation and measurement output; the `RANGING_TDMA` constructor without configured slots caused SIGFPE in the probe (this does not prove the protocol unusable with a valid setup) |
| Real modem drivers / hardware (Ahoi, EvoLogics and other drivers/packers) | Drivers are installed; no modem is detected or mapped in the container and no hardware configuration is verified; hardware, addressing, packing and a real-time scheduler are separate prerequisites |

## Communication profiles

A communication profile is a reusable `network` section.

- CLI profiles (`src/holo_desert/resources/profiles/*.yaml`) are bare `Network`
  documents. `holo-desert run <scenario> --profile acoustic_aloha` replaces the
  scenario's whole `network`, including routes. To change only the MAC while
  keeping everything else, use `--mac`.
- Dashboard profiles are stored as `{name, description, network}`
  (`CommunicationProfile`) under `<library>/profiles`; they are created,
  duplicated, imported and exported as YAML from the dashboard
  ([dashboard.md](dashboard.md#communication-profiles)).

```yaml
# CLI profile: a bare Network document
backend: desert
acoustic: {bitrate_bps: 4800, tx_power_db: 135, frequency_hz: 25000, bandwidth_hz: 5000, propagation: underwater, interference: miv}
mac: {protocol: csma_aloha, ack: false, max_tx_tries: 3, buffer_packets: 100}
routing: static
```

```yaml
# Dashboard profile export (CommunicationProfile)
name: TDMA long frame
description: TDMA with a 6 s frame for 32-byte payloads.
network:
  mac:
    protocol: tdma
    tdma: {frame_duration_s: 6, guard_time_s: 0.1}
```
