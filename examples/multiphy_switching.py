"""Native DESERT multi-PHY controller driven by received power (standalone).

Two acoustic interfaces per node ("long": 25 kHz/4800 bit/s, "short":
50 kHz/8800 bit/s). The native master/slave controller picks the interface;
this script only moves auv_02 and prints which interface DESERT used.
Thresholds are in the controller's native linear power units.

    python examples/multiphy_switching.py [--port 5555]
"""
import argparse

from holo_desert import Network, NetworkSession, NodeConfig, Scenario

NETWORK = {"multiphy": {
    "interfaces": [
        {"id": "long", "acoustic": {"frequency_hz": 25000, "bandwidth_hz": 5000, "bitrate_bps": 4800, "tx_power_db": 150}},
        {"id": "short", "acoustic": {"frequency_hz": 50000, "bandwidth_hz": 9000, "bitrate_bps": 8800, "tx_power_db": 150}}],
    "initial_interface": "long", "policy": "received_power",
    "thresholds": [{"from_interface": "long", "to_interface": "short", "power_linear": 1},
                   {"from_interface": "short", "to_interface": "long", "power_linear": 1e-6}]}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    scenario = Scenario(name="multiphy", description="Received-power interface switching", physics_hz=10,
                        nodes=[NodeConfig(id="auv_01", position=(0, 0, -20)),
                               NodeConfig(id="auv_02", position=(30, 0, -20))],
                        network=Network.model_validate(NETWORK))
    names = {1: "long", 2: "short"}
    with NetworkSession(scenario, port=args.port, manage_engine=args.port is None) as net:
        a, b = net.node("auv_01"), net.node("auv_02")
        print("distance  interface(auv_02 -> auv_01, auv_01 -> auv_02)  delivered")
        for distance in (30, 300, 1000, 3000, 6000, 300, 30):
            b.update_pose((distance, 0, -20))
            start = net.time
            b.send("auv_01", b"probe")              # lets the controller observe power
            events = net.run_until(start + 6)
            a.send("auv_02", b"data")
            events += net.run_until(start + 12)
            used = [names.get(e.get("interface_index")) for e in events if e["event"] == "phy_tx_start"]
            delivered = len(a.receive()) + len(b.receive())
            print(f"{distance:8} m  {used}  {delivered}/2")


if __name__ == "__main__":
    main()
