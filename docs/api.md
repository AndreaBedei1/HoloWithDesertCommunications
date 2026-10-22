# Python API reference and tutorial

`holo_desert` is usable as an ordinary Python package. The web laboratory is an
optional client of the same classes and is not needed for any of the workflows
below.

```python
from holo_desert import (NetworkSession, HoloOceanLink, ManagedSimulation,
                         Scenario, NodeConfig, Network, Flow, Pose,
                         load_scenario, list_examples, pose_from_sensors)
```

Importing the package loads neither HoloOcean nor the dashboard dependencies
(FastAPI/uvicorn). All network behaviour (PHY, propagation, interference, MAC,
routing, native generators, ranging) is executed by DESERT/NS-MIRACLE inside
the engine container. Python validates configuration, moves time, transports
poses and messages, and records telemetry.

## Choosing a mode

| Mode | Class | Who owns HoloOcean | Who moves time | Typical use |
|---|---|---|---|---|
| A. Managed | `ManagedSimulation` | the library | the library (scenario duration) | run a scenario with its flows, like the dashboard |
| B. Attached | `NetworkSession` + `HoloOceanLink` | your application | your `env.tick()` loop | add DESERT networking to an existing HoloOcean program |
| C. Standalone | `NetworkSession` | nobody | your code (`step`, `run_until`) | protocol studies, scripted mobility, reproducible network tests |

All modes need a running engine service (`holo-desert engine up`, or
`manage_engine=True`, the default, which starts the Compose service when no
healthy service answers). Only A (with `holoocean=True`) and B need HoloOcean.

## Building a scenario

A `Scenario` is the typed, validated description shared by all modes. It can
be loaded from YAML (`load_scenario("e03_mobility")`, a saved user scenario
id, or a file path) or built in Python:

```python
from holo_desert import Scenario, NodeConfig, Network

scenario = Scenario(
    name="two_nodes", description="CSMA-ALOHA over 40 m",
    physics_hz=30,                       # tick rate shared by HoloOcean and DESERT
    nodes=[NodeConfig(id="auv_01", position=(0, 0, -20)),
           NodeConfig(id="auv_02", position=(40, 0, -20))],
    network=Network.model_validate({
        "mac": {"protocol": "tdma", "tdma": {"frame_duration_s": 3}},
        "acoustic": {"tx_power_db": 130, "phy": "bpsk_upstream"},
    }),
)
```

Node identifiers follow `auv_NN`. Units are metres for positions (Z negative
under the surface), degrees for yaw/pitch/roll, seconds for time and the
medium's native unit for transmit power (dB re µPa SPL acoustic, W optical,
dBm EM). Unsupported or unverified stacks are rejected at construction, for
example Flooding over CSMA/CA. The complete schema is described in
[stack-configuration.md](stack-configuration.md) and the verification status
of each module in [capabilities.md](capabilities.md).

## Mode C: standalone network

```python
from holo_desert import NetworkSession

with NetworkSession(scenario) as net:            # start() ... close()
    a, b = net.node("auv_01"), net.node("auv_02")
    b.on_receive(lambda d: print(d.network_time, d.message.json()))
    a.send_json("auv_02", {"cmd": "survey", "leg": 3})
    a.send("auv_02", b"\x01\x02")               # binary payload
    for second in range(20):
        net.update_pose("auv_02", (40 + 5 * second, 0, -20))   # your motion model
        net.run_until(second + 1)
    print(net.summary()["received"], net.summary()["mean_latency_s"])
    net.export("run.zip")
```

`examples/standalone_network.py` is a runnable version with three nodes and
a node that drives out of range.

## Mode B: attach to your HoloOcean environment

```python
import holoocean
from holo_desert import NetworkSession, HoloOceanLink

with holoocean.make(scenario_cfg=my_config, ticks_per_sec=30) as env, \
        NetworkSession(scenario) as net:
    link = HoloOceanLink(net, {"leader": "auv_01", "follower": "auv_02"}, ticks_per_sec=30)
    link.attach(env.reset())                # t=0 poses on both simulators
    while running:
        env.act("leader", my_controller())  # you keep full control
        state = env.tick()
        link.sync(state)                    # DESERT covers the same tick
        for delivery in net.node("auv_02").receive():
            handle(delivery)
```

