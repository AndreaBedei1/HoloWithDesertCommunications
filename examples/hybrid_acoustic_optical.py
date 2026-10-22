"""Mixed acoustic/optical interfaces switched by DESERT's native controller (standalone).

Each node has an acoustic interface (25 kHz, 150 dB re 1 uPa) and an optical one
(1 Mbit/s, default optical parameters). The master moves to optical when the
averaged acoustic received power exceeds 1e13 (linear, about 14 m) and back to
acoustic when the optical received power falls below 3e-8 W (about 28 m). This
script only moves auv_02 and prints which interface DESERT used.

    python examples/hybrid_acoustic_optical.py [--port 5555]
"""
import argparse

from holo_desert import Network, NetworkSession, NodeConfig, Scenario

NETWORK = {"multiphy": {
    "interfaces": [
        {"id": "acoustic", "acoustic": {"frequency_hz": 25000, "bandwidth_hz": 5000, "bitrate_bps": 4800, "tx_power_db": 150}},
        {"id": "optical", "medium": "optical", "optical": {"bitrate_bps": 1000000}}],
    "initial_interface": "acoustic", "policy": "received_power", "master": "auv_01",
    "thresholds": [{"from_interface": "acoustic", "to_interface": "optical", "power_linear": 1e13},
                   {"from_interface": "optical", "to_interface": "acoustic", "power_linear": 3e-8}]}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    # Optical interfaces need nodes between 0 and 20 m depth (range of the pinned noise table).
    scenario = Scenario(name="hybrid", description="Acoustic/optical switching", physics_hz=10,
                        nodes=[NodeConfig(id="auv_01", position=(0, 0, -10)),
                               NodeConfig(id="auv_02", position=(8, 0, -10))],
                        network=Network.model_validate(NETWORK))
    names = {1: "acoustic", 2: "optical"}
    with NetworkSession(scenario, port=args.port, manage_engine=args.port is None) as net:
        a, b = net.node("auv_01"), net.node("auv_02")
        print("distance  auv_02 -> auv_01            auv_01 -> auv_02")
        for distance in (8, 8, 20, 50, 100, 8, 8):
            b.update_pose((distance, 0, -10))
            row = []
            for source, destination in ((b, "auv_01"), (a, "auv_02")):
                start = net.time
                source.send(destination, b"probe")
                events = net.run_until(start + 5)
                used = [names[e["interface_index"]] for e in events
                        if e["event"] == "phy_tx_start" and e["node"] == scenario.node_map[source.id]]
                delivered = bool(net.node(destination).receive())
                row.append(f"{'/'.join(used):9} {'delivered' if delivered else 'lost':9}")
            print(f"{distance:6} m  " + "   ".join(row))


if __name__ == "__main__":
    main()
