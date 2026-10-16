"""Run actual HoloOcean + DESERT demos and report compact observed evidence."""
import argparse
import itertools
import json
import math
from pathlib import Path
import time

from holo_desert.core.orchestrator import SimulationOrchestrator
from holo_desert.scenarios.config import ScenarioManager


def validate(name, mac=None):
    scenario = ScenarioManager().load(name)
    if mac:
        scenario.network.mac.protocol = mac
    scenario.realtime = False
    run = SimulationOrchestrator(scenario, manage_docker=False, show_viewport=False)
    started = time.monotonic()
    try:
        run.run()
        snapshot = run.snapshot()
        states, distances, phy_errors, queue_max = [], [], {}, 0
        for line in (run.telemetry.directory / "events.jsonl").read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            if event["event"] == "application_state":
                states.append({k: event[k] for k in ("time", "node", "state")})
            elif event["event"] == "fleet":
                nodes = list(event["nodes"].values())
                a, b = nodes[0], nodes[1]
                distances.append((event["time"], math.dist([a[k] for k in ("x", "y", "z")], [b[k] for k in ("x", "y", "z")])))
            elif event["event"] == "phy_rx_end":
                key = event["outcome"]
                phy_errors[key] = phy_errors.get(key, 0) + 1
            elif event["event"] == "stats":
                queue_max = max(queue_max, event.get("mac_queue") or 0)
        packets = snapshot["packets"]
        windows = []
        for low, high in ((0, 12), (25, 55), (70, 100)):
            cohort = [p for p in packets if low <= p["creation_time"] < high]
            if cohort:
                windows.append({"creation_window_s": [low, high], "generated": len(cohort),
                                "received": sum(p["status"] == "received" for p in cohort)})
        summary = {"scenario": name, "state": run.state, "error": run.error,
                   "mac": scenario.network.mac.protocol,
                   "wall_duration_s": round(time.monotonic() - started, 2), "logical_duration_s": run.clock.time,
                   "counts": snapshot["counts"], "phy_receptions": phy_errors, "max_mac_queue": queue_max,
                   "distance_min_m": min((d for t, d in distances), default=None),
                   "distance_max_m": max((d for t, d in distances), default=None),
                   "distance_end_m": distances[-1][1] if distances else None,
                   "application_states": states, "creation_cohorts": windows,
                   "relay_forwarding_observations": sum(e["event"] == "forward" and e.get("node") == 2 for p in packets for e in p["events"])}
        print(json.dumps(summary), flush=True)
        return summary
    finally:
        run.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("scenarios", nargs="*", default=["e02_multi_node", "e03_mobility", "e04_congestion", "e05_multihop", "e06_coordination"])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--mac", choices=["csma_aloha", "aloha"])
    args = parser.parse_args()
    results = []
    for name in args.scenarios:
        results.append(validate(name, args.mac))
        if args.output:
            args.output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return int(any(r["error"] for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
