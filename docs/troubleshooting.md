# Troubleshooting

Start with `holo-desert doctor` (or `holo-desert doctor --library-only`) and,
for engine problems, `holo-desert logs`. A failed run moves to the `failed`
state; no alternative Python delivery is ever activated.

## Docker and the engine

**Docker is not running or does not answer.**
Symptoms: `Docker did not respond within the timeout`, `Docker failed: …`, an
HTTP 500 from Docker before the image pull, or the `docker`/`compose` doctor
checks fail. Check `docker version`; on Windows restart Docker Desktop and make
sure it uses Linux containers. This is a Docker problem, not an acoustic
channel result.

**`Docker CLI unavailable`.** Install Docker Desktop (Windows) or Docker Engine
+ Compose (Ubuntu). On Windows the client also looks for
`%ProgramFiles%/Docker/Docker/resources/bin/docker.exe` and prepends that
directory to `PATH` for its own Docker calls, which also covers a missing
`docker-credential-desktop` on the terminal `PATH`.

**Outdated engine image (fingerprint mismatch).**
Symptoms: doctor reports `Engine image is outdated or built from another base
(service <a> from <base>, package <b> from <base>); run holo-desert engine up`,
or a run fails with `DESERT engine image is outdated or built from another base
(engine <a> from <base>, package <b>): rebuild with holo-desert engine up`. The
running image was built from a different Dockerfile, bridge, adapter, builder,
catalogue or DESERT base image than the installed package expects. Run
`holo-desert engine up` (it rebuilds) after every package update. If the
engine was built with a custom `DESERT_IMAGE`, set the same variable for the
client and `doctor`. If another service was started manually on the same port,
stop it first.

**`DESERT service did not become healthy; run holo-desert logs`.** The container
did not answer `HEALTH` within 30 s after `compose up`. Read the logs; the first
build downloads more than 1 GB.

**`The DESERT service on port … is running another session` / `DESERT is busy`.**
One engine serves one simulation at a time (each session owns one NS process).
Wait for the other run (dashboard, script or test) to finish, or point the
second client to another engine with `DESERT_PORT`.

**`DESERT process/socket closed unexpectedly`, `Invalid or interrupted DESERT
event stream`, `DESERT: {'event': 'error', …}`.** The NS process or the
connection ended. The bridge never puts exception text in the JSON stream; the
actual reason is in `holo-desert logs` (`Holo bridge command failed: …` or
`Session error: …`).

**Port already in use.** Doctor reports `Port <n> is occupied by another
service`; it recognises its own healthy DESERT service and a HoloOcean-DESERT
dashboard on the default ports. Use `DESERT_PORT` for the engine and `--port`
for the dashboard. `holo-desert run` and `holo-desert dashboard` reserve the
dashboard port before starting either simulator, so a busy port fails without
side effects.

**Upstream warnings in the logs.** Matplotlib/pyparsing deprecation warnings and
Tcl warnings about missing default variables come from upstream dependencies.
They are not communication losses; real process errors stop the run.

## HoloOcean

**`holoocean` / `ocean_package` checks fail.** HoloOcean must be exactly 2.3.0
and the `Ocean` package of the same version and platform must be installed
(`holoocean.install("Ocean")`); see [installation.md](installation.md).

**Binary timeout or no rendering.** Check the GPU driver, the Ocean version and
the graphical environment, then run `holo-desert probe-holo` (two AUVs, 30
physics ticks). A working `nvidia-smi` alone does not certify the renderer.

**Windows: intermittent start-up failure (IPC).** In the HoloOcean 2.3 sources
the Windows server releases its LOADING semaphore before creating the SERVER
and CLIENT semaphores, while the client opens them immediately; this produced
Windows error 2 and a world process waiting for commands, before any packet was
generated. The adapter uses a subclass of the official environment on Windows
that waits at most 2 s for both semaphores of its own session UUID (no retry on
permission errors) and keeps ownership of the process if the constructor fails,
so it can close it. If it still fails, the error is `HoloOcean Windows IPC did
not become ready after loading`. Runs record `windows-ipc-ready-v1` in
`run_started.versions.holoocean_adapter_patch`.

**Windows: Unreal process teardown.** A process already terminated according to
`GetExitCodeProcess` may not yet be signalled to Python's wait. When the
upstream 10 s teardown times out, the adapter queries only its own process
handle, waits up to 20 s more, never treats `STILL_ACTIVE` as a successful stop
and never kills processes by name. Release of kernel/driver objects remains the
operating system's responsibility. A teardown that still fails is reported as
`cleanup_error` and the run ends `failed`; a reset requested while the run
thread is still shutting down returns `Simulation is still shutting down;
cannot reset yet`.

