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
selectable in the dashboard's Network Designer; every verified stack is also
configurable from YAML (scenario import) and from the Python API.

## Operational

| Area | Selection | DESERT implementation | Native | E2E | Designer | Notes |
|---|---|---|---|---|---|---|
| MAC | `aloha`, `csma_aloha` | `Module/UW/ALOHA`, `Module/UW/CSMA_ALOHA` | yes | yes | yes | historical E01–E06 configuration; ALOHA buffer limit keeps the legacy (non-finite queue) behaviour unless `queue_mode: bounded` |
| MAC | `tdma`, `tdma_frame` | `Module/UW/TDMA`, `Module/UW/TDMA_FRAME` | yes | yes | yes | frame must fit the physical envelope; guard < slot; no ALOHA ACK |
| MAC | `csma_ca`, `dacap` | `Module/UW/CSMA_CA`, `Module/UW/DACAP` | yes | yes | yes | RTS/CTS handshakes; not combinable with Flooding (CSMA/CA rejects broadcast RTS in `stateRxRTS`) |
| MAC | `tokenbus`, `csburst` | `Module/UW/TOKENBUS`, `Module/UW/CSBURST` | yes | yes | yes | StaticRouting only; no ALOHA ACK option |
| MAC + ranging | `ranging_tokenbus` | `Module/UW/RANGING_TOKENBUS` | yes | yes | yes | `ranging_estimate` events: native one-way travel time × configured sound speed; `measurement_time` is not exposed natively and stays `null` |
| Routing | `static` | `Module/UW/StaticRouting` | yes | yes | yes | direct and multi-hop routes; loops rejected; a route does not guarantee reception |
| Routing | `flooding` | `Module/UW/FLOODING` | yes | yes | yes | with ALOHA, CSMA-ALOHA, TDMA, TDMA Frame |
| Routing | `sun` | `Module/UW/SUNNode` / `SUNSink` | yes | yes | yes | convergecast to one sink; CSMA-ALOHA without MAC ACK; routes chosen by native probes (`probe_min_snr_db`) |
| PHY | `bpsk_upstream` | `Module/MPhy/BPSK/Underwater` (observer subclass) | yes | yes | yes | analytic Underwater propagation (Thorp), MIV interference |
| Applications | Python generators (periodic, Poisson, burst, events, request/reply, heartbeat) and API messages | `Module/UW/APPLICATION` bridge over UDP/IP/MLL | yes | yes | yes | unicast only; application TTL is a validity window, not a MAC deadline |

## Operational, configured from YAML or Python only

| Area | Selection | DESERT implementation | Native | E2E | Notes |
|---|---|---|---|---|---|
| Propagation | `acoustic.propagation: woss` | `WOSS/Module/Channel`, `WOSS/MPropagation`, WOSS BPSK + Bellhop | yes | yes (`demos/e08_woss`) | synthetic flat environment with configured SSP and one sediment; no bathymetry/geographic databases; vertical links rejected (Bellhop abort guard) |
| Applications | flow `generator: desert_cbr` / `desert_vbr` | `Module/UW/CBR/HOLO`, `Module/UW/VBR/HOLO` (observer subclasses of the native CBR/VBR modules) | yes | yes | native timers; Python TTL does not apply |
| Medium | `medium: optical` | `UwOpticalPhy`, `UwOpticalMPropagation`, optical channel + noise LUT | yes | yes | **experimental** body-frame Lambert–Beer gain adapter; depth limited to 0–20 m by the pinned noise LUT; no receiver FOV/occlusion |
| Medium | `medium: em` | EM channel/propagation/antenna + patched PHY `em-power-lut-v1` | yes | yes | **experimental** patch (fixes LUT end-iterator and percent/probability handling); default 868 MHz decodes only up to ≈2 m in fresh water |
| PHY | `bpsk_corrected` | project class `…/HOLO/Corrected` (`conditional-bpsk-v1`) | yes | yes | **experimental** statistical correction of the interference branch; not a modem calibration |

## Native-verified, not yet validated in HoloOcean

| Area | Selection | Evidence | Missing |
|---|---|---|---|
| Multi-PHY / switching | `network.multiphy` (`manual` or `received_power`) | `tests/integration/test_multiphy_stack.py`; `examples/multiphy_switching.py` | HoloOcean E2E test; dashboard controls; only 2–3 **acoustic** interfaces with CSMA-ALOHA (no ACK) + StaticRouting. Hybrid acoustic/optical stacks are not supported by the current controller wiring |

## Installed in DESERT but not integrated

| Module | Concrete blocker found |
|---|---|
| Polling | needs AUV/sink/node roles, polling cycle and formats not adapted to the bridge |
| T-LOHI | needs tone/wake-up handling in PHY/MIV; not verified with the bridge PHY |
| ALOHA-Q, ALOHA-Q-Sync | learning state and synchronisation not integrated |
| UFetch | plugin load fails in the probe (native symbols/dependencies, RTLD_LOCAL); roles unresolved |
| ICRP | load fails: `UWIP_CLMSG_SEND_ADDR` unresolved under RTLD_LOCAL |
| Position-Based routing | needs a position-distribution policy permitted by the protocol; global ground truth deliberately not supplied |
| OFDM, HMM PHY | dedicated framing/state tables not verified with the bridge envelope |
| Ranging TDMA / TDOA | constructor without configured slots raises SIGFPE in the probe; headers/measurement output not adapted |
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
* The dashboard visualises ranging estimates only as raw events (export or
  Python API); there is no dedicated ranging chart yet.
* Rendering and HoloOcean co-simulation were verified on Windows only; the
  Linux path is verified for installation, unit and browser tests.

See [stack-configuration.md](stack-configuration.md) for parameters and
[limitations.md](limitations.md) for the full list.
