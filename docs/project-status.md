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
| Unit (`-m "not desert and not holoocean"`), Windows Python 3.10 | 126 passed, 1 skipped |
| Unit, clean Ubuntu 24.04 container, Python 3.12 (`scripts/check_linux_package.sh`) | 123 passed; `pip check` clean; wheel-only external check OK |
| Native DESERT, freshly built isolated engine | 90/90 full suite; after the review fixes the API, demo, media, WOSS and additional-protocol files were re-run (all passed) |
| HoloOcean E2E (`tests/end_to_end`) | 17/19 first run; both failures were wrong test assumptions (optical/EM), fixed; 19/19 after the fix; the 2 new API E2E tests pass |
| Playwright frontend (Edge, Windows) | 24/24 |
| Clean wheel install in a fresh Windows venv | core deps only; real DESERT round trip with matching engine fingerprint |
| Dashboard over HTTP and in the browser | new MACs and SUN selectable with help icons; e07/e09 runs finish with services stopped; results equal to the library path |

GitHub Actions was not run (no push).

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

Docker image `holo-desert-engine:consolidation-dev` (built from this branch,
used by the isolated test containers, which were removed at the end). Remove it with
`docker image rm holo-desert-engine:consolidation-dev` when no longer needed.

## Review findings still open

* `ENGINE_FILES` does not include the Dockerfile, so changing the base image
  digest does not change the fingerprint; the base digest is not recorded per
  run in `engine_info`.
* Power events (`PowerEvent.tx_power_db`, bounded 0–200) cannot express the
  negative dBm values that are valid for the EM medium.
* The `t_lohi` catalog entry says `loadable: false`, but the inventory probe
  loads `libuwtlohi.so` (only `libuwtlohiTracer.so` fails). It stays not integrated either way.
