# Project status — 22 October 2026 (evening)

Branch `feat/desert-laboratory`. The seven consolidation commits up to
`80e0e4b` are on `origin` (pushed at 19:04); the commits of this session are
local and not pushed. Plan: `docs/superpowers/plans/2026-10-22-open-items-closure.md`.

## Decisions taken

* **Engine identity.** The fingerprint now also covers the `Dockerfile` (copied
  into the image), `probe-sockets.py` and the DESERT base image reference
  (`DESERT_IMAGE` build argument, default = Dockerfile pin = lock file). The
  image records the reference; `HEALTH` and `engine_info` report
  `desert_base_image`; `doctor` checks the expected base locally and names both
  bases on a mismatch. A unit test keeps `ENGINE_FILES` and the `COPY` line
  aligned.
* **Power events** carry exactly one value in the medium's unit:
  `tx_power_db` (acoustic), `tx_power_w` (optical) or `tx_power_dbm` (EM,
  negative values allowed); a field of another medium is rejected. Unset
  fields are not serialised, so E01–E06 are unchanged.
* **Dashboard on the public API only.** The server and `holo-desert run` use
  `ManagedSimulation`, `network_catalog()`, `network_inventory()`,
  `ScenarioManager`, `ScenarioLibrary`, `ProfileLibrary`; a unit test rejects
  any other import. `ManagedSimulation` gained `run_id`, `holoocean`,
  `versions`, `trajectory_fingerprint()`, `annotate()`, `export_bytes()`; the
  dashboard export now includes `summary.json`.
* **Network Designer** (catalogue-driven): medium selector with optical/EM
  parameter blocks, WOSS parameters with an editable SSP table, a multi-PHY
  editor (interfaces, policy, initial interface, master/alpha/thresholds,
  per-vehicle availability, renames), a generator selector per flow (Python or
  native CBR/VBR with their timers). Every control's help states meaning, unit,
  default and constraints; unusable options are listed disabled with a short
  reason; media, WOSS, native generators and multi-PHY are enabled only while
  the catalogue marks them verified.
* **Ranging view** (*Analisi → Ranging*): native estimates per observer beside
  the HoloOcean geometric distance, labelled as estimate and reference. Message
  details show the multi-PHY interface, medium-specific labels and power units;
  optical/EM receptions without a native outcome are no longer labelled
  "non sincronizzata".
* **Multi-PHY** is experimental and operational: HoloOcean end-to-end tests
  (received-power controller following the real distance; manual switching in
  a caller-owned environment), controller power units documented (linear
  `Pr`), `POWER` acts on the first interface only (native and E2E evidence).
* **Mixed acoustic/optical stacks**: supported by DESERT (official ROV sample,
  prototype through the bridge) but not by this bridge; six concrete blockers
  are documented in `docs/capabilities.md`.
* **Ranging-TDMA integrated** (`Module/UW/RANGING_TDMA`): Tcl adapter, builder
  rules (no ACK, static routing, ≥ 2 packets per slot, slot fit including the
  ranging frame), catalogue entry. Ranging TDOA, HMM, OFDM, T-LOHI, ALOHA-Q,
  Polling, UFetch, ICRP and Position-Based routing stay not integrated, each
  with a source-level blocker (audit notes kept outside the repository).

## Tests executed in this session (Windows 11, Python 3.10.20)

Isolated engines `holo-desert-engine:followup-dev` on 127.0.0.1:5561/5562;
dashboard tests on port 8011. The user's service on 5555 and dashboard on 8000
were not used.

| Suite | Result |
|---|---|
| Unit (`-m "not desert and not holoocean"`) | 157 passed, 1 skipped |
| Native DESERT (`-m "desert and not holoocean"`, fresh engine) | 96/96 on the final image (engine fingerprint `9f7640bc58f4c468`) |
| HoloOcean end-to-end (`-m holoocean`) | 25/25 on the final image (13 min); new: EM negative-dBm power events, multi-PHY received-power and manual switching, Ranging-TDMA, ranging estimates through the dashboard API |
| Playwright frontend (Edge) | 31/31 (7 new: media, WOSS/SSP, multi-PHY, native generators, help completeness, ranging view, interface labels and power units) |

GitHub Actions was not run (no push).

## Review findings resolved in this session

* `ENGINE_FILES` now includes the `Dockerfile`, and the base image reference is
  part of the fingerprint and of `engine_info` (`desert_base_image`).
* EM power events accept negative dBm (`tx_power_dbm`, −100…100).
* The `t_lohi` catalogue entry now says `loadable: true` (only the optional
  tracer library fails) and states the tone-PHY blocker.
* `test_real_physics_completed_laboratory_paths[desert_cbr|desert_vbr]` asserted
  a Python `rx` observation that native generators never produce (their
  receptions are `native_app_rx`); the check introduced in `18a2b07` could not
  pass for these two cases. The test now checks the received native packet rows
  for them and keeps the `rx` check for the other stacks.

## Open items / next steps

1. Push the branch and check GitHub Actions (owner's approval).
2. Rebuild the user's default engine on port 5555 (`holo-desert engine up`):
   the fingerprint changed again (Dockerfile, catalogue, adapters).
3. Mixed acoustic/optical multi-PHY: implement the six blockers listed in
   `docs/capabilities.md` (per-medium channel registry, medium-aware interface
   factory, schema with per-interface medium and units, optical observer
   `interface_index_` and outcome, per-interface POWER/POSITION/STATS, master
   signalling period).
4. HMM PHY (Markov links per directed link, `Module/UW/INTERFERENCE`) and OFDM
   (needs an OFDM MAC adapter) are the next feasible module integrations.
5. The Playwright scenario-editor test "duplicate E03 …" waits 5 s for a save;
   it failed once while another simulator saturated the CPU and passed in the
   two later full runs.
6. Linux GPU host for HoloOcean rendering validation is still unavailable.

## Local resources created by this session

Docker image `holo-desert-engine:followup-dev` (built from this branch). Remove
it with `docker image rm holo-desert-engine:followup-dev` when no longer
needed; its test containers were removed at the end of the session.
