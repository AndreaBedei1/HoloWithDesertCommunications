# Installation

This guide covers the Python package `holoocean-desert` (import name `holo_desert`),
the DESERT engine image and the optional HoloOcean and dashboard components.
For a first diagnosis of a failing installation see
[troubleshooting.md](troubleshooting.md).

## Components and requirements

| Component | Where it runs | Required for |
|---|---|---|
| Python 3.10–3.12 package `holoocean-desert` | Host | Everything |
| DESERT Underwater 4.0 / NS-MIRACLE engine | Docker container (Linux amd64) | Everything; all network decisions are taken here |
| HoloOcean 2.3.0 client and the **Ocean** package of the same version and platform | Host (GPU rendering) | Integrated runs with vehicle physics |
| FastAPI + Uvicorn (`[dashboard]` extra) | Host | Web dashboard only |

DESERT runs exclusively in Docker. It is not installed in a WSL distribution
and NS is never compiled on the host. HoloOcean and Unreal stay on the host.
The project scripts do not change user groups, services or system policies;
install Docker, GPU drivers and system packages following their official
instructions.

Supported targets:

- **Windows (native)**: Docker Desktop in Linux-container mode. Docker Desktop
  needs its own virtualisation backend (WSL2 or Hyper-V, depending on edition
  and configuration); the project itself never calls `wsl` and does not depend
  on a personal Ubuntu distribution.
- **Ubuntu 24.04**: Python 3.12 with `venv`, Git, Docker Engine and Compose with
  access to the daemon, GPU drivers suitable for HoloOcean rendering. Building
  `posix_ipc` from the lock file requires `build-essential` and `python3-dev`.

The engine requires Docker Linux amd64. macOS GPUs, ARM hosts and WSLg
rendering have not been certified. Native HoloOcean rendering on Linux has not
been verified with a GPU host (see [limitations.md](limitations.md)).

## Package dependencies

`pyproject.toml` declares only `PyYAML` and `pydantic` as core dependencies.
Optional extras:

| Extra | Adds | Use |
|---|---|---|
| `dashboard` | `fastapi`, `uvicorn` | `holo-desert dashboard` and `holo-desert run` with its dashboard |
| `test` | `pytest`, `httpx`, `fastapi`, `uvicorn` | Test suite |

