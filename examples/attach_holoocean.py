"""Attach DESERT networking to a HoloOcean environment owned by this script.

The application creates the environment, commands the vehicles and calls
env.tick(); the library only reads each agent's own DynamicsSensor and keeps
DESERT on the same timeline. Requires HoloOcean 2.3.0 with the Ocean package.

    python examples/attach_holoocean.py [--port 5555] [--seconds 20]
"""
import argparse

import holoocean

from holo_desert import HoloOceanLink, NetworkSession, NodeConfig, Scenario

HZ = 30


def agent(name, location):
    return {"agent_name": name, "agent_type": "HoveringAUV", "control_scheme": 1,
            "location": list(location), "rotation": [0, 0, 0],
            "sensors": [{"sensor_type": "DynamicsSensor", "socket": "COM",
                         "configuration": {"UseCOM": True, "UseRPY": True}}]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int)
    parser.add_argument("--seconds", type=float, default=20)
    args = parser.parse_args()
    config = {"name": "my_mission", "world": "OpenWater", "package_name": "Ocean", "main_agent": "leader",
              "ticks_per_sec": HZ, "frames_per_sec": False,
              "agents": [agent("leader", (0, 0, -20)), agent("follower", (30, 0, -20))]}
    # Network nodes use auv_NN identifiers; the link maps them to the agents.
    scenario = Scenario(name="attached", description="Leader/follower under external control", physics_hz=HZ,
                        nodes=[NodeConfig(id="auv_01", position=(0, 0, -20)),
                               NodeConfig(id="auv_02", position=(30, 0, -20))])
    with holoocean.make(scenario_cfg=config, show_viewport=False, ticks_per_sec=HZ, frames_per_sec=False) as env, \
            NetworkSession(scenario, port=args.port, manage_engine=args.port is None) as net:
        link = HoloOceanLink(net, {"leader": "auv_01", "follower": "auv_02"}, ticks_per_sec=HZ)
        link.attach(env.tick())
        net.node("auv_02").on_receive(
            lambda d: print(f"t={d.network_time:6.2f} s follower received {d.message.json()}"))
        leader = net.node("auv_01")
        for tick in range(int(args.seconds * HZ)):
            if tick % (2 * HZ) == 0:
                leader.send_json("auv_02", {"leader_x": round(leader.pose.x, 2)})  # its own pose only
            env.act("leader", [tick / HZ, 0, -20, 0, 0, 0])      # the application controls motion
            env.act("follower", [30, 0, -20, 0, 0, 0])
            link.sync(env.tick())
        print(net.summary()["received"], "messages delivered by DESERT")


if __name__ == "__main__":
    main()