The link never starts or ticks HoloOcean. It reads each mapped agent's own
sensor: `DynamicsSensor` configured with `UseRPY: true`, `PoseSensor`, or
`LocationSensor` (+ optional `RotationSensor`); a custom `pose_reader` can be
passed. Each agent's pose is given to DESERT because the channel model needs
geometry; your application code receives only its own messages and, through
`NetworkNode.pose`, only the pose of the node it holds. `examples/attach_holoocean.py`
is a complete program.

`ticks_per_sec` must equal `scenario.physics_hz`. If your loop ticks HoloOcean
several times between two `sync` calls, pass `ticks=n`; the network then holds
the last poses for those ticks.

## Mode A: managed simulation

```python
from holo_desert import ManagedSimulation

with ManagedSimulation("e03_mobility", realtime=False) as sim:
    summary = sim.run()                 # HoloOcean + DESERT + scenario flows
    sim.export("e03.zip")
```

`holoocean=False` runs the same scenario on fixed configured positions (no
waypoints or coordination). `start_background()`, `pause()`, `resume()`,
`stop()`, `wait()` and `snapshot()` give the dashboard's controls. This is the
orchestrator the dashboard uses; the dashboard adds no communication logic.

## Clock and order of operations

There is a single simulated timeline `t = k / physics_hz` (integer tick `k`).
Wall-clock time never advances it; `ManagedSimulation(realtime=True)` only
paces the loop.

One `step()` from tick `k` to `k+1`, with `t = k/physics_hz`:

1. every node pose currently stored is sent to DESERT, timestamped `t`
   (DESERT must acknowledge all of them);
2. messages queued since the previous step enter DESERT with creation time `t`;
3. once per simulated second a statistics request is queued;
4. DESERT runs its scheduler up to `t + dt` and returns every event with its
   own timestamp (transmission start, reception lifecycle, forwarding, rx ...);
5. receptions are delivered to the inbox or callbacks once
   `network_time <= t + dt`, ordered by network time, duplicates suppressed and
   receptions after the message TTL reported as `late_receive`.

Consequences:

* a message sent between two steps is created at the current barrier time;
  its end-to-end latency `delivery.network_time - message.creation_time`
  includes queueing, MAC, transmission duration (airtime) and propagation;
* the network uses each pose for one whole tick (no movement during a packet's
  flight, no Doppler); choose `physics_hz` accordingly;
* in mode B, `sync(state)` first advances DESERT over the tick that produced
  `state` using the poses from the previous tick, then stores the new poses;
* `delivery.transport_observed_wall_time` is a diagnostic wall-clock value,
  not a simulation time.

## Life cycle and errors

`NetworkSession.state` is `created` → `running` → `closed`. Any transport or
engine failure during `start`/`step` raises `SessionError`, stops DESERT and
sets `failed`; recorded results remain available for `summary()`/`export()`
until `close()`. `restart()` starts a new DESERT run at t=0 with the same
scenario and the initial poses (callbacks are kept). Each engine service runs
one session at a time; a second concurrent session fails with a clear "busy"
error. Use separate engines (ports) for parallel experiments.

Configuration errors raise `ValueError` (pydantic `ValidationError` is a
subclass) before anything is started. A stale engine image is rejected at
start: its content fingerprint must match the installed package
(`holo-desert engine up` rebuilds it, `holo-desert doctor` reports it).

## Reference

### `NetworkSession(scenario, *, host="127.0.0.1", port=None, manage_engine=True, persist=None, timeout=30)`

* `scenario`: `Scenario`, example name or YAML path. `port` defaults to
  `$DESERT_PORT` or 5555. `persist`: directory receiving `run-NNN/` folders with
  `config.json` and `events.jsonl`; otherwise a temporary directory removed on
  `close()`.
* `start()`, `close()` (alias `stop()`), `restart()`; context manager.
* `node(node_id) -> NetworkNode`; `node_ids`; `time`; `dt`; `engine_info`
  (DESERT release and source commit, engine fingerprint, patches, effective
  network and per-node stack as applied by the engine).