**`This scenario needs HoloOcean; standalone supports fixed network fixtures
only`.** `--standalone` / DESERT-only mode rejects scenarios with waypoints or
`coordination: true`.

## Dashboard

**`The web laboratory needs the dashboard extra`.** Install
`pip install "holoocean-desert[dashboard]"`.

**Blank page / JavaScript modules rejected on Windows.** The Windows MIME
registry can map `.js` to `text/plain`, which browsers reject for ES modules.
The dashboard sets `text/javascript` and `text/css` explicitly for its static
files; if the problem appears, make sure the installed package is current and
that the page is served by `holo-desert dashboard`.

**HTTP 409.** A run is already active (start), there is no run (controls), the
run is not finished/integrated (comparison), a personal scenario or profile was
modified elsewhere (stale revision) or its name already exists. Reload and
retry.

## Configuration errors

Validation errors are raised before the engine starts. Common ones:

| Message | Fix |
|---|---|
| `Frame does not fit its TDMA slot: increase frame duration or reduce payload` | Increase `mac.tdma.frame_duration_s`, reduce `payload_bytes` or the guard |
| `TDMA guard time must be shorter than a slot` | `guard_time_s < frame_duration_s / N` |
| `Assign one slot to every node` / `TDMA slot assignments must be unique in 0..N-1` | Complete the slot map or leave it empty |
| `Frame does not fit its token holding time …` / `Frame exceeds the native token startup timeout …` | Increase `max_token_hold_s` or `slot_time_s`, or reduce the payload |
| `Flooding broadcast is not supported by the verified CSMA/CA or DACAP handshake stack` | Use static routing or another MAC |
| `Static routes cannot be used with Flooding` | Remove `routes` when `routing` is not `static` |
| `Static routing loop from … to …`, `Static routes cannot route to or through their own source` | Fix `network.routes` |
| `CSMA-CA requires integer bitrate in 1..2147483647` | Use an integer `bitrate_bps` |
| `SUN supports convergecast flows to the designated sink without replies` | All flows must end at `sun.sink` |
| `This medium currently requires verified CSMA-ALOHA and StaticRouting` | Optical/EM accept only that stack |
| `Native generators require data, native timing, and no Python reply` | See [native applications](stack-configuration.md#native-applications-uwcbr-uwvbr) |
| `Encoded message is … bytes; maximum is …` | Reduce the payload or raise `max_wire_bytes` (≤ 4096) |

**Optical depth limit.** `Optical noise LUT covers underwater depths through
20 m`: the pinned optical ambient-noise LUT covers 0–20 m, so initial
positions, waypoints and every measured position must satisfy `-20 <= z < 0`.
The check also runs at each position update, so a vehicle drifting below 20 m
stops the run.

**WOSS geometry guards.** `WOSS Bellhop requires at least 1 m horizontal
separation between nodes` and `WOSS position needs 0.1 m clearance from
surface/seabed and must be within 100 km of the geographic origin`. In the
pinned native implementation a vertically aligned link aborts in
`bellhop-woss.cpp:946`; the configuration and runtime guards stop the run
before propagation instead. They are model constraints, not artificial losses.
See [stack-configuration.md](stack-configuration.md#woss--bellhop).

## Installation and tests

**Ubuntu: `posix_ipc` fails to build.** Install `build-essential` and
`python3-dev`.

**Native tests refuse to start: `Explicit DESERT_PORT is unavailable; start the
isolated test service`.** With `DESERT_PORT` set, the test fixture does not
manage the default Compose project; start a healthy engine on that port first
(see [developer-guide.md](developer-guide.md#running-tests)).

**Frontend tests.** On Windows Playwright uses the installed Microsoft Edge
(`msedge` channel); on Linux install Chromium with
`npx playwright install --with-deps chromium`. One Python test that creates a
symlink is skipped on Windows without the required privilege.

**CI: Chromium dependency installation fails with apt HTTP 403.** The hosted
Ubuntu runner preconfigures `packages.microsoft.com`/Azure apt sources; when
they answer 403, `apt-get update` (run by `playwright install --with-deps`)
aborts. The workflow (`.github/workflows/tests.yml`) removes those unused
sources, enables apt retries (`Acquire::Retries "5"`) and retries
`npx playwright install-deps chromium` up to three times, so the browser suite
still runs in full.
