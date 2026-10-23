# Project status — release 1.0.0 (23 October 2026)

## State
Release 1.0.0 is on `master`. The library, the web laboratory and the DESERT
engine adapters described in the documentation are verified by the test
suites listed below; anything not verified is listed as such in
[capabilities.md](capabilities.md) and [limitations.md](limitations.md).

## Decisions
- DESERT executes every network behaviour; Python only validates, moves time,
  transports poses and messages and records telemetry. Project patches to
  DESERT models are opt-in and identified (`phy_patch`).
- A module is offered (schema, builder, Designer) only after a native test
  through the bridge; untested combinations are rejected or disabled with a
  reason. Serialised configurations keep the default block of every
  catalogued protocol; only the selected ones reach the generated Tcl.
- Position-Based Routing never receives global ground truth: anchors know
  their surveyed position, vehicles only their own fix.
- HMM PHY is not integrated: its error process ignores geometry within range
  and DESERT ships no usable fitted parameters. Rogers propagation,
  UW/PHYSICAL, ship noise, USR and HERMES are documented candidates with
  their blockers.
- Test workloads on the shared workstation run below normal priority and
  start only when CPU/GPU load leaves headroom for higher-priority simulations.

## Verification of the release (engine fingerprint `6d45c8c445d2b0cb`)
| Suite | Result |
|---|---|
| Unit (`-m "not desert and not holoocean"`) | 186 passed, 1 skipped |
| Native DESERT (`-m desert`, isolated engine) | 163 passed |
| HoloOcean end-to-end (hybrid, Position-Based, multi-PHY, integrated, API) | 7 passed |
| E01–E06 + E04 ALOHA with HoloOcean | identical to the recorded counts (2/2, 24/11, 45/22, 84/23, 3/3, 29/19, 84/0) |
| Playwright (Edge) | 37 of 38 in the gated run; the scenario-editor test failed once under CPU saturation (server connection reset) and passed when repeated |
| GitHub Actions (unit 3.10/3.12, wheel in a clean venv, Chromium frontend) | green on the release commit |

## Open items
- Integrate the documented DESERT candidates after native validation
  (Rogers propagation first, then UW/PHYSICAL).
- HoloOcean rendering on Linux remains unverified.
- The browser suite is sensitive to a saturated CPU (timeouts and connection
  resets of the test server); rerun it when the machine is idle.