* `update_pose(node_id, pose)`, `update_poses({node_id: pose})`: `Pose` or
  `(x, y, z[, yaw[, pitch, roll]])`, measured at the current time.
* `send(source, destination, payload, **options) -> message_id`.
* `step(ticks=1) -> list[dict]` raw DESERT events; `run_until(time_s)`.
* `summary()`: counts (generated, received, timed_out, pending), PDR over
  resolved and over generated messages, goodput, mean latency, PHY outcome
  observations, MAC queue peak, per-node MAC statistics. `packets()`: one
  record per message with status, delay and its network events.
  `snapshot()`: full telemetry state. `export(path)`: ZIP with `config.json`,
  `events.jsonl`, `packets.csv`, `summary.json`.

### `NetworkNode`

* `send(destination, payload, *, ttl=20.0, message_type=None, priority=0)`:
  `bytes` are sent as `binary`, other values as JSON. Unicast only; the
  destination must be another configured node. `ttl` is an application
  validity window (late receptions are reported, not delivered); `priority`
  is metadata and does not change MAC behaviour.
* `send_json(destination, obj, **options)`.
* `receive() -> list[Delivery]`; `on_receive(callback)` (usable as decorator)
  and `remove_callback(callback)`. A node with callbacks does not fill its inbox.
* `update_pose(pose)`, `pose` (own pose only).
* `set_tx_power(value)`: sent immediately and applied by DESERT at the current
  barrier time, before the next step.
* `select_interface(name)`: multi-PHY with `policy: manual` only.

`Delivery` has `message` (`source`, `destination`, `payload`, `message_type`,
`creation_time`, `ttl`, `id`, `json()`), `receiver`, `network_time` and
`metadata` (the raw `rx` event, including interface information when present).

### `HoloOceanLink(session, agents=None, *, ticks_per_sec=None, pose_reader=pose_from_sensors)`

`agents` maps HoloOcean agent names to node ids (default: identical names).
Methods: `attach(state)`, `sync(state, ticks=1) -> events`, `read_poses(state)`.

### `ManagedSimulation(scenario, *, holoocean=True, show_viewport=False, realtime=None, manage_engine=True, port=None, persist=None, application_factory=None)`

`run() -> summary`, `start_background()`, `wait(timeout)`, `pause()`,
`resume()`, `stop()`, `summary()`, `snapshot()`, `export(path)`,
`export_bytes()` (the same ZIP in memory), `close()` (idempotent), `state`,
`error`, `run_id`, `holoocean` (whether HoloOcean drives the poses),
`versions` (platform, HoloOcean and engine identity recorded at start),
`trajectory_fingerprint()` (SHA-256 per vehicle of the observed fleet
telemetry) and `annotate(event, **fields)` (adds a caller event to the
exported log). `application_factory(node, communication, scenario)` replaces
the built-in traffic applications with your own objects exposing
`update(now, own_pose, received) -> pose target or None`.

### Helpers

`load_scenario(name_or_path)`, `list_examples()`, `pose_from_sensors(sensors)`.

`network_catalog()` returns the module catalogue that the engine also uses
for validation (verification status, parameters with unit, default, bounds
and help, selectors for medium, propagation and SSP); `network_inventory()`
returns the audit of what the pinned DESERT image installs.

### Scenario and profile libraries

`ScenarioManager(root=None, user_root=None)` lists and loads the bundled
examples and the personal scenarios (`list()`, `load(name_or_id)`,
`list_user()`, `get_user(id)`, `save_user(configuration, id=None,
expected_revision=None)`, `delete_user(id, expected_revision)`; the store is
`ScenarioLibrary`, which raises `ScenarioConflict` on a stale revision).
`ProfileLibrary(directory, reserved_names)` stores communication profiles
(`CommunicationProfile`: name, description, network); `builtin_profiles()`
returns the bundled ones. The dashboard uses exactly these public objects and
`ManagedSimulation`; it has no private access to the engine or orchestrator.

## Command line equivalents

```bash
holo-desert run e03_mobility --fast --no-dashboard --persist results/e03
holo-desert run e01_chat --standalone --no-dashboard
holo-desert doctor --library-only
```
