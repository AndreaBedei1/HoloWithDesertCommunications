"""Bundled advanced demos run on the real engine with fixed positions."""
import json
import zipfile

import pytest

from holo_desert import ManagedSimulation
from holo_desert.scenarios.config import RESOURCE_ROOT

pytestmark = pytest.mark.desert


def run_demo(name, tmp_path):
    path = RESOURCE_ROOT / "demos" / name / "scenario.yaml"
    with ManagedSimulation(str(path), holoocean=False, realtime=False, manage_engine=False) as sim:
        summary = sim.run()
        archive = sim.export(tmp_path / f"{name}.zip")
        packets = [dict(p) for p in sim._run.telemetry.packets.values()]
    with zipfile.ZipFile(archive) as z:
        events = [json.loads(line) for line in z.read("events.jsonl").decode().splitlines()]
    return summary, packets, events


def test_ranging_tokenbus_demo_reports_native_estimates(engine, tmp_path):
    summary, _, events = run_demo("e07_ranging_tokenbus", tmp_path)
    assert summary["generated"] >= 10 and summary["received"] == summary["generated"]
    estimates = {(e["peer_a"], e["peer_b"]): e["distance_m"] for e in events
                 if e["event"] == "ranging_estimate" and e["valid"]}
    # Configured geometry: 40 m, 60 m and sqrt(40^2+60^2) m between the three nodes.
    assert estimates[(1, 2)] == pytest.approx(40, abs=0.5)
    assert estimates[(1, 3)] == pytest.approx(60, abs=0.5)
    assert estimates[(2, 3)] == pytest.approx(72.11, abs=0.5)


def test_sun_demo_uses_native_relay_and_is_reproducible(engine, tmp_path):
    first, packets, _ = run_demo("e09_sun_convergecast", tmp_path)
    relayed = [p for p in packets if p["source"] == "auv_01" and p["status"] == "received" and
               any(e["event"] == "forward" and e.get("node_id") not in ("auv_01", "auv_04") for e in p["events"])]
    assert relayed, "SUN should deliver auv_01 traffic through a relay at probe_min_snr_db 30"
    second, _, _ = run_demo("e09_sun_convergecast", tmp_path)
    keys = ("generated", "received", "timed_out", "pending", "phy_observations", "network_metrics")
    assert {k: first[k] for k in keys} == {k: second[k] for k in keys}
