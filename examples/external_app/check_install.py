"""Smoke test of an installed holoocean-desert package, as an external project.

Uses only the public API. Without arguments it needs no Docker or HoloOcean:

    python check_install.py            # import, configuration and validation
    python check_install.py --engine   # plus one real DESERT round trip
"""
import argparse
import sys

import holo_desert
from holo_desert import Network, NetworkSession, NodeConfig, Scenario, list_examples, pose_from_sensors


def build_scenario() -> Scenario:
    return Scenario(
        name="external_check", description="Two static nodes 40 m apart",
        nodes=[NodeConfig(id="auv_01", position=(0, 0, -20)), NodeConfig(id="auv_02", position=(40, 0, -20))],
        network=Network.model_validate({"mac": {"protocol": "tdma"}}))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", action="store_true", help="exchange a message through DESERT")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    scenario = build_scenario()
    assert {"e01_chat", "e06_coordination"} <= set(list_examples())
    assert "fastapi" not in sys.modules, "library import must not load the dashboard"
    try:
        Network.model_validate({"routing": "flooding", "mac": {"protocol": "csma_ca"}})
        raise AssertionError("unsupported stack was accepted")
    except ValueError:
        pass
    assert pose_from_sensors({"LocationSensor": [1, 2, -3]}).z == -3
    print(f"holo_desert {holo_desert.__version__}: API, scenario and stack validation OK")
    if not args.engine:
        return 0
    with NetworkSession(scenario, port=args.port, manage_engine=False) as net:
        net.node("auv_01").send_json("auv_02", {"check": True})
        net.run_until(10)
        deliveries = net.node("auv_02").receive()
        assert [d.message.json() for d in deliveries] == [{"check": True}], deliveries
        print(f"DESERT round trip OK: latency {deliveries[0].network_time:.3f} s, "
              f"engine {net.engine_info.get('engine_fingerprint')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
