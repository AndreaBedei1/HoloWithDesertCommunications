"""Small controlled experiments on the real Docker DESERT engine.

These are fixed network fixtures, not HoloOcean E2E tests. Nothing is persisted
unless --output is explicitly supplied. Exit nonzero if the required qualitative
checks fail; results are never used to replace simulated outcomes.
"""
import argparse
from dataclasses import replace
import json
from pathlib import Path

from holo_desert.common.models import Message, Pose
from holo_desert.desert_adapter.backend import DESERTAdapter, COMPOSE, docker_command
from holo_desert.scenarios.config import ScenarioManager


def measure(*, distance=30, bitrate=4800, power=135, relay=False, concurrent=False):
    scenario = ScenarioManager().load("e05_multihop" if relay else "e01_chat")
    scenario.network.acoustic.tx_power_db = power
    scenario.network.acoustic.bitrate_bps = bitrate
    if relay:
        for index, node in enumerate(scenario.nodes):
            node.position = (index * distance, 0, -100)
    else:
        scenario.nodes[0].position = (0, 0, -100)
        scenario.nodes[1].position = (distance, 0, -100)
    backend = DESERTAdapter(manage_docker=False)
    try:
        backend.start(scenario)
        for node in scenario.nodes:
            backend.update_node_position(node.id, Pose(*node.position), 0)
        destination = scenario.nodes[-1].id
        message = Message("auv_01", destination, b"controlled-channel-experiment", 0, ttl=60)
        backend.send(message)
        if concurrent:
            backend.send(Message(destination, "auv_01", b"concurrent", 0, ttl=60))
        backend.request_stats()
        events = backend.advance(30)
        backend.request_stats()
        events += backend.advance(31)
        reception = [e for e in events if e["event"] == "rx" and Message.decode(bytes.fromhex(e["wire_hex"])).id == message.id]
        forwards = [e["node"] for e in events if e["event"] == "forward" and Message.decode(bytes.fromhex(e["wire_hex"])).id == message.id]
        return {"distance_m": distance, "bitrate_bps": bitrate, "tx_power_db": power,
                "relay": relay, "concurrent": concurrent,
                "received": bool(reception), "delay_s": reception[0]["time"] if reception else None,
                "forwarding_nodes": forwards,
                "mac_counters": [e for e in events if e["event"] == "stats" and e["time"] == 30]}
    finally:
        backend.stop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--sweep", action="store_true", help="Explore a small explicitly reported power range")
    args = parser.parse_args()
    owned = not DESERTAdapter().health()
    if owned:
        docker_command(*COMPOSE, "up", "-d", "--build", timeout=1200)
    try:
        results = [measure(), measure(distance=500), measure(bitrate=1200),
                   measure(power=0), measure(concurrent=True)]
        powers = (100, 105, 110, 115, 120, 125) if args.sweep else (115,)
        for power in powers:
            results.append(measure(distance=500, power=power, relay=True))
            results.append(measure(distance=1000, power=power))
        text = json.dumps(results, indent=2)
        print(text)
        if args.output:
            args.output.write_text(text + "\n", encoding="utf-8")
        return 0 if (results[0]["received"] and results[1]["received"] and results[2]["received"]
                     and results[1]["delay_s"] > results[0]["delay_s"]
                     and results[2]["delay_s"] > results[0]["delay_s"]
                     and not results[3]["received"]) else 1
    finally:
        if owned:
            docker_command(*COMPOSE, "down", timeout=30)


if __name__ == "__main__":
    raise SystemExit(main())
