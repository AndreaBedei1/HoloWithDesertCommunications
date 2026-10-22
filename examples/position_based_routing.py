"""Native Position-Based Routing with static anchors and one vehicle (standalone).

Anchors auv_01..auv_03 lie on a line 500 m apart and know only their surveyed
positions and next-hop tables; the vehicle auv_04 knows only its own position
(the pose this script supplies) and the anchors' surveyed positions. Anchors
estimate the vehicle from the headers of the packets it sends. The script moves
the vehicle along the line and prints the hops DESERT chose.

    python examples/position_based_routing.py [--port 5555]
"""
import argparse

from holo_desert import Network, NetworkSession, NodeConfig, Scenario

ANCHORS = {"auv_01": (-500, 0, -100), "auv_02": (0, 0, -100), "auv_03": (500, 0, -100)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    scenario = Scenario(
        name="position_based", description="Vehicle among three anchors", physics_hz=10,
        nodes=[NodeConfig(id=node, position=position) for node, position in ANCHORS.items()]
        + [NodeConfig(id="auv_04", position=(-500, 200, -100))],
        network=Network.model_validate({
            "acoustic": {"tx_power_db": 132}, "routing": "position_based",
            "position_based": {"anchor_range_m": 450, "vehicle_range_m": 450,
                               "anchors": {node: {} for node in ANCHORS}},
            # Anchor tables; a missing entry means "direct".
            "routes": {"auv_01": {"auv_03": "auv_02", "auv_04": "auv_02"},
                       "auv_02": {"auv_04": "auv_03"}, "auv_03": {"auv_01": "auv_02"}}}))
    names = {i: node for node, i in scenario.node_map.items()}
    with NetworkSession(scenario, port=args.port, manage_engine=args.port is None) as net:
        net.run_until(1)       # the native estimator ignores headers stamped t = 0
        print("vehicle x   uplink auv_04 -> auv_01          downlink auv_01 -> auv_04")
        for x in (-500, -225, 275, 500):
            net.update_pose("auv_04", (x, 200, -100))
            row = []
            for source, destination in (("auv_04", "auv_01"), ("auv_01", "auv_04")):
                start = net.time
                net.node(source).send(destination, b"position-based")
                events = net.run_until(start + 10)
                hops = [f"{names[e['node']][-2:]}>{names[e['next_hop_address']][-2:]}" for e in events if e["event"] == "forward"]
                delivered = bool(net.node(destination).receive())
                row.append(f"{' '.join(hops):22} {'ok' if delivered else 'lost':4}")
            print(f"{x:9}   " + "   ".join(row))


if __name__ == "__main__":
    main()
