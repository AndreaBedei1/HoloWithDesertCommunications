# Web dashboard

The dashboard is an optional web laboratory for running scenarios, inspecting
messages and configuring the network. It requires the `[dashboard]` extra (see
[installation.md](installation.md)).

```bash
holo-desert dashboard                 # idle server; choose a scenario in the browser
holo-desert run e03_mobility          # start a scenario and serve the dashboard while it runs
holo-desert dashboard --port 8010 --no-manage-docker
```

Open `http://127.0.0.1:8000` (or the chosen `--port`). Opening the page does not
start a simulation. `Ctrl+C` closes the server and cleans up the current run.

**It is not a second communication engine.** The dashboard server is a client
of the public library API only (`from holo_desert import …`; a unit test rejects
any other import): every run it starts is a `ManagedSimulation`, the class
also used by `holo-desert run`, and the module catalogue, scenario library and
profiles come from `network_catalog()`, `ScenarioManager` and `ProfileLibrary`.
The browser polls `GET /api/state` every 500 ms and renders the run's telemetry
snapshot; there is no separate frontend server and no Python network fallback.
All delivery, loss and timing come from DESERT.

The user interface is in Italian. Labels are quoted below in Italian with an
English gloss.

## Running a scenario

The home page lists the six bundled examples with a description, what to
observe, number of vehicles and duration, plus the personal library ("I miei
scenari"). **Come funziona** (How it works) and the `?` icons explain
operations and terms.

Execution modes ("Motori dell'esperimento"):

- **HoloOcean e DESERT** (integrated): native HoloOcean on the host and DESERT
  in Docker.
- **Solo DESERT** (DESERT only): fixed configured positions, no physics; not
  available for scenarios with movement or coordination.

Controls: start, **Pausa** (pause both simulators at a barrier; resume continues
from the same clocks), **Arresta** (stop), reset, **Riesegui** (re-run with the
configuration applied to the previous run). During start-up the state of both
services is shown; `stopping` includes teardown and reset/new start wait for
it. Errors show a short explanation, expandable details and a diagnostic
command (`holo-desert logs`). One run is active at a time; a second start is
refused with HTTP 409.

## Simulation view

The **Simulazione** view combines the map, communications, contextual details
and the latest messages.

- The XY map uses equal scales on both axes. Positions, orientation, depth and
  3D distances come from HoloOcean sensors (or the fixed fixture in DESERT-only
  mode). Mouse wheel zooms, drag pans, **Adatta mappa** fits the view. Travelled
  trajectories are distinct from the editor's desired waypoints. The browser
  does not replace HoloOcean's 3D world.
- Selecting a vehicle shows its information; selecting a message isolates its
  path and timeline. Blue arrows follow the observed PHY TX/RX of that message;
  the final application delivery is a dashed green arc with its timestamp. Past
  PHY arrows reappear only when the message is selected.
- **Livelli** (layers) can show the configured static routes (grey, dashed,
  off by default; default next hop = destination). Configured routes do not
  guarantee reachability.

**Topology semantics.** Edges drawn from the run data are **application
end-to-end receptions** (`source → receiver`, evidence `application_receive`),
not physical links inferred from proximity and not one-hop claims. A relay is
verified in the message details through the observed `forward` and PHY events.
A past delivery does not certify that a link is still available. PHY
receptions of packets addressed to other vehicles stay in the details and do
not create graphical deliveries.

Headline indicators:

- **Generati** (generated): messages created by the applications.
- **Ricevuti** (received): application deliveries within TTL.
- **Consegna riuscita** (delivery success): `received / (received + timed out)`;
  pending messages are excluded.
- **Latenza media** (mean latency): cumulative mean from generation to
  delivery in NS simulated time.

Map times are absolute simulated times; latency is reception minus generation.
See [telemetry-and-reproducibility.md](telemetry-and-reproducibility.md) for the
definitions.

## Messages (Packet Inspector)

**Messaggi** filters by vehicle, destination, type, status and, optionally,
technical event. Details show only the phases actually observed, separating
application, network forwarding and PHY, with the original JSON, payload and
envelope, counters and the complete event list expandable.

- A generated message is not necessarily transmitted; "transmission observed"
  describes history, not an active radio.
- MAC queue and discards are aggregated per node, not per message.
- A PHY error does not prove the final application loss; a TTL expiry means no
  delivery within the validity window, cause unknown.
- The upstream second noise test with zero interference is labelled
  explicitly; `N/D` means not observable, never zero.
- MAC acknowledgements are not correlated with individual message IDs; the
  per-message trace describes the application DATA frames.

## Analysis

**Analisi** is split into delivery, acoustic channel, movement and time,
ranging and MAC comparison.

- Goodput: payload bits delivered per second in the sampled interval.
  Envelope throughput: delivered JSON/base64 envelope bits, without PHY/MAC
  headers, ACKs or retransmissions.
- The MAC queue is sampled once per simulated second; intermediate peaks are
  not observed. Gaps and `N/D` are not turned into zeros.
- Delivery metrics are global; select a vehicle for PHY/queue series and a
  vehicle pair for the distance series. Drift is wall time minus simulated time,
  excluding pauses.
- Advanced statistics show per-node counters, effective routes, channel
  events, HOLD/PROCEED transitions and E06 power changes, and **Configurazione
  applicata negli oggetti DESERT**: the classes and bound values read back from
  the native objects at the start of the run (`N/D` when a module does not
  expose a value), to check that the configuration reached DESERT.
- Total airtime is the sum of transmission durations, not the union of channel
  occupancy; overlaps and forwarding can make it exceed the run duration. It is
  not energy.
- **Ranging** shows, for the selected vehicle pair, the native DESERT distance
  estimates (one line per observing vehicle: travel time measured by the
  ranging MAC × configured sound speed) beside the HoloOcean geometric distance
  (grey line, an external reference the protocol does not know), and a table
  with the latest estimate, travel time, reference distance and difference per
  observer and pair. Estimates are read once per simulated second; the native
  modules expose no measurement time, so the reference is the latest fleet
  sample at reading time and a stale estimate is shown unchanged. Pairs not yet
  measured are labelled as such. Without Ranging-TokenBus or Ranging-TDMA the
  tab says that no estimate exists.
- In message details, multi-PHY transmissions show the interface used
  (`Interfaccia: short · 2`), and transmission/reception labels name the
  medium (acoustic, optical, EM). Applied power is shown in the medium's unit
  (dB re 1 µPa, W or dBm). Optical and EM receptions whose PHY reports no
  outcome are labelled "esito non esposto dal PHY" instead of a guessed one.

### MAC comparison

In **Analisi → Confronto MAC**: complete an integrated run, press **Conserva
riepilogo corrente** (keep current summary), change only the MAC and repeat. Up
to six summaries are kept in server memory (they survive reset until the server
closes); export the comparison as JSON to inspect the full configurations.

Each retained run stores a configuration fingerprint computed with the
protocol-specific MAC sections removed (common `ack`, `buffer_packets` and
`max_tx_tries` kept, `profile_id` removed), the full configuration, the
versions, the summary and a SHA-256 digest of the observed trajectory. The
comparison is reported as controlled only when all fingerprints match and the
MACs differ; otherwise the differing fields are listed. The same configured
seed and geometry do not imply identical measured trajectories. The comparison
does not start automatic campaigns and does not rewrite applications or
traffic. Only integrated runs (not DESERT-only) can be retained.

## Network Designer

**Impostazioni** (Settings) opens the Network Designer; the same sections are
available in the personal scenario editor.

1. Choose the **Tecnologia** (medium: acoustic, optical, electromagnetic),
   then MAC, PHY (acoustic only) and routing. Every catalogued module is
   listed; those that cannot be used are disabled with a short reason, either
   because they are not integrated (for example "Polling — non disponibile:
   richiede ruoli AUV, sink e nodo che il bridge non assegna") or because they
   conflict with the current choices (for example TDMA with the optical
   medium, Flooding with CSMA/CA, SUN with MAC ACK, the corrected BPSK with
   WOSS). The `?` icon of each selector lists the unavailable options and why.
2. Set the two primary parameters of the medium: bitrate and source level in
   dB re 1 µPa (acoustic), optical power in W, or EM power in dBm (negative
   values allowed).
3. **Impostazioni avanzate** (advanced settings):
   - *Propagazione acustica e ambiente*: analytic DESERT propagation or
     **WOSS / Bellhop** with its origin, bearing, seabed depth, sediment and an
     editable **sound-speed profile** table (2–256 samples from 0 m to the
     seabed; a new sample is inserted before the seabed one). For optical and
     EM this section lists the medium's native parameters instead (receiver
     and transmitter areas, attenuation, photodiode noise, orientation adapter;
     salinity, temperature, antenna gain).
   - *Canale acustico e accesso al mezzo*: PHY and MAC parameters, TDMA slots
     per vehicle (0..N−1; empty = node order).
   - *Interfacce multiple (multi-PHY)*: 2–3 interfaces, each acoustic or
     optical (name, medium, frequency, bandwidth, bitrate, transmit power in
     dB re 1 µPa or W, PHY; empty cells inherit the global values of the
     medium; with an optical interface the shared optical parameters appear
     below the table), the selection policy (manual through the Python API, or
     the native received-power controller with master vehicle, alpha and
     thresholds for both directions between adjacent interfaces, each in the
     received-power unit of the interface left: linear acoustic or W), the
     initial interface and, for manual selection, the interfaces installed on
     each vehicle. The optical medium is unavailable, with the reason, for
     vehicles outside 0–20 m depth and, with the received-power policy, before
     an acoustic interface. Renaming an
     interface updates the initial interface, thresholds and availability.
   - *Routing e relay*: parameters of the selected routing and the static
     route table; with Position-Based routing also the anchor table (anchor
     or vehicle per drone, optional surveyed position) and the anchors'
     next-hop tables.
   - *Override acustici per drone* (acoustic medium only),
     *Flussi applicativi* and the execution mode.
   - Each flow chooses its **Generatore**: Python application messages, or the
     native DESERT CBR/VBR generators with packet size and, for VBR, the second
     interval and the two state durations. Native generators accept only data,
     periodic or Poisson timing and no reply; the Python TTL, payload and reply
     controls are then disabled with the reason, and the native options are
     disabled with the reason while a flow uses replies, bursts or explicit
     events.
4. The `?` icons (pointer, click or keyboard) state meaning, unit, default and
   constraints of every control, from the catalogue; an allowed range is not a
   recommended value.
5. **Applica alla prossima corsa** (apply to next run). The configuration is
   validated by the server and again in the engine container; errors and
   incompatible combinations block the start. Changes never affect the current
   run.

The JSON editor remains available as an advanced option: **Campi → JSON**,
edit, **JSON → Campi**.

With Flooding, do not keep static routes (forwarding is native broadcast).
Empty per-vehicle overrides inherit the global profile; sound speed stays
shared; per-vehicle MAC/routing is not offered. **Catalogo dei moduli** (module
catalogue) shows every catalogued module with its status, including modules
installed in DESERT but not integrated.

All selectors, parameters, help texts, defaults, bounds and unavailability
reasons come from the catalogue (`/api/network-catalog`, the document the
engine also validates against). Settings the Designer does not cover — power
events and per-vehicle values of individual multi-PHY interfaces
(`interface_overrides`) — remain available in YAML
([stack-configuration.md](stack-configuration.md)), the CLI and the Python
API.

## Personal scenarios

**Nuovo scenario** starts from defaults; **Duplica** copies an example or a
personal scenario without altering the original. The editor has five steps:

1. Name, description, duration, environment; physics rate in the advanced
   options.
2. 2–32 vehicles with unique `auv_NN` IDs, X/Y/Z in metres, yaw in degrees and
   time-ordered waypoints. Depth is −Z. The preview map allows dragging the
   initial positions; it does not show observations of a run.
3. Flows: sender, destination, generator pattern (periodic, Poisson, burst,
   explicit events), interval and payload; start, stop, final interval, TTL,
   message type and reply in the details.
4. MAC, acoustic settings and static routes.
5. Summary, validation and save, optionally followed by an immediate start.

Renaming an ID updates its references; removing a vehicle removes, after
confirmation, the flows, routes and power events that use it. Inconsistent
saves are rejected. Editing is disabled while a run is starting, running,
paused or stopping. Deleting a personal scenario requires confirmation; the
bundled examples are protected, also at the API level.

`OpenWater` and `HoveringAUV` are the only choices offered and verified in the
editor. Imported YAML keeps other worlds (they need a compatible HoloOcean
installation). Duplicated heartbeat scenarios keep the two-node coordination
application and accept no additional flows. Imported power events are kept in
full; there is no dedicated editor for them.

**Importa YAML** opens a draft to check and save; **Esporta YAML** downloads the
same pydantic `Scenario` schema used by the CLI. There is no second
configuration format.

Storage: the library directory is described in
[installation.md](installation.md#ports-and-directories) and can be moved with
`HOLO_DESERT_SCENARIOS_DIR`, for example to keep it inside the project:

```powershell
$env:HOLO_DESERT_SCENARIOS_DIR = Join-Path (Get-Location) 'user_scenarios'
.venv\Scripts\holo-desert.exe dashboard
```

Files are ordinary YAML with server-generated IDs (no browser-supplied paths),
unique names, a 256 KiB limit, safe YAML parsing, an inter-process OS lock
(`.library.lock`), write-to-temporary + `fsync` + `os.replace`, and SHA-256
revisions: a concurrent modification returns HTTP 409 and requires reloading.
The CLI also accepts personal IDs (`user_…`) and arbitrary YAML paths.

## Communication profiles

A **scenario** contains vehicles, movement, traffic and network; a
**communication profile** contains only the network, reusable across
scenarios. In **Profili di comunicazione** choose a built-in example (one per
operational MAC, Flooding with TDMA, corrected BPSK) or **Nuovo dalla rete
corrente** (new from the current network), name it and save. Examples can be
duplicated; personal profiles can be edited, duplicated, deleted, imported and
exported as YAML (`{name, description, network}`). Writes are atomic and
revisioned like scenarios.

**Applica rete al progetto** (apply network to project) keeps vehicles,
waypoints and flows; routes and slots must reference the vehicles of the
current scenario, which is checked. The profile is resolved into the run
configuration (its `profile_id` is kept only as provenance), so later edits of
the profile do not change earlier results. Profiles are stored in the
`profiles` subdirectory of the scenario library.

## Results and memory

Ordinary results are temporary. **Esporta risultati** saves the ZIP
(`config.json`, `events.jsonl`, `packets.csv`, `summary.json`); export before
reset or closing.
`holo-desert run --persist DIR` is the CLI option for explicit persistence.
Personal saves concern configurations, not results.

Retained in memory: 500 messages exposed (5000 rows kept), 256 events per
message with declared truncation, 300 topology observations, 200 trajectory
points per node, 1000 series samples, 100 state transitions, 100 recent events
and six comparison summaries. The temporary `events.jsonl` keeps the full
history until reset.

## HTTP API (used by the browser)

| Endpoint | Purpose |
|---|---|
| `GET /api/state` | current snapshot (idle state when no run) |
| `POST /api/start` | `{scenario, standalone, configuration?}`; 409 if a run is active |
| `POST /api/stop`, `/api/pause`, `/api/resume`, `/api/reset` | controls |
| `GET /api/export` | results ZIP |
| `POST /api/validate` | validate a scenario without saving |
| `GET /api/comparisons`, `POST /api/comparison` | MAC comparison |
| `GET /api/scenarios`, `GET /api/scenarios/{id}`, `GET /api/scenarios/{id}/yaml` | bundled and personal scenarios |
| `/api/user-scenarios` (`GET`, `POST`, `PUT /{id}`, `DELETE /{id}?revision=`, `POST /import`) | personal library |
| `/api/network-profiles` (same pattern, plus `GET /{id}/yaml`) | communication profiles |
| `GET /api/network-catalog`, `GET /api/network-inventory`, `GET /api/capabilities` | catalogue, image audit, editor capabilities |

The HTTP API never accepts arbitrary file paths. Static ES modules are served
with an explicit `text/javascript` content type (see
[troubleshooting.md](troubleshooting.md)).

## Verification status

Browser tests (Playwright, `tests/frontend`) cover the dashboard, the Network
Designer and the scenario editor; presentation fixtures intercept requests only
in the browser and are marked by a visible banner, so they do not prove physics
or networking. The dated visual review and real-backend checks are recorded in
[evidence/ui-review.md](evidence/ui-review.md) and
[evidence/desert-laboratory.md](evidence/desert-laboratory.md); screenshots are
in [images/](images/).