HoloOcean is not a pip dependency of the package; it is installed separately
(see [HoloOcean and Ocean](#holoocean-230-and-the-ocean-package)).

## Option A: install from Git

Library and dashboard, without cloning:

```bash
pip install "holoocean-desert[dashboard] @ git+https://github.com/AndreaBedei1/HoloWithDesertCommunications.git@feat/desert-laboratory"
```

Library only (no web dashboard): omit `[dashboard]`. Then build and check the
engine:

```bash
holo-desert engine up
holo-desert doctor            # full check (HoloOcean, GPU, dashboard, ports, engine)
holo-desert doctor --library-only   # skips HoloOcean, GPU and dashboard checks
```

## Option B: development checkout with the pinned lock file

The setup scripts create `.venv`, install `requirements-lock.txt` (exact
versions, with platform markers for `pywin32` on Windows and `posix_ipc` on
Linux), install the project in editable mode with `--no-deps` and, optionally,
the pinned HoloOcean client. The lock file includes the dashboard and test
dependencies.

**Windows (PowerShell, repository root):**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1 -HoloOceanClient "<HoloOcean-2.3.0 folder>\client"
.venv\Scripts\holo-desert.exe doctor
.venv\Scripts\holo-desert.exe probe-holo
.venv\Scripts\holo-desert.exe run e01_chat
```

`setup.ps1` uses `py -3.10` by default; pass `-PythonVersion` to choose another
version or `-Python "<path to python.exe>"` if the launcher is not available.
Activating the virtual environment is not necessary. `ExecutionPolicy Bypass`
applies only to that PowerShell process.

**Ubuntu 24.04:**

```bash
bash scripts/setup.sh
.venv/bin/python scripts/install_holoocean.py
.venv/bin/python -c 'import holoocean; holoocean.install("Ocean")'
.venv/bin/holo-desert doctor
.venv/bin/holo-desert probe-holo
.venv/bin/holo-desert run e01_chat
```

To use an already downloaded client instead:
`HOLOOCEAN_CLIENT=/path/to/HoloOcean/client bash scripts/setup.sh`.

For a development install without the lock file, `pip install -e ".[test]"`
installs the package and the test tools.

## HoloOcean 2.3.0 and the Ocean package

`scripts/install_holoocean.py` installs the HoloOcean client with
`pip install --no-deps`, either from the pinned commit
`byu-holoocean/HoloOcean@49e70552dfd97273b7dfbe755fbe65d7738b24b7` (subdirectory
`client`) or, with `--client <dir>`, from a temporary copy of a local client
directory containing `setup.py`. It never modifies the source tree of that
directory. Because the client is installed without dependencies, its runtime
dependencies come from `requirements-lock.txt`.

After the client, install the Ocean world package through HoloOcean's own
package manager (`holoocean.install("Ocean")`). `holo-desert doctor` requires
`holoocean.__version__ == "2.3.0"` and `Ocean` among the installed packages.
`holo-desert probe-holo` starts the E01 world with two AUVs and runs 30 physics
ticks; this is the actual renderer check (a working `nvidia-smi` alone does not
prove that rendering works).

## The DESERT engine image

`holo-desert engine up` runs `docker compose up -d --build` for the Compose
project `holo-desert`. The image `holo-desert-engine:4.0.0-v2` is derived from
the pinned upstream image

```text
uwsignet/desert:4.0.0@sha256:59c734d2980de64e4b36429c3fb4a60aceb1cb7efc5f9d605f9b7781fbc51ca6
```

and adds the TCP bridge, the stack builder, the Tcl adapters and the compiled
C++ extension `libholobridge.so`. The upstream download exceeds 1 GB
compressed. The first `holo-desert run` also builds the image if no healthy
engine is reachable.

```bash
holo-desert engine up       # build (if needed) and start
holo-desert engine status   # docker compose ps
holo-desert logs            # last 100 lines of the engine log
holo-desert engine down     # stop and remove the service
holo-desert official-sample # run the unmodified upstream test_uwApplication.tcl
```

Engine lifecycle rules:

- A `run` stops the service only if it started it; a service started explicitly
  with `engine up` is reused and left running.
- Each client connection owns a fresh NS process, terminated when the
  connection closes. One simulation runs per service at a time.
- `--no-manage-docker` attaches to an existing service without managing its
  lifecycle.

### Engine fingerprint

At build time the image stores a 16-hex-digit SHA-256 **engine fingerprint**
computed over the files copied into the image: `server.py`, `stack_builder.py`,
the `*_config.py` validators, `communication-catalog.json`,
`desert-inventory.json`, `build-extension.sh` and every file under
`resources/desert/` (bridge Tcl, module adapters, C++ extension). The service
reports it in its `HEALTH` reply and in `engine_info`. The host recomputes it
from the installed package:

- `holo-desert doctor` fails the `desert_engine` check when the fingerprints
  differ;
- a session refuses to start on a mismatching image ("DESERT engine image is
  outdated … rebuild with holo-desert engine up").

This prevents an older image from silently ignoring newer configuration options.

## Ports and directories

| Item | Default | Override |
|---|---|---|
| DESERT engine TCP port (bound to `127.0.0.1` only) | `5555` | `DESERT_PORT` environment variable (used by the Compose file, the client, `doctor` and the tests) |
| Dashboard | `127.0.0.1:8000` | `--port` on `holo-desert dashboard` / `holo-desert run` |
| Personal scenario and profile library (Windows) | `%LOCALAPPDATA%/HoloOceanDESERT/scenarios` | `HOLO_DESERT_SCENARIOS_DIR` |
| Personal scenario and profile library (Linux) | `$XDG_DATA_HOME/holo-desert/scenarios`, else `~/.local/share/holo-desert/scenarios` | `HOLO_DESERT_SCENARIOS_DIR` |

No port is published on external interfaces and Docker creates no persistent
result volume. Ordinary run results live in a temporary directory until they
are exported (see [telemetry-and-reproducibility.md](telemetry-and-reproducibility.md)).

## What `holo-desert doctor` checks

| Check | Skipped by `--library-only` | Passes when |
|---|---|---|
| `os`, `python` | no | Python is 3.10–3.12 |
| `package` | no | reports the installed package version (or "not installed (source tree)") and the module version |
| `dashboard_extra` | yes | `fastapi` and `uvicorn` are importable |
| `docker`, `compose` | no | `docker version` and `docker compose version` answer |
| `holoocean`, `ocean_package`, `gpu` | yes | HoloOcean 2.3.0, Ocean installed, `nvidia-smi` succeeds |
| `port_8000` | yes | free, or already held by a HoloOcean-DESERT dashboard |
| `port_<DESERT_PORT>` | no | free, or held by a healthy DESERT service |
| `desert_base_image` | no | the pinned base image is present locally |
| `desert_engine` | no | a service answers `HEALTH` and its fingerprint matches the package |

`holo-desert doctor --json` prints the same results as JSON. The exit code is
non-zero if any check fails.

## Dashboard versus library-only use

- **Library-only** (`pip install holoocean-desert`): `NetworkSession`,
  `HoloOceanLink`, `ManagedSimulation`, `holo-desert run <scenario> --no-dashboard`
  and `holo-desert engine …` work. See [api.md](api.md).
- **Dashboard** (`[dashboard]` extra): `holo-desert dashboard` and
  `holo-desert run <scenario>` (which serves the dashboard while running). Without
  the extra these commands stop with an explicit message asking to install it.
  See [dashboard.md](dashboard.md).

## Updating or reinstalling

1. Update the package (`pip install --upgrade` of the Git URL, or `git pull`
   followed by the setup script in a checkout).
2. **Rebuild the engine**: `holo-desert engine up`. Any change to the bridge,
   adapters, builder or catalog changes the engine fingerprint, and an outdated
   image is rejected until it is rebuilt.
3. Run `holo-desert doctor` (or `--library-only`).

Personal scenarios and communication profiles are stored outside the package
and survive updates.

The Linux host setup and the unit tests (without rendering) were also executed
in a clean Ubuntu 24.04 container through `scripts/check_linux_package.sh`; this
does not certify native HoloOcean GPU rendering on Linux. The dated records are
in [evidence/](evidence/README.md).
