# Reproducibility

This page lists what is needed to repeat the results reported in this
repository and what each run records. Results are model observations of DESERT
Underwater 4.0 driven by HoloOcean 2.3 vehicle physics; they are not modem or
sea-trial measurements. How to cite the software: [`CITATION.cff`](../CITATION.cff)
(please also cite HoloOcean and DESERT, listed there).

## Pinned components

| Component | Version used for the recorded results | Where it is pinned |
|---|---|---|
| Source code | `master` (release 1.1.0); cite the exact commit you ran (`git rev-parse HEAD`) | Git |
| Python packages | Python 3.10.20 on Windows (CI: 3.10 and 3.12 on Ubuntu 24.04) | `requirements-lock.txt`, `pyproject.toml` |
| HoloOcean client | 2.3.0, commit `49e70552dfd97273b7dfbe755fbe65d7738b24b7` | `dependencies.lock.json`, `scripts/install_holoocean.py` |
| HoloOcean world | Ocean package 2.3.0, world `OpenWater` | installed with `holoocean.install("Ocean")` |
| DESERT base image | `uwsignet/desert:4.0.0@sha256:59c734d2980de64e4b36429c3fb4a60aceb1cb7efc5f9d605f9b7781fbc51ca6` (DESERT source commit `12203f3c…` inside the image) | `resources/docker/Dockerfile`, `dependencies.lock.json` |
| Engine image | built locally from the base image and this repository; identified by its 16-hex engine fingerprint (bridge, adapters, builder, catalogue, Dockerfile and base image) | `holo-desert doctor`, `engine_info` |
| Browser tests | Node 24, Playwright 1.64.1 (Edge on Windows, Chromium on Linux) | `tests/frontend/package-lock.json` |

Hardware and OS of the recorded runs: Windows 11 Enterprise (build 26200),
NVIDIA RTX 6000 Ada (driver 597.16), Docker Desktop 29.8.2. HoloOcean rendering
on Linux has not been verified (see [limitations.md](limitations.md)).

## Steps

```bash
git clone https://github.com/AndreaBedei1/HoloWithDesertCommunications.git
cd HoloWithDesertCommunications
git checkout <commit to reproduce>
```

Then follow [installation.md](installation.md) (Option B, the pinned lock
file), build the engine and check it:

```bash
holo-desert engine up
holo-desert doctor        # the engine fingerprint must match the package
```

Run the test suites (heavier suites need Docker and, for `-m holoocean`,
HoloOcean with a GPU):

```bash
python -m pytest -q -m "not desert and not holoocean"     # unit
python -m pytest -q -m "desert and not holoocean"         # real DESERT engine
python -m pytest -q -m holoocean                          # HoloOcean + DESERT end to end
cd tests/frontend && npm ci && npx playwright test --config playwright.config.cjs
```

Repeat the reference examples and compare with the recorded counts in
[telemetry-and-reproducibility.md](telemetry-and-reproducibility.md#recorded-results):

```bash
python scripts/validate_examples.py e01_chat e02_multi_node e03_mobility e04_congestion e05_multihop e06_coordination --output e01-e06.json
python scripts/validate_examples.py e04_congestion --mac aloha --output e04-aloha.json
```

With the engine fingerprint of the commit you run, the DESERT results of
E01–E06 are deterministic for a given seed (`network.seed`, default 1, used as
the RNG substream). Vehicle trajectories come from HoloOcean's physics: the
recorded runs reproduced the same message counts, but positions can differ
slightly between runs. `ManagedSimulation.trajectory_fingerprint()` gives a
SHA-256 per vehicle of the observed fleet telemetry (the dashboard keeps it
with each run retained for comparison) to make such differences visible.

## What every run records

The export ZIP (`holo-desert run … --persist DIR`, `ManagedSimulation.export`,
`NetworkSession.export`, dashboard **Export results**) contains:

- `config.json`: the validated scenario as run;
- `events.jsonl`: every event, including `run_started.versions` (package,
  HoloOcean, engine), `engine_info` (DESERT release and source commit, base
  image, engine fingerprint, PHY patch identifiers, effective network and
  per-node stack) and the `native_bindings` read back from the native DESERT
  objects at t = 0 (classes and bound values actually in use);
- `packets.csv` and `summary.json`.

Ordinary dashboard runs live in a temporary directory: export them before
resetting. The provenance fields are described in
[telemetry-and-reproducibility.md](telemetry-and-reproducibility.md#provenance).

## Shared machines

The suites can share a workstation with other simulators. On the reference
machine they ran below normal priority on a few cores, one HoloOcean instance
at a time, with engine containers limited to one CPU
(`docker run --cpus=1 --memory=2g …` against `DESERT_PORT`), and HoloOcean's
GPU load was checked before each end-to-end run. Results do not depend on wall
time: the logical clock advances by whole physics ticks.
