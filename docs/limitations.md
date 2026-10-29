# Limitations and verified boundaries

This list states what the software does not model or has not verified. Module
status follows the vocabulary of
[stack-configuration.md](stack-configuration.md#status-vocabulary); the
summary of verified capabilities is in [capabilities.md](capabilities.md).

## Platforms and identity

- Linux host target: Ubuntu 24.04. The graphical verification covers native
  Windows, Ocean 2.3.0 and an NVIDIA GPU. It is not a rendering certification
  for Ubuntu, WSLg, macOS or other GPUs; the Linux setup and unit tests were run
  without GPU rendering.
- DESERT is pinned to the official Linux amd64 image digest. Its internal
  source commit (`12203f3c…`) differs from the commit the public `4.0.0` tag
  resolves to today (`8991214a…`); both are recorded in
  `dependencies.lock.json`. The SDK headers and the compile-only
  `extensions/autoconf.h` (Linux LP64, `RANDOM_RETURN_TYPE long`, `HAVE_STL`,
  checked by a `static_assert`) are valid only for this image; other builds
  require an ABI check.
- One simulation per DESERT service at a time.

## Physical and channel modelling

- Obstacles and the seabed affect HoloOcean physics only; they are not
  converted into acoustic occlusions or bathymetry for DESERT. WOSS uses an
  explicitly synthetic flat seabed and surface with a configured SSP; it
  does not read the Unreal scene or geographic databases.
- Geometry is constant within one physics tick. There is no Doppler, no
  continuous motion during a signal's flight and no retroactive recomputation
  of signals already in flight. Waypoints are controller targets; the channel
  uses only measured positions.
- Each reception is handed to the application at the next (or coincident)
  physics tick, keeping the precise NS timestamp for metrics.
- The acoustic defaults are the bridge profile taken from the official
  examples. E03/E05 power thresholds are qualitative demonstrations of the
  configured model and seed, not a modem or environment calibration.
- The corrected BPSK (`conditional-bpsk-v1`) is a patch of an idealised model,
  not a calibration; it changes the number of RNG draws.
- Optical: experimental gain adapter; receiver optics omnidirectional, no
  receiver field of view or occlusion; offsets affect gain only (delay and
  noise depth use the vehicle COM); the pinned noise LUT limits all positions
  to `-20 <= z < 0`; fixed attenuation constant.
- EM: empirical SF7 CR4/5 PER table, not a calibration for every bitrate,
  frequency or device; antenna gain is constant and ignores pointing.
- WOSS: requires ≥ 1 m horizontal separation between every pair and > 0.1 m
  clearance from surface and seabed (the pinned Bellhop integration aborts on
  vertically aligned links); stationary environment; omnidirectional; only the
  original BPSK.
- Energy consumption is not modelled; total airtime is not energy.
- No real modem hardware, sea trial or field calibration has been performed.

## Protocol stack

- Only one network interface per node, except the experimental multi-PHY
  stack (2–3 acoustic BPSK or optical interfaces, CSMA-ALOHA without ACK,
  static routing). Flows cannot choose an interface. Optical interfaces need
  nodes within 0–20 m depth, automatic switching needs the acoustic interfaces
  before the optical ones, and `STATS` PHY counters cover each node's first
  interface only ([capabilities.md](capabilities.md#mixed-acousticoptical-stacks)).
- No per-node MAC or routing selection, no MAC priority (application priority
  is metadata), no application multicast or group API. Applications send
  unicast; Flooding uses broadcast forwarding internally.
- Flooding is rejected with CSMA/CA and DACAP (no delivery in the native matrix;
  CSMA/CA drops broadcast RTS).
- CSMA-ALOHA in the default `legacy` queue mode has no active native queue
  limit; use `bounded` to enforce `buffer_packets`. CSMA/CA's native queue test
  is inclusive (`queue_size + 1` packets plus the frame in service).
- TDMA/TDMA Frame frame-fit validation is a conservative envelope check, not a
  guarantee of collision freedom; TDMA Frame keeps its native phase, which
  differs from TDMA.
- SUN supports only convergecast to one sink without replies; its cumulative
  counters are class-wide.
- Position-Based routing has static anchors and vehicles only: no direct
  vehicle-to-vehicle link, no moving anchor, no TTL or routing counters; the
  anchors' estimate of a vehicle is its last reported position, (0, 0, 0)
  before its first packet arrives (a packet sent at t = 0 does not count), and
  a vehicle with no anchor in range drops its packets before the MAC.
- Ranging-TokenBus and Ranging-TDMA do not expose measurement age
  (`measurement_time` is always `null`); Ranging-TDMA keeps the last value of a
  pair that lost contact. Ranging-TDMA slots follow the node order.
- Native UW/CBR/VBR packets have no JSON envelope and no Python TTL.
- Modules installed but not integrated (Polling, T-LOHI, ALOHA-Q/Sync, UFetch,
  ICRP, OFDM, HMM, ranging TDOA, modem drivers) are
  listed with their blockers in [capabilities.md](capabilities.md#not-integrated).
- The dashboard Designer has no controls for power events or for per-vehicle
  values of individual multi-PHY interfaces; these are configured through YAML
  or the API.

## Telemetry and interpretation

- Application TTL and priority are application metadata: they do not cancel
  frames already queued in the MAC and do not change MAC priority.
- PHY counters include overheard receptions. `interference_error` is evidence
  of the PHY's interference branch, not a synonym for any timeout; with the
  upstream BPSK it can occur with zero interference. Unsynchronised receptions
  can result from low SNR, overlap or a busy transmitter; the outcome is kept
  per event.
- Per-message retries are not reconstructed; MAC counters are aggregated per
  node. MAC ACKs are not correlated with message IDs.
- The dashboard topology shows application end-to-end receptions, not
  estimated physical links; relays are verified in the message details.
- The MAC queue is sampled once per simulated second.
- Dashboard memory is bounded (500 messages shown, 5000 rows kept, 1000 series
  samples, 200 trajectory points per node, six comparison summaries); the
  complete history is in the run's `events.jsonl` until reset.
- Identical seed and configured trajectories do not imply identical measured
  HoloOcean trajectories.
- The dashboard message inspector shows only what DESERT and the telemetry
  observe. It does not attribute collisions or causes of loss; facts derived by
  matching events are tagged as inferred, and durations are shown only when
  both endpoints are recorded.
- The map replay works on the run held by the dashboard: timed poses (one sample
  per 0.25 s, at most 600 sent per drone) and the events of the latest 500
  messages. Exported ZIPs cannot be reopened for replay; frames that belong to
  no message (MAC control) are not animated. The moving dot marks the elapsed
  share of the recorded TX start → RX end interval, not a simulated wavefront.
- On narrow phone screens the messages table scrolls horizontally.

## Operation

- Pause stops both logical schedulers. Rendering, world loading and the initial
  image build are not simulated time. Stopping during a Docker build waits for
  the current operation or its timeout; it does not interrupt Docker globally.
- Upstream dependencies emit Matplotlib/pyparsing deprecation warnings and some
  Tcl warnings about missing default variables; they are not communication
  losses. Real process errors stop the run.
- On Windows an Unreal process can be reported terminated by
  `GetExitCodeProcess` before its handle is signalled to Python; the adapter
  checks only its own handle and never accepts `STILL_ACTIVE` as a successful
  stop. Final release of kernel/driver objects is the operating system's
  responsibility.
- Only `HoveringAUV` and the `OpenWater` world are offered and verified in the
  editor.

Dated measurements and the commands actually executed are in
[evidence/](evidence/README.md).
