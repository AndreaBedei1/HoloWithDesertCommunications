# Additional native protocols

These adapters use the installed DESERT implementations. Python validates and
serializes configuration; it does not schedule channel access, select routes or
calculate ranging estimates.

| Selection | Verified stack | Native controls |
| --- | --- | --- |
| `csburst` | StaticRouting, original/corrected acoustic BPSK | Queue capacity, burst length, fixed/random sensing time |
| `tokenbus` | StaticRouting, original/corrected acoustic BPSK | Queue capacity, constructor ring membership, slot and token holding times |
| `ranging_tokenbus` | Same as TokenBus | Same MAC controls; native least-squares ranging observations |
| `sun` routing | CSMA-ALOHA without MAC ACK, original/corrected acoustic BPSK | Designated sink, probe/status/data/buffer timers, native randomized timing, buffer/retry limits, minimum probe SNR |

Additional MACs reject the ALOHA ACK option and unverified routing combinations.
TokenBus defaults use the upstream 10-second slot and maximum holding time.
Declared frames must fit the maximum holding time and the initial idle timeout
`3 * (slot_time_s + min_token_hold_s)`. Short initial idle timers can regenerate
the token while a large data frame is still being received.

Ranging events identify the observing node and measured peer pair. The native
`get_distance` command returns one-way travel time in seconds; the adapter
multiplies it by the configured channel sound speed to report metres. Unavailable
measurements remain `null` with `valid: false`. The native API does not expose
measurement age, so `measurement_time` remains `null`; a valid retained estimate
must not be presented as a fresh measurement.

SUN supports convergecast to the configured sink. Static routes, sink-originated
flows, replies and coordination traffic are rejected. Native probes and path
establishment choose the route. Probe reception is distinct from reliable data
reception: configure the minimum probe SNR for the payload and geometry. The
five-node test uses a 20 dB probe threshold to avoid selecting a weak direct link.
SUN's cumulative counters are static members of its node/sink classes; therefore
`routing_stats.class_values` reports class totals, while `values` contains only
local queue and path counters. Do not sum repeated class totals across nodes.

Reproducible checks are in `tests/unit/test_additional_protocols.py` and
`tests/integration/test_native_additional_protocols.py`. Native tests cover both
PHY implementations, repeated process starts, bidirectional packets, actual
queue overflow, two/three/five-node ranging and changed positions, repeated and
queued SUN traffic, and native discovery through a five-node topology with two
available branches. Set `DESERT_PORT` to an isolated healthy service before
selecting `-m desert`.
