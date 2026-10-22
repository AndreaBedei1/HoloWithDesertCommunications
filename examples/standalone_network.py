"""Standalone DESERT network driven from Python (no HoloOcean, no dashboard).

Three nodes share a TDMA channel; auv_03 moves along a path supplied by the
caller. Received messages arrive through callbacks.

    python examples/standalone_network.py [--port 5555] [--out results.zip]
"""
import argparse

from holo_desert import Network, NetworkSession, NodeConfig, Scenario


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int)
    parser.add_argument("--out")
    args = parser.parse_args()
    scenario = Scenario(
        name="standalone_tdma", description="Three nodes, TDMA, one scripted moving node",
        physics_hz=10,
        nodes=[NodeConfig(id="auv_01", position=(0, 0, -30)),
               NodeConfig(id="auv_02", position=(60, 0, -30)),
               NodeConfig(id="auv_03", position=(0, 60, -30))],
        network=Network.model_validate({"mac": {"protocol": "tdma", "tdma": {"frame_duration_s": 3}},
                                        "acoustic": {"tx_power_db": 130}}))
    log = []
    with NetworkSession(scenario, port=args.port, manage_engine=args.port is None) as net:
        for node_id in ("auv_02", "auv_03"):
            net.node(node_id).on_receive(lambda d, n=node_id: log.append(
                (n, d.message.source, d.message.json(), d.network_time - d.message.creation_time)))
        hub = net.node("auv_01")
        for second in range(40):
            if second % 5 == 0:
                hub.send_json("auv_02", {"seq": second})
                hub.send_json("auv_03", {"seq": second})
            # The caller owns the motion model: auv_03 drifts away at 25 m/s.
            net.update_pose("auv_03", (0, 60 + 25 * second, -30))
            net.run_until(second + 1)
        print("deliveries (receiver <- source, payload, end-to-end latency):")
        for receiver, source, payload, latency in log:
            print(f"  {receiver} <- {source} {payload} {latency:.3f} s")
        summary = net.summary()
        print({k: summary[k] for k in ("generated", "received", "timed_out", "pending", "mean_latency_s")})
        if args.out:
            print("exported", net.export(args.out))


if __name__ == "__main__":
    main()
