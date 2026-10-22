# Capability matrix

This matrix records what has been **executed**, not what is installed. A
module counts as available only when a configuration built by this project
makes the real DESERT/NS-MIRACLE module exchange packets through the bridge
and the corresponding tests pass. Source presence, a compiled library or a
successful Tcl `load` alone do not qualify.

Evidence base: 22 October 2026, engine built from this branch on
`uwsignet/desert:4.0.0@sha256:59c734d2…51ca6` (DESERT source commit
`12203f3c`), HoloOcean 2.3.0 + Ocean on Windows 11 with an NVIDIA RTX 6000 Ada,
Docker Desktop 29.8.2. The running engine identifies itself by the
`engine_fingerprint` reported in `engine_info`; `holo-desert doctor` checks it.
The machine-readable version of this table is
`src/holo_desert/resources/docker/communication-catalog.json` (also served at
`/api/network-catalog` and shown in the dashboard's module catalog).

Legend — **Native**: tests in `tests/integration` drive the real engine through
the bridge (`pytest -m desert`). **E2E**: the stack ran inside a HoloOcean
co-simulation (`pytest -m holoocean`, `tests/end_to_end`). **Designer**:
selectable in the dashboard's Network Designer, verified by the Playwright
suite (`tests/frontend`); every verified stack is also configurable from YAML
(scenario import) and from the Python API. Options that cannot be combined
with the current choices, or that are not integrated, are shown disabled with
a short reason.

## Operational

| Area | Selection | DESERT implementation | Native | E2E | Designer | Notes |
|---|---|---|---|---|---|---|
| MAC | `aloha`, `csma_aloha` | `Module/UW/ALOHA`, `Module/UW/CSMA_ALOHA` | yes | yes | yes | historical E01–E06 configuration; ALOHA buffer limit keeps the legacy (non-finite queue) behaviour unless `queue_mode: bounded` |
| MAC | `tdma`, `tdma_frame` | `Module/UW/TDMA`, `Module/UW/TDMA_FRAME` | yes | yes | yes | frame must fit the physical envelope; guard < slot; no ALOHA ACK |
| MAC | `csma_ca`, `dacap` | `Module/UW/CSMA_CA`, `Module/UW/DACAP` | yes | yes | yes | RTS/CTS handshakes; not combinable with Flooding (CSMA/CA rejects broadcast RTS in `stateRxRTS`) |
| MAC | `tokenbus`, `csburst` | `Module/UW/TOKENBUS`, `Module/UW/CSBURST` | yes | yes | yes | StaticRouting only; no ALOHA ACK option |
| MAC + ranging | `ranging_tokenbus` | `Module/UW/RANGING_TOKENBUS` | yes | yes | yes | `ranging_estimate` events: native one-way travel time × configured sound speed; `measurement_time` is not exposed natively and stays `null` |
| MAC + ranging | `ranging_tdma` | `Module/UW/RANGING_TDMA` (native UwTDMA subclass) | yes | yes | yes | slots follow the node order (no slot assignment); each own slot starts with a native ranging frame of 4·(N−1)+2 bytes, so `max_packets_per_slot ≥ 2`; every node estimates every pair (direct and relayed values); StaticRouting only, no ACK; estimates are never aged by the module |
| Routing | `static` | `Module/UW/StaticRouting` | yes | yes | yes | direct and multi-hop routes; loops rejected; a route does not guarantee reception |
| Routing | `flooding` | `Module/UW/FLOODING` | yes | yes | yes | with ALOHA, CSMA-ALOHA, TDMA, TDMA Frame |
| Routing | `sun` | `Module/UW/SUNNode` / `SUNSink` | yes | yes | yes | convergecast to one sink; CSMA-ALOHA without MAC ACK; routes chosen by native probes (`probe_min_snr_db`) |
| PHY | `bpsk_upstream` | `Module/MPhy/BPSK/Underwater` (observer subclass) | yes | yes | yes | analytic Underwater propagation (Thorp), MIV interference |
| Applications | Python generators (periodic, Poisson, burst, events, request/reply, heartbeat) and API messages | `Module/UW/APPLICATION` bridge over UDP/IP/MLL | yes | yes | yes | unicast only; application TTL is a validity window, not a MAC deadline |
| Propagation | `acoustic.propagation: woss` | `WOSS/Module/Channel`, `WOSS/MPropagation`, WOSS BPSK + Bellhop | yes | yes (`demos/e08_woss`) | yes | synthetic flat environment with configured SSP (editable table in the Designer) and one sediment; no bathymetry/geographic databases; vertical links rejected (Bellhop abort guard) |
| Applications | flow `generator: desert_cbr` / `desert_vbr` | `Module/UW/CBR/HOLO`, `Module/UW/VBR/HOLO` (observer subclasses of the native CBR/VBR modules) | yes | yes | yes | native timers; Python TTL does not apply |
| Interfaces | `network.multiphy` (`manual` or `received_power`) | `Module/UW/MULTI_STACK_CONTROLLER_PHY[_MASTER/_SLAVE]` | yes | yes | yes | **experimental**: 2–3 acoustic BPSK or optical interfaces, CSMA-ALOHA without ACK, StaticRouting; thresholds in the received-power unit of the interface left (linear acoustic power, or W for optical); `POWER` changes the named interface, by default the first; see [Mixed acoustic/optical stacks](#mixed-acousticoptical-stacks) |

## Experimental, verified

| Area | Selection | DESERT implementation | Native | E2E | Designer | Notes |
|---|---|---|---|---|---|---|
| Medium | `medium: optical` | `UwOpticalPhy`, `UwOpticalMPropagation`, optical channel + noise LUT | yes | yes | yes | body-frame Lambert–Beer gain adapter; depth limited to 0–20 m by the pinned noise LUT; no receiver FOV/occlusion |
| Medium | `medium: em` | EM channel/propagation/antenna + patched PHY `em-power-lut-v1` | yes | yes | yes | patch fixes the LUT end-iterator and percent/probability handling; default 868 MHz decodes only up to ≈2 m in fresh water; power events in dBm, negative values included |
| PHY | `bpsk_corrected` | project class `…/HOLO/Corrected` (`conditional-bpsk-v1`) | yes | yes | yes | statistical correction of the interference branch; not a modem calibration |
| Routing | `routing: position_based` | `Module/UW/PosBasedRt` (anchors), `Module/UW/PosBasedRt/ROV` (vehicles) | yes | test added, not run yet | test added, not run yet | no global ground truth: anchors know only their surveyed position, tables and the vehicle states carried by received headers; a vehicle knows only its own fix and the anchors' surveyed positions; estimate held at the last report; CSMA-ALOHA, analytic acoustic, one interface |

The HoloOcean evidence for multi-PHY is `tests/end_to_end/test_multiphy_holoocean.py`:
with the native received-power controller, the master moved from `long` to
`short` while the other vehicle hovered 30 m away and back to `long` after
HoloOcean drove it beyond about 100 m; a caller-owned HoloOcean environment
switched interfaces manually through `select_interface`.

## Mixed acoustic/optical stacks

**Experimental, verified natively and in the Network Designer**
(`tests/integration/test_hybrid_multiphy_stack.py`,
`tests/frontend/network-designer.spec.cjs`); the HoloOcean end-to-end test is
`tests/end_to_end/test_hybrid_holoocean.py`. A multi-PHY interface may be
`medium: optical`. Each optical interface gets its own
`Module/UW/OPTICAL/PHY/HOLO` observer, `Module/UW/OPTICAL/Propagation/HOLO`
and noise LUT, as `medium: optical` does, and all optical interfaces share one
`Module/UW/Optical/Channel`, separate from the acoustic channel. One MAC and the
native multi-stack controller sit above both media, as in the official DESERT
sample `test_uwmultiphy/test_uwmultiphy_ctr_rov.tcl`.

Observed through the real bridge:

- manual selection delivers on each medium within its own range: optical at
  10 m (`rx_end` `decoded`), not at 100 m (`rx_start`
  `below_acquisition_threshold`), acoustic at 100 m;
- the received-power master moves to optical when the averaged acoustic power
  exceeds 10^13 (about 14 m) and returns to acoustic when the optical power
  falls below 3·10^-8 W (about 28 m); the slave follows the last interface it
  heard, so its first packet beyond the optical range is lost;
- an optical interface may be the node's first interface; `POWER` with an
  interface index changes that interface in its own unit (W for optical);
- `native_bindings` report every interface with its class, medium and values.

Limits: the optical interfaces need nodes between 0 and 20 m depth (noise
LUT); with `received_power` acoustic interfaces must precede optical ones; the
`STATS` PHY counters still come from each node's first interface (per-interface
outcomes are in the PHY events); CSMA-ALOHA timers are tuned for acoustic links
and also apply to the optical interface; EM interfaces are not offered.
Without the master's signalling period, the native received-power statistic is
reset at every transmission of the master, so automatic switching depends on
traffic from the peer.

## Not integrated

| Module | Concrete blocker found |
|---|---|
| Ranging TDOA (`Module/UW/RANGING_TDOA` + `Module/UW/TAP`) | needs a RANGE layer above the MAC and a TAP layer below it, outside the bridge's fixed module chain; its pings share the data MAC queue; in the official sample the per-node mean error reached 198 m (maximum 5992 m) |
| HMM PHY (`Module/UW/HMMPHYSICAL`) | its `setInterference` rejects the bridge's `MInterference/MIV` (needs `Module/UW/INTERFERENCE`); one Markov link object per directed link must be configured; channel-state errors are counted as noise, so observer outcomes need relabelling |
| OFDM PHY (`Module/UW/OFDM/PHY`) | works only with an OFDM MAC: with CSMA-ALOHA the native PHY aborts (`USED BANDWIDTH = 0`, SIGFPE); with `OFDM_ALOHA` it delivered, which needs a new MAC adapter, carrier headers and an OFDM interference model |
| T-LOHI | the MAC looks up a tone PHY (`Module/MPhy/Underwater/WKUP`) and its data PHY by Tcl class name below it; with one PHY the tone PHY id is never set, so the reservation mechanism does not exist |
| ALOHA-Q, ALOHA-Q-Sync | node and sink find their PHYs by discovery tags that the bridge does not set; sharing one PHY for data and ACKs would change the native learning rewards; node/sink roles and convergecast |
| Polling | NODE/AUV/SINK roles with data only node → AUV → sink; the adaptive back-off queries the PHY's lost-packet counter, which the bridge PHY does not answer |
| UFetch | loads only with a global promotion of `libuwip`/`libuwcbr`; three roles and about 17 timing bindings; no official sample in the pinned tree to validate against |
| ICRP | needs the same loader promotion in production plus node/sink roles; no official reference run |
| Real modem drivers (Ahoi, EvoLogics, …) | drivers installed, no hardware mapped or tested; hardware use is outside this simulation package |

## Known limits that apply to every stack

* One interface per vehicle unless multi-PHY is configured; one MAC class per
  network (per-node MAC choice is not supported).
* Geometry is held constant for one physics tick; no Doppler; HoloOcean
  obstacles and seabed are not converted into acoustic occlusion/bathymetry.
* Broadcast/multicast application messages are not offered by the API;
  Flooding uses native broadcast internally.
* Application priority is metadata; TTL does not cancel packets in flight.
* PHY counters include overheard receptions; `interference_error` is a PHY
  observation, not the cause of every timeout. The topology view shows
  application end-to-end deliveries, not inferred physical links.
* The dashboard's ranging view shows native estimates next to the HoloOcean
  geometric distance; the modules expose no measurement time, so the
  comparison uses the latest fleet sample at reading time.
* Rendering and HoloOcean co-simulation were verified on Windows only; the
  Linux path is verified for installation, unit and browser tests.

See [stack-configuration.md](stack-configuration.md) for parameters and
[limitations.md](limitations.md) for the full list.
