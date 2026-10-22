"""Managed run: the library starts HoloOcean and DESERT for a bundled scenario.

    python examples/managed_run.py e03_mobility --out e03.zip
    python examples/managed_run.py e05_multihop --no-holoocean   # fixed positions
"""
import argparse
import json

from holo_desert import ManagedSimulation


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", nargs="?", default="e01_chat")
    parser.add_argument("--no-holoocean", action="store_true")
    parser.add_argument("--port", type=int)
    parser.add_argument("--out")
    args = parser.parse_args()
    with ManagedSimulation(args.scenario, holoocean=not args.no_holoocean, realtime=False,
                           port=args.port, manage_engine=args.port is None) as sim:
        summary = sim.run()
        print(json.dumps({k: summary[k] for k in ("generated", "received", "timed_out", "pdr_resolved",
                                                   "mean_latency_s", "phy_observations")}, indent=2))
        if args.out:
            sim.export(args.out)


if __name__ == "__main__":
    main()
