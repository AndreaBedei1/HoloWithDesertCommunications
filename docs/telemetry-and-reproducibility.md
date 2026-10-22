# Telemetry, metrics and reproducibility

This document defines what a run records, how the reported metrics are
computed (`src/holo_desert/telemetry/collector.py`), what is exported and how
to reproduce the reference examples E01–E06. Telemetry only observes: every
delivery, loss, interference and propagation decision is taken by DESERT.

## Event log

Every run writes `events.jsonl`, one JSON object per line. Each line has
`event`, `time` (logical simulated time in seconds since the start of the run)
and `wall_time` (host wall clock, never used in metrics). Events produced by
the engine carry `origin: "desert"`; the host adds `node_id` (the `auv_NN` name)
next to the numeric DESERT `node` address and, when a payload is recognised,
`packet_id`. Raw `wire_hex` payloads are not written to the log.

### Engine events

| Event | Emitted by | Content |
|---|---|---|
| `engine_info` | `server.py`, at session start | `desert_release`, `desert_source_commit` (Git commit inside the container), `desert_base_image` (base image reference the engine was built from), `stack_builder` (`desert-lab-v2`), `engine_fingerprint`, `phy_patch` (`upstream-original`, `conditional-bpsk-v1`, `native-optical-lambert-beer-body-frame-v1` or `em-power-lut-v1`), `effective_network`, `effective_nodes` (resolved per-node values) |
| `node_info` | `bridge.tcl` | DESERT node address and its MAC address |
| `position_applied` | `bridge.tcl`, every tick per node | `x`, `y`, `z` applied to the DESERT position object (WOSS adds `latitude_deg`, `longitude_deg`, `altitude_m`) |
| `power_applied` | `POWER` command | `tx_power_db`, `tx_power_w` or `tx_power_dbm` |
| `app_tx` | `Module/UW/APPLICATION/HOLO` | message entered the DESERT stack at the source: `destination_address`, `ns_uid` |
| `forward` | `Module/HoloProbe` (below IP) | packet passing downwards through a node, including relays: `source_address`, `destination_address`, `next_hop_address` (→ `next_hop_id`). A forward is not a successful PHY transmission |
| `phy_tx_start`, `phy_tx_end` | observer PHY | data frame; `outcome` `transmitting` / `transmitted` |
| `phy_rx_start` | observer PHY | `outcome`: `synchronized`, `transmitter_busy`, `receiver_busy_overlap`, `wrong_modulation`, `below_acquisition_threshold` |
| `phy_rx_end` | observer PHY | `outcome`: `decoded`, `noise_error`, `interference_error`, `not_synchronized`; plus `positive_interference` and, for the corrected BPSK, `conditional_interference_per` |
| `phy_control_*` | observer PHY | same four events for MAC control frames (RTS, CTS, ACK, token, …) |
| `rx` | application module at the destination | reception in the application module: `source_address`, `network_tx_time`, `ns_uid` |
| `stats` | `STATS`, once per simulated second | per node: `app_sent`, `app_received`, `mac_queue`, `mac_data_tx`, `mac_data_rx`, `mac_error_rx`, `mac_discarded_tx`, `phy_noise_errors`, `phy_interference_errors` |
| `mac_specific_stats` | `STATS` | per node `values` for the MAC's own counters (for example CSMA/CA RTS/CTS, DACAP defer times, TokenBus token counters) |
| `routing_stats` | `STATS` with SUN | `role`, local `values`, class-wide `class_values` |
| `ranging_estimate` | `STATS` with Ranging-TokenBus or Ranging-TDMA | see [stack-configuration.md](stack-configuration.md#ranging-ranging-tokenbus-ranging-tdma); the collector adds `peer_a_id`/`peer_b_id` and keeps, per pair, the estimates of every observer beside the latest HoloOcean geometric distance (`snapshot()["ranging"]`: `series` per pair and `latest` per observer and pair, with `error_m` = estimate − reference) |
| `interface_selected`, `interface_state` | multi-PHY | active interface index and controller state |
| `native_app_tx`, `native_app_rx` | UW/CBR, UW/VBR subclasses | `native_packet_id`, `flow_index`, `packet_bytes`, `creation_time` |

Acoustic PHY events carry `duration_s`, `phy_bits`, `pt`, `pr`, `pn`, `pi`
(normalised linear acoustic powers; `pr`/`pn`/`pi` are `null` on TX events),
`snr_db` (raw `10·log10(Pr/Pn)`, before the SNR penalty), `rx_snr_penalty_db`,
`phy_tx_time`, `phy_rx_time`, `ns_uid`, `packet_type`, `phy_patch_id`,
`transmitter_mac`/`next_hop_mac` (→ `transmitter_id`/`next_hop_id`) and
`interface_index`. Optical/EM PHY events carry `medium`, `power_unit`,
`received_power_unit` (and `noise_unit` for optical) and no `outcome`.

A counter the native module does not expose is `null`, never zero. NS UIDs are
not globally unique across sources; always correlate with the application
`packet_id`.

### Host events

| Event | Meaning |
|---|---|
| `run_selection` | dashboard only: selected `scenario_id` and `profile_id` |
| `run_started` | `versions`, `seed`, `rng_substream`, `scenario_name`, `profile_id`, `mode` (`integrated`, `desert_standalone`, `network_session`, `holoocean_attached`), `node_map` |
| `generated` | an application created a message: `packet_id`, `source`, `destination`, `size` (payload bytes), `wire_size` (envelope bytes) |
| `delivered` | the destination application received it within its TTL: `delay`, `size`, `observed_wall_time` |
| `timeout` | TTL expired without delivery; `cause: "unknown"` |
| `late_receive` | received after its TTL; not counted as delivered |
| `duplicate` | same `packet_id` received again within its validity; ignored |
| `bridge_receive_overflow` | the receiving node's application inbox (1000 entries) was full; distinct from network loss |
| `fleet` | poses of all nodes (at most every 0.1 s simulated) with `origin` (`holoocean`, `standalone_fixture`, `caller`) |
| `metrics` | one sample of the time series (every ≥ 0.5 s simulated) |
| `application_state` | state change of an application (for example HOLD/PROCEED in E06) |
| `run_error`, `cleanup_error`, `run_ended` | failure, teardown failure, final state |

Per-message records (dashboard Packet Inspector, `packets.csv`) move through
`queued` → `in_flight` (after `app_tx`) → `phy_tx_observed` → `received` or
`timeout_unknown_cause`. A generated message is not necessarily transmitted;
"transmission observed" describes history, not a radio that is still active.

## Metrics

| Metric | Definition |
|---|---|
| `generated` | messages created by the applications (Python and native generators) |
| `received` | messages delivered to the destination application within their TTL (plus native packets received) |
| `timed_out` | messages whose TTL expired without delivery |
| `pending` | `generated − received − timed_out` |
| `pdr_resolved` | `received / (received + timed_out)`; pending messages are excluded. Shown in the dashboard as delivery success |
| `pdr_generated` | `received / generated` (summary only) |
| `mean_latency_s` | mean of `delivery time − creation time` over delivered messages, in NS simulated time |
| `goodput_bps` | 8 × user payload bytes delivered / time. In the series: over the last sampling interval; in the summary: over the run duration (`null` if native generators were used) |
| `application_wire_throughput_bps` | the same with the serialised envelope (JSON + base64) bytes; excludes UDP/IP/MAC/PHY headers, MAC ACKs and retransmissions |
| `phy_observations` | counts of `phy_rx_end` outcomes `noise_error`, `interference_error`, `not_synchronized` over **all** receivers |
| `mac_queue_peak` | maximum `mac_queue` among the `stats` samples (once per simulated second); intermediate peaks are not observed |
| `network_metrics` | data/control PHY frames, bits and airtime summed over `phy_tx_start`/`phy_control_tx_start`; `late_received` |
| `mac_stats`, `mac_specific_stats` | last native counters per node |
| `native_application` | native generator counts, received packet bytes and `packet_throughput_bps`; `python_ttl_applies: false` |
| `wall_drift_s` | wall-clock time minus simulated time, excluding pauses |

Interpretation rules:

- A TTL expiry means "not delivered within the validity window, cause
  unknown"; it does not prove a PHY error. Retries are not reconstructed per
  message and collisions are never inferred from missing deliveries.
- PHY error counts include overheard receptions at nodes that are not the
  destination; they are not the number of lost messages.
- `interference_error` from the upstream BPSK with `Pi = 0` is the second
  noise test of the upstream `endRx`, labelled in the dashboard as
  "second PHY test failed (zero interference)".
- The DESERT `app_received` counter precedes the Python TTL check and can
  include late receptions.
- The dashboard shows the most recent 500 messages, 1000 series samples and
  200 trajectory points per node; at most 5000 message rows are retained (older
  resolved rows are pruned) and each row keeps at most 256 events (truncation is
  marked). `events.jsonl` keeps the complete history of the run.

### Message sizes

Three sizes are kept separate:

1. **Payload**: the user bytes (`size`).
2. **Envelope** (`wire_size`): the JSON message v1 with `id`, `version`,
   `source`, `destination`, `message_type`, `creation_time`, base64 `payload`,
   `priority`, `ttl`. `network.max_wire_bytes` (default and maximum 4096) limits
   the whole serialised envelope.
3. **PHY bits** (`phy_bits`): the frame size declared by the native model,
   including the UDP and protocol headers it accounts for. Native control frames
   can be idealised and very small; this is not a measurement of a real modem
   with preamble, coding and hardware framing.

Application `priority` and `ttl` are envelope metadata only: priority does not
change the MAC, and the TTL does not remove a frame already queued in DESERT.

## Time quantities

| Quantity | Where | Meaning |
|---|---|---|
| Absolute time | `time` of every event | NS scheduler time, identical to the HoloOcean logical time at each barrier (`tick / physics_hz`). Map labels in the dashboard show absolute times |
| Transmission duration (airtime) | `duration_s` of `phy_tx_*` | frame bits / bitrate for the acoustic BPSK (verified per interface in the multi-PHY test) |
| Propagation delay | `phy_rx_start.time − phy_tx_start.time` of the same frame | distance / `sound_speed_mps` with the analytic model; Bellhop arrivals with WOSS |
| End-to-end latency | `delay` of `delivered` | delivery time at the destination application − creation time; includes queueing, MAC waiting/handshakes, airtime and propagation of every hop and forwarding |
| Total airtime | `network_metrics.*_airtime_s` | **sum** of transmission durations including retransmissions and forwarding; with overlapping transmissions it can exceed the simulated duration. It is not the union of channel occupancy and not energy |

Synchronisation model: at each tick the measured HoloOcean poses at `t_k` are
sent to DESERT with timestamp `t_k`, application messages generated at `t_k`
are injected, HoloOcean advances one physics tick and DESERT runs its own event
scheduler up to `t_(k+1)`. Geometry is constant within a tick (left-sampled);
signals already in flight keep normal DESERT semantics (no Doppler, no
continuous motion during flight, no retroactive recomputation). An application
receives a delivery at the first tick at or after its NS timestamp, but the
reported latency uses the NS timestamp, not the polling time. Wall time is used
only for pacing (`realtime`) and drift measurement; pausing stops both
simulators at a barrier.

## Exports

| Export | Contents |
|---|---|
| `NetworkSession.export(path)`, `ManagedSimulation.export(path)` / `export_bytes()`, dashboard **Esporta risultati** (`GET /api/export`) | ZIP with `config.json` (the validated scenario as run), `events.jsonl` (complete event log), `packets.csv` (`id`, `source`, `destination`, `size`, `wire_size`, `creation_time`, `status`, `delay` of the retained message rows) and `summary.json` (the summary dictionary above) |
| `holo-desert run … --persist DIR` / `persist=` in the API | keeps `config.json` and `events.jsonl` in `DIR` instead of a temporary directory (`NetworkSession` writes one `run-NNN` subdirectory per start) |

Ordinary runs live in a temporary directory deleted at reset/close; export
before resetting. The dashboard comparison export (JSON) contains, per retained
run, the full configuration, `versions`, a configuration fingerprint, an
experiment digest, the summary and a SHA-256 digest of the observed fleet
trajectory (see [dashboard.md](dashboard.md#mac-comparison)).

## Provenance

| Item | Where it is recorded |
|---|---|
| DESERT base image digest `uwsignet/desert:4.0.0@sha256:59c734d2…51ca6` | pinned in `resources/docker/Dockerfile` (read by the client), `compose.yaml` and `dependencies.lock.json`; recorded per run in `engine_info.desert_base_image` and covered by the engine fingerprint |
| DESERT source commit inside the image | `engine_info.desert_source_commit` (the pinned image reports `12203f3cdba7d85bac78074d1f2ccfddbfb08021`, while the public tag `4.0.0` resolves to `8991214a1379747a2450f0dc4dd69f9173128f90`; both are in `dependencies.lock.json`) |
| Build recipe, bridge/adapter/builder content and base image | `engine_info.engine_fingerprint` (checked against the package before every run) and `engine_info.stack_builder` |
| Patches | `engine_info.phy_patch`, per-event `phy_patch_id`, `run_started.versions.holoocean_adapter_patch` (`windows-ipc-ready-v1` on Windows) |
| Software versions | `run_started.versions`: `platform` (package version), `desert`, `holoocean`, `engine` (the full `engine_info`) |
| Randomness | `run_started.seed` and `rng_substream` (= `network.seed`) |
| Effective configuration | `config.json`, `engine_info.effective_network`, `engine_info.effective_nodes`, `run_started.node_map` |

The hash of the locally built derived image depends on the local build and
does not replace the base digest. Identical seed and configured waypoints do
not guarantee identical measured HoloOcean trajectories; compare the
trajectory digests when this matters. The corrected BPSK changes the number of
RNG draws, so its individual outcomes cannot be matched with the upstream PHY.

## Reproducing the reference examples (E01–E06)

Start a healthy engine first (`holo-desert engine up`; `holo-desert doctor`).

```bash
holo-desert run e01_chat                  # dashboard at http://127.0.0.1:8000
holo-desert run e03_mobility --fast       # no wall-clock pacing, same logical timeline
holo-desert run e04_congestion --fast --no-dashboard   # prints state and counts
holo-desert run e04_congestion --mac aloha             # change only the MAC
holo-desert run e01_chat --standalone     # fixed positions, no HoloOcean (e01, e02, e04, e05)
python scripts/validate_examples.py                     # E02–E06 with HoloOcean, compact summary
python scripts/validate_examples.py e04_congestion --mac aloha
python scripts/validate_channel.py --sweep              # DESERT-only controlled channel checks
python scripts/validate_dashboard.py                    # HTTP path of an idle dashboard
```

`validate_examples.py` attaches to the running engine without managing
Docker; `validate_channel.py` starts the Compose service only if no healthy
engine answers. `--output FILE` saves only an explicit compact summary. `validate_dashboard.py` runs E03, both E04 MAC variants, E05 and E06
sequentially through the HTTP API of an idle dashboard (it is not a browser
rendering test); do not run it while other simulations use the engine.

### Recorded results

The values below are model observations with substream 1 recorded in the dated
validation reports ([evidence/validation.md](evidence/validation.md),
[evidence/consolidation-validation.md](evidence/consolidation-validation.md),
[evidence/desert-laboratory.md](evidence/desert-laboratory.md)); they are not
measurements of a real modem. Validation runs used `--fast`.

| Example | Logical duration | Generated | Delivered | TTL expired | Observation |
|---|---:|---:|---:|---:|---|
| E01 chat | 16 s | 2 | 2 | 0 | request and reply with the same IDs in engine and dashboard |
| E02 multi-node | 25 s | 24 | 11 | 13 | 11 PHY interference-error observations, sampled queue peak 3 |
| E03 mobility | 100 s | 45 | 22 | 23 | distance 19.7 → 76.9 → 20.0 m; loss and recovery observed |
| E04 CSMA-ALOHA | 45 s | 84 | 23 | 61 | sampled MAC queue peak 20 |
| E04 ALOHA (`--mac aloha`) | 45 s | 84 | 0 | 84 | 28 interference-error and 224 not-synchronised PHY observations, queue peak 7 |
| E05 multi-hop | 30 s | 3 | 3 | 0 | 3 forwards observed at B, reception at C |
| E06 coordination | 30 s | 29 | 19 | 10 | HOLD/PROCEED follow the power outage and recovery |

The full regression after the laboratory extension (one run per original
YAML, upstream BPSK) reproduced the same generated/delivered/expired counts for
E01–E06 with zero pending messages.

E03: by generation-time cohort, 5/6 delivered in the first 12 s, 0/15 between
25 and 55 s, 10/10 between 70 and 100 s (105 dB SPL). The diagnosis
([evidence/e03-loss-diagnosis.md](evidence/e03-loss-diagnosis.md)) attributes
the 22 failures of messages generated at 13, 15, …, 55 s to 21 `noise_error`
and 1 second-test `interference_error`, all after actual transmission; the
dominant cause is the BER at 105 dB with the −10 dB receiver penalty on frames
of 1600/1608 bits, worsened by the upstream second noise test.

E04 dashboard metrics (CSMA-ALOHA vs ALOHA, identical configuration except the
MAC):

| Metric | CSMA-ALOHA | ALOHA |
|---|---:|---:|
| PDR (resolved) | 0.27381 | 0 |
| Mean goodput over 45 s [bit/s] | 1046.756 | 0 |
| Mean envelope throughput [bit/s] | 2126.222 | 0 |
| Mean latency of delivered [s] | 5.49942 | n/a |
| PHY interference errors [observations] | 8 | 28 |
| PHY not synchronised [observations] | 16 | 224 |
| Sampled MAC queue peak [packets] | 20 | 7 |

The E04 YAML sets `buffer_packets: 20` with CSMA-ALOHA in the default `legacy`
queue mode, in which the native queue limit is not active (see
[stack-configuration.md](stack-configuration.md#csma-aloha-csma_aloha-default));
the value 20 is therefore a sampled peak, not evidence of an enforced limit.

E05 and controlled channel checks (fixed positions, same payload and
substream): A-B-C with 500 m per hop at 132 dB SPL delivered via B, while the
direct 1000 m A-C link did not deliver the payload (error observed at the PHY).
In the declared power exploration, 100–126 dB did not deliver over the 500 m
hops, 128–135 dB delivered via the relay but not directly at 1000 m, and 136 dB
also delivered directly.

E06: follower HOLD at start, PROCEED at 1.867 s, HOLD at 10.467 s, PROCEED at
18.6 s; the leader's source level is set to 0 dB SPL at 8 s and restored to
135 dB SPL at 18 s inside DESERT.

The E03/E05 thresholds are qualitative demonstrations of the configured model
and seed, not a calibration of a modem or marine environment.
