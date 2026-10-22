# Open items closure — 22 October 2026 (evening session)

Scope: the five open points left by the consolidation run (see
`docs/project-status.md`). Constraints: DESERT takes every network decision;
no Python re-implementation of DESERT protocols; nothing is declared
operational without passing unit, native DESERT, HoloOcean end-to-end and
(for UI) Playwright tests; E01–E06 stay reproducible; isolated test engine
`holo-desert-engine:followup-dev` on `127.0.0.1:5561`, dashboard tests on
port 8011 (never 5555 or 8000).

## Decisions

1. **Engine identity.** `ENGINE_FILES` adds the `Dockerfile` (copied into the
   image) and `probe-sockets.py`; the fingerprint also hashes the base image
   reference (`DESERT_IMAGE` build argument, default = Dockerfile pin = lock
   file). The image records the reference in `engine-base-image`; `HEALTH`
   and `engine_info` report `desert_base_image`; `doctor` checks the expected
   reference is present locally and names both bases on mismatch.
2. **Power events.** `PowerEvent` carries exactly one native unit field:
   `tx_power_db` (acoustic, 0–200), `tx_power_w` (optical, 1e-15–1e4) or
   `tx_power_dbm` (EM, −100–100). The field must match `network.medium`;
   serialisation omits unset fields, so E06 is unchanged.
3. **Designer.** Data-driven from the catalogue: medium selector with optical
   and EM parameter blocks, acoustic propagation selector with WOSS
   parameters and an SSP table, a multi-PHY editor (interfaces, policy,
   initial interface, master/alpha/thresholds, per-node availability), and a
   generator selector per flow (Python, native CBR/VBR with their native
   parameters). Every control shows meaning, unit, default and constraints;
   options that cannot be used are listed disabled with a short reason. New
   Analysis tab for ranging: native estimates against the HoloOcean geometric
   distance, labelled as measurement versus reference. The dashboard server
   imports only the public `holo_desert` API (`ManagedSimulation`,
   `network_catalog`, scenario/profile libraries).
4. **Multi-PHY E2E.** Managed HoloOcean run with the native received-power
   controller and a moving vehicle, plus an attached run with manual
   switching. Mixed acoustic/optical stacks: decided from the native
   controller sources and official samples (module audit).
5. **Remaining DESERT modules.** Integrate only modules whose real DESERT
   implementation can run in the bridge chain with tests at every level;
   document the concrete blocker for the others (audit notes in the session
   notes folder; summary in `docs/capabilities.md`).

## Verification per item

Unit (`-m "not desert and not holoocean"`), native (`-m desert`, isolated
engine), HoloOcean end-to-end (`-m holoocean`), Playwright (Edge). Catalogue,
README and docs change only after the corresponding tests pass.
