# Bundled scenarios

Common command: `holo-desert run <id>`. The dashboard serves the local
laboratory at http://127.0.0.1:8000; the 3D world is the official HoloOcean
one. The YAML files are in `src/holo_desert/resources/examples/<id>/scenario.yaml`
(E01–E06) and `src/holo_desert/resources/demos/<id>/scenario.yaml` (demos).

## Reference experiments (E01–E06)

| ID | What it runs | Evidence to check |
|---|---|---|
| `e01_chat` | Request and reply between two stationary vehicles | `app_tx`, `rx` and `delivered` with the same message ID; timestamps and payload |
| `e02_multi_node` | Four simultaneous sources | Offered load, receptions, MAC queues; no collision inferred from timeouts |
| `e03_mobility` | Two PD controllers follow targets that move apart and come back | Measured positions, `position_applied`, distance and delivery ratio |
| `e04_congestion` | Three flows to one sink with decreasing intervals | Real MAC queues, throughput, and timeouts kept apart from bridge errors |
| `e05_multihop` | Static routes A → B → C | Forwarding observed at B and reception at C |
| `e06_coordination` | Heartbeat leader and follower with HOLD/PROCEED states | PHY power lowered to 0 dB from 8 to 18 s; states and recovery after reception |

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

## Demos

| ID | What it shows |
|---|---|
| `e07_ranging_tokenbus` | Native Ranging-TokenBus distance estimates between three vehicles, beside the HoloOcean geometry |
| `e08_woss` | A moving receiver in a WOSS/Bellhop channel with a synthetic sound-speed profile |
| `e09_sun_convergecast` | Native SUN route discovery through relays to a sink |

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
