# Changelog

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
