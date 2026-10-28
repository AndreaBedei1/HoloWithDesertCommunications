# Bundled scenarios

Nine scenarios are bundled. `ScenarioManager` discovers them in two folders
and assigns each a group:

| Group | Dashboard heading | IDs | YAML files |
|---|---|---|---|
| `reference` | Reference Scenarios | E01–E06 | `src/holo_desert/resources/examples/<id>/scenario.yaml` |
| `demonstration` | Advanced Demonstrations | E07–E09 | `src/holo_desert/resources/demos/<id>/scenario.yaml` |

`ScenarioManager.group(name)` returns the group of a bundled scenario;
`list_examples()` and `ScenarioManager().list()` return all nine IDs.

## Launching a scenario

Every bundled scenario is addressed by its ID in all three entry points.

- Command line: `holo-desert examples` prints the ID, group and description of
  each scenario; `holo-desert run <id>` runs one and serves the dashboard at
  http://127.0.0.1:8000 while it runs (`--no-dashboard` prints state and
  counts instead, `--fast` skips wall-clock pacing).
- Python: `ManagedSimulation("<id>")` or `load_scenario("<id>")`
  ([api.md](api.md)).
- Dashboard: `holo-desert dashboard`, then select the scenario on the home
  page and press **Start simulation**. `GET /api/scenarios` returns `id`,
  `group` and `description` for each bundled scenario (personal scenarios are
  listed by `GET /api/user-scenarios`).

The 3D world is the official HoloOcean one.

## Reference Scenarios (E01–E06)

One communication concept each, on the analytic acoustic channel. The titles
are those shown on the dashboard home page.

| ID | Title | What it runs | Evidence to check |
|---|---|---|---|
| `e01_chat` | Message exchange | Request and reply between two stationary vehicles | `app_tx`, `rx` and `delivered` with the same message ID; timestamps and payload |
| `e02_multi_node` | Multi-drone communication | Four simultaneous sources | Offered load, receptions, MAC queues; no collision inferred from timeouts |
| `e03_mobility` | Moving drones | Two PD controllers follow targets that move apart and come back | Measured positions, `position_applied`, distance and delivery ratio |
| `e04_congestion` | Network congestion | Three flows to one sink with decreasing intervals | Real MAC queues, throughput, and timeouts kept apart from bridge errors |
| `e05_multihop` | Relay communication | Static routes A → B → C | Forwarding observed at B and reception at C |
| `e06_coordination` | Drone coordination | Heartbeat leader and follower with HOLD/PROCEED states | PHY power lowered to 0 dB from 8 to 18 s; states and recovery after reception |

E01–E06 are kept unchanged as reference experiments; their expected message
counts are listed in
[telemetry-and-reproducibility.md](telemetry-and-reproducibility.md#recorded-results).
`e01`, `e02`, `e04` and `e05` also run with `--standalone`: fixed positions,
the real DESERT engine and no vehicle simulation. The mobile demos and the
coordination example refuse that mode.

MAC comparison on the same experiment:

```bash
holo-desert run e04_congestion
holo-desert run e04_congestion --mac aloha
```

## Advanced Demonstrations (E07–E09)

Native DESERT ranging, Bellhop propagation and dynamic routing.

| ID | Title | What it shows | What to observe in the dashboard |
|---|---|---|---|
| `e07_ranging_tokenbus` | Native ranging with TokenBus | Three stationary drones share the native Ranging-TokenBus MAC; data travels on the token ring while the MAC measures one-way travel times and estimates distances (travel time × sound speed) | **Analysis → Ranging**: native estimates beside the HoloOcean geometric distance, which the protocol does not know |
| `e08_woss` | Bellhop propagation (WOSS) | Native Bellhop propagation with a synthetic non-uniform sound-speed profile; the receiver changes range and depth over a flat seabed | Native received power and arrival delay as the receiver moves |
| `e09_sun_convergecast` | SUN convergecast to a sink | Four stationary drones use native SUN dynamic routing towards sink D; probes select relays B or C instead of the 800 m direct link, and routes can change during the run | The relays SUN discovers for each message (message details and relay path on the map); some late messages are still pending when the run ends |

```bash
holo-desert run e07_ranging_tokenbus
holo-desert run e08_woss
holo-desert run e09_sun_convergecast
```

## Reading the results

The parameters of `e03` and `e05` are specific to the model and the seed: a
configured relay does not by itself prove that direct reception is impossible.
For E05 this was checked: at 132 dB SPL two 500 m hops deliver through B,
while the direct 1000 m link does not deliver the payload. The dashboard
labels the arcs as end-to-end application receptions, not physical hops; the
message details list the forwarding observations actually produced in the
stack.

The coordination example is not a safety system: it is a didactic example of
reacting to message freshness. The outage happens in DESERT's power model,
never by dropping messages in the application.

The dated records in [evidence/](evidence/README.md) separate configurations
that were implemented from demonstrations that were executed and verified.
