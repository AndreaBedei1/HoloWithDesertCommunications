# Project status — 22 October 2026

Branch `feat/desert-laboratory` (local commits, not pushed). Scheduled
consolidation session; continue from here.

## Decisions taken

* The library is the primary product. Public API in `src/holo_desert/api.py`,
  exported from `holo_desert`: `NetworkSession` (standalone DESERT, caller
  drives poses/time), `HoloOceanLink` (attach to a caller-owned HoloOcean
  env), `ManagedSimulation` (the dashboard orchestrator as a library call).
  The dashboard keeps using `SimulationOrchestrator`; no second engine.
* fastapi/uvicorn moved to the optional `[dashboard]` extra; core deps are
  PyYAML + pydantic. Version 0.2.0.
* The engine image now carries a content fingerprint of bridge, Tcl adapters
  and Stack Builder (`engine_fingerprint`). Client and `doctor` reject a
  mismatching (stale) service. `CATALOG_VERSION` alone had let an image built
  before the multi-PHY/WOSS/optical work pass silently.
* Catalog statuses follow executed evidence only (see `docs/capabilities.md`).
  TokenBus, CS-Burst, Ranging-TokenBus and SUN are now in the Network
  Designer; WOSS, optical, EM, native CBR/VBR are verified end-to-end but
  configurable from YAML/API only; multi-PHY is native-verified only.
* CI frontend: unused Microsoft/Azure apt sources are removed before
  `playwright install-deps` (HTTP 403 root cause) with apt retries; tests are
  not skipped. New `package` job builds the wheel and runs the external check.
* README rewritten in English; technical docs consolidated in English
  (`docs/index.md`); Italian validation reports moved to `docs/evidence/`.

## Tests executed in this session (Windows 11, Python 3.10.20)

| Suite | Result |
|---|---|
| Unit (`-m "not desert and not holoocean"`) | see final run below |
| Native DESERT on a freshly built isolated engine (port 5560) | 83/83 before this session's additions; + public API (5) and demos (2) |
| HoloOcean E2E (`tests/end_to_end`) | 17/19 first run; the 2 failures were test assumptions (optical/EM, see commit 18a2b07); 19/19 after fix + 2 new API E2E tests |
| Playwright frontend (Edge) | 24/24 |
| Clean wheel install (fresh venv, Windows) | core deps only; `examples/external_app/check_install.py --engine` OK |
| Dashboard HTTP + browser check | new MACs/SUN selectable with help; e07/e09 runs finish, services stopped |

Final numbers of the closing run are in the session report / commit log.

## Open items / next steps

1. Push the branch and check the GitHub Actions run (frontend fix and new
   `package` job are unverified on GitHub). Requires the owner's approval.
2. Rebuild the user's default engine: the service on port 5555 predates the
   last commits (`holo-desert doctor` reports "Engine image is outdated").
   Run `holo-desert engine up` (rebuilds `holo-desert-engine:4.0.0-v2`).
3. Dashboard: expose `network.medium`, `acoustic.propagation`/WOSS SSP,
   multi-PHY and native generators in the Designer (catalog `selectors`
   already describe medium/propagation/SSP; `configuration.js` ignores them).
   Add a ranging view and per-interface labels in the message timeline.
4. Multi-PHY: add a HoloOcean E2E test; document controller power units.
5. Not integrated (documented blockers): Polling, T-LOHI, ALOHA-Q, UFetch,
   ICRP, Position-Based, OFDM, HMM, ranging TDMA/TDOA, hardware modems.
6. Linux GPU host for HoloOcean rendering validation is still unavailable.

## Local resources created by this session

Docker containers `holo-consolidation-qa` (127.0.0.1:5560) and
`holo-consolidation-qa2` (127.0.0.1:5561) from image
`holo-desert-engine:consolidation-dev`; safe to remove with
`docker rm -f holo-consolidation-qa holo-consolidation-qa2`.
