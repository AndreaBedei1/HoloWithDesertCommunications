# Changelog

## 1.1.0 — 2026-10-28

Dashboard and scenario discovery release. Engines, protocols, the E01–E06
configurations and their recorded results are unchanged.

### Added
- `ScenarioManager` discovers all nine bundled scenarios: E01–E06 in
  `resources/examples` (group `reference`) and E07–E09 in `resources/demos`
  (group `demonstration`: `e07_ranging_tokenbus`, `e08_woss`,
  `e09_sun_convergecast`). New `ScenarioManager.group(name)`;
  `list_examples()`, `holo-desert run <id>` and the dashboard accept the demos
  by name.
- `GET /api/scenarios` returns `id`, `group` and `description`;
  `holo-desert examples` prints name, group and description.
- Message inspector with a per-message lifecycle: final status, per-drone
  lane timeline, per-hop outcomes, relays, decoded-by and overheard-by drones,
  each fact tagged observed, inferred or configured; durations only when both
  endpoints are recorded. The selected message's hops are drawn on the map as
  arrows coloured by outcome.
- Message filters by MAC, interface (multi-PHY) and generation time range, in
  addition to drone, recipient, type, status and technical event; the
  selected message persists across the periodic refresh.
- Home page groups the bundled scenarios into "Reference Scenarios" (E01–E06)
  and "Advanced Demonstrations" (E07–E09).

### Changed
- Dashboard, module catalogue and user-facing Python messages are in English.
- Network Designer menus list only operational modules; the full inventory,
  including modules not integrated, remains in the Module catalogue dialog.

## 1.0.0 — 2026-10-23

First stable release of the library and web laboratory. Every network behaviour
is executed by DESERT Underwater 4.0 / NS-MIRACLE; Python validates
configurations, moves time, transports poses and messages and records telemetry.

### Library
- Public API for three modes: standalone DESERT (`NetworkSession`), DESERT
  attached to a HoloOcean environment owned by the caller (`HoloOceanLink`) and
  a complete simulation run by the library (`ManagedSimulation`); the dashboard
  uses the same API.
- Per-node send/receive with callbacks, pose updates, tick-based time control,
  interface selection, transmit power in the medium's unit (per interface with
  multi-PHY), summaries, snapshots, ZIP export and the configuration read back
  from the native DESERT objects (`applied_configuration`).
- Engine identified by a content fingerprint that covers the bridge, adapters,
  builder, catalogue, Dockerfile and pinned DESERT base image.

### DESERT stacks
- MAC: ALOHA, CSMA-ALOHA, TDMA, TDMA Frame, CSMA/CA, DACAP, CS-Burst, TokenBus,
  Ranging-TokenBus, Ranging-TDMA.
- Routing: static multi-hop, Flooding, SUN, Position-Based (static anchors and
  vehicles that know only their own fix; no global ground truth).
- PHY and channel: analytic BPSK (upstream and corrected), WOSS/Bellhop with a
  synthetic sound-speed profile, optical and electromagnetic media.
- Multi-PHY: 2–3 acoustic or optical interfaces under the native multi-stack
  controller, manual or received-power switching.
- Native UW/CBR and UW/VBR generators; native ranging estimates.
- WOSS with every MAC and routing protocol, and the native generators with
  every MAC, routing protocol and medium, are each covered by a native delivery
  test; combinations without such a test are rejected or disabled with a reason.

### Web laboratory
- Network Designer with contextual help (meaning, unit, default, constraints)
  for every parameter and a reason for every unavailable option; personal
  scenarios and communication profiles.
- Map, message timeline with observed paths and interfaces, delivery, channel,
  interface-switching, movement and ranging views, MAC comparison, export.

### Documentation and reproducibility
- English documentation: installation (Windows, Ubuntu), API reference and
  tutorial, stack configuration, capability matrix, limitations,
  troubleshooting, reproducibility guide and `CITATION.cff`.
- E01–E06 reference experiments kept unchanged, with recorded expected counts.
