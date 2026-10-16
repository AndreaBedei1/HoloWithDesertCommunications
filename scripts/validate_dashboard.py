"""Small explicit HTTP audit of existing demos. Real HoloOcean + DESERT only.

Run the dashboard first. This is API validation, not a browser/visual test.
No results persist unless --output is supplied. One session at a time.
"""
import argparse
import io
import json
from pathlib import Path
import time
import zipfile

import httpx


def request(client, method, path, **kwargs):
    response = client.request(method, path, **kwargs)
    response.raise_for_status()
    return response


def validate(client, name, mac):
    config = request(client, "GET", "/api/scenarios/" + name).json()
    config["realtime"] = False
    config["network"]["mac"]["protocol"] = mac
    request(client, "POST", "/api/validate", json=config)
    request(client, "POST", "/api/start", json={"configuration": config})
    deadline, latencies, paused = time.monotonic() + 240, [], False
    while True:
        started = time.monotonic()
        state = request(client, "GET", "/api/state").json()
        latencies.append(time.monotonic() - started)
        assert not state.get("error"), state.get("error")
        if name == "e03_mobility" and not paused and state["state"] == "running" and state["time"] > .3:
            request(client, "POST", "/api/pause")
            while request(client, "GET", "/api/state").json()["state"] != "paused":
                assert time.monotonic() < deadline
                time.sleep(.02)
            before = request(client, "GET", "/api/state").json()["time"]
            time.sleep(.15)
            assert request(client, "GET", "/api/state").json()["time"] == before
            request(client, "POST", "/api/resume")
            paused = True
        if state["state"] in ("finished", "failed", "stopped"):
            break
        assert time.monotonic() < deadline, "Dashboard run timed out"
        time.sleep(.1)
    assert state["state"] == "finished" and all(v == "stopped" for v in state["services"].values())
    assert len(state["fleet"]) == len(config["nodes"])
    assert state["series"][-1]["distances_m"]
    assert all(e.get("next_hop_id") for e in state["observations"] if e["event"] == "phy_tx_start")
    with zipfile.ZipFile(io.BytesIO(request(client, "GET", "/api/export").content)) as archive:
        events = [json.loads(line) for line in archive.read("events.jsonl").splitlines()]
    assert not any(e["event"] in ("cleanup_error", "run_error") for e in events)
    assert sum(e["event"] == "delivered" for e in events) == state["counts"]["received"]
    distances = [p["distances_m"]["auv_01>auv_02"] for p in state["series"]]
    if name == "e03_mobility":
        assert max(distances) > 70 and distances[-1] < 21 and paused
    if name == "e05_multihop":
        assert state["counts"]["received"] == 3
        assert any(e["event"] == "forward" and e.get("node_id") == "auv_02" for e in events)
        assert {(e["node_id"], e["next_hop_id"]) for e in events if e["event"] == "phy_tx_start"} == {("auv_01", "auv_02"), ("auv_02", "auv_03")}
    if name == "e06_coordination":
        assert [e["state"] for e in state["transitions"] if e["event"] == "application_state" and e["node"] == "auv_02"] == ["HOLD", "PROCEED", "HOLD", "PROCEED"]
        assert state["applications"]["auv_02"]["last_heartbeat_s"] > 18
        assert sum(e["event"] == "power_applied" for e in state["transitions"]) == 2
    summary = {"scenario": name, "mac": mac, "counts": state["counts"],
               "state": state["state"], "services": state["services"],
               "max_state_http_seconds": round(max(latencies), 3),
               "distance_min_max_end_m": [min(distances), max(distances), distances[-1]],
               "transitions": state["transitions"], "series_samples": len(state["series"])}
    if name == "e04_congestion":
        request(client, "POST", "/api/comparison")
    request(client, "POST", "/api/reset")
    assert request(client, "GET", "/api/state").json()["state"] == "idle"
    print(json.dumps(summary), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = {"runs": []}
    with httpx.Client(base_url=args.url, timeout=45) as client:
        assert request(client, "GET", "/api/state").json()["state"] == "idle", "Dashboard must be idle"
        for asset in ("/", "/static/app.js", "/static/maps.js", "/static/configuration.js", "/static/charts.js", "/static/packets.js", "/static/ui.js"):
            response = request(client, "GET", asset)
            if asset.endswith(".js"):
                assert response.headers["content-type"].startswith(("text/javascript", "application/javascript"))
        for name, mac in (("e03_mobility", "csma_aloha"), ("e04_congestion", "csma_aloha"),
                          ("e04_congestion", "aloha"), ("e05_multihop", "csma_aloha"), ("e06_coordination", "csma_aloha")):
            result["runs"].append(validate(client, name, mac))
            if args.output:
                args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        result["comparison"] = request(client, "GET", "/api/comparisons").json()
        assert result["comparison"]["equivalent"]
    if args.output:
        args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
