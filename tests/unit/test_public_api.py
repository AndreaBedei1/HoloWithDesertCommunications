"""Public API contract with a scripted transport; no Docker, HoloOcean or dashboard."""
import json
import subprocess
import sys
import zipfile

import pytest

import holo_desert
from holo_desert import HoloOceanLink, NetworkSession, Pose, SessionError, load_scenario, pose_from_sensors
from holo_desert.common.models import Message


class ScriptedBackend:
    """Records commands; echoes each SEND as an rx at a fixed network delay."""
    __test__ = False
    pause_supported = True

    def __init__(self, delay=0.25, fail_at=None):
        self.delay, self.fail_at = delay, fail_at
        self.time, self.log, self.inflight = 0.0, [], []
        self.versions, self.initial_events = {"engine_fingerprint": "test"}, []
        self.stopped = 0

    def start(self, scenario):
        self.nodes = scenario.node_map
        self.time = 0.0

    def update_node_position(self, node, pose, timestamp):
        assert timestamp == pytest.approx(self.time)
        self.log.append(("POSITION", node, (pose.x, pose.y, pose.z), timestamp))

    def send(self, message):
        assert message.creation_time == pytest.approx(self.time)
        self.log.append(("SEND", message.source, message.destination, self.time))
        self.inflight.append((self.time + self.delay, message))

    def request_stats(self):
        self.log.append(("STATS", self.time))

    def advance(self, target):
        if self.fail_at is not None and target >= self.fail_at:
            from holo_desert.desert_adapter.backend import BackendError
            raise BackendError("engine died")
        events = [{"event": "position_applied", "node": n, "time": self.time} for n in self.nodes.values()]
        due = [(t, m) for t, m in self.inflight if t <= target + 1e-9]
        self.inflight = [(t, m) for t, m in self.inflight if t > target + 1e-9]
        for t, m in due:
            events.append({"event": "rx", "time": t, "node": self.nodes[m.destination],
                           "wire_hex": m.encode().hex(), "observed_wall_time": 0})
        self.time = target
        self.log.append(("STEP", target))
        return events

    def set_power(self, node, value):
        self.log.append(("POWER", node, value))

    def stop(self):
        self.stopped += 1


def session(**kw):
    backend = ScriptedBackend(**kw)
    return NetworkSession(load_scenario("e01_chat"), backend=backend), backend


def test_package_exports_and_no_gui_dependency():
    code = "import holo_desert,sys;print('fastapi' in sys.modules,'uvicorn' in sys.modules,'holoocean' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout
    assert out.split() == ["False", "False", "False"]
    for name in holo_desert.__all__:
        assert hasattr(holo_desert, name)


def test_operation_order_per_barrier_and_delivery_time():
    net, backend = session()
    with net:
        net.node("auv_01").send("auv_02", b"\x00\x01")
        net.update_pose("auv_02", (31, 0, -20))
        net.step()
        # Poses of all nodes, then the queued SEND, then STEP: all at t=0.
        kinds = [entry[0] for entry in backend.log]
        assert kinds == ["POSITION", "POSITION", "SEND", "STATS", "STEP"]
        assert backend.log[1][2] == (31, 0, -20)
        assert net.node("auv_02").receive() == []
        net.run_until(0.25)
        received = net.node("auv_02").receive()
        assert [d.message.payload for d in received] == [b"\x00\x01"]
        # Delivered at the tick barrier reaching the network timestamp, never earlier.
        assert received[0].network_time == pytest.approx(0.25) and net.time >= 0.25
        assert net.summary()["received"] == 1


def test_callbacks_replace_inbox_and_json_payload():
    net, _ = session()
    seen = []
    with net:
        net.node("auv_02").on_receive(lambda d: seen.append((d.message.message_type, d.message.json())))
        net.node("auv_01").send("auv_02", {"x": 1})
        net.run_until(1)
        assert seen == [("json", {"x": 1})]
        assert net.node("auv_02").receive() == []


def test_failure_marks_session_and_restart_recovers():
    net, backend = session(fail_at=0.5)
    net.start()
    with pytest.raises(SessionError, match="engine died"):
        net.run_until(1)
    assert net.state == "failed"
    with pytest.raises(SessionError):
        net.step()
    backend.fail_at = None
    net.restart()
    assert net.state == "running" and net.time == 0
    net.run_until(1)
    net.close()
    assert net.state == "closed" and backend.stopped >= 2


def test_validation_errors():
    net, _ = session()
    with net:
        with pytest.raises(ValueError):
            net.node("auv_99")
        with pytest.raises(ValueError):
            net.step(0)
        with pytest.raises(ValueError):
            net.update_pose("auv_01", (1, 2))
        with pytest.raises(ValueError):
            net.node("auv_01").send("auv_01", b"self")
        with pytest.raises(TypeError):
            net.node("auv_01").send_json("auv_02", b"raw")
    with pytest.raises(ValueError):
        HoloOceanLink(net, ticks_per_sec=net.scenario.physics_hz + 1)
    with pytest.raises(ValueError):
        HoloOceanLink(net, {"agent": "auv_42"})


def test_export_contains_summary(tmp_path):
    net, _ = session()
    with net:
        net.node("auv_01").send("auv_02", b"abc")
        net.run_until(1)
        path = net.export(tmp_path / "run.zip")
    with zipfile.ZipFile(path) as archive:
        assert {"config.json", "events.jsonl", "packets.csv", "summary.json"} <= set(archive.namelist())
        assert json.loads(archive.read("summary.json"))["received"] == 1


def test_persisted_runs_are_separate(tmp_path):
    net, _ = session()
    net = NetworkSession(load_scenario("e01_chat"), backend=ScriptedBackend(), persist=tmp_path)
    net.start(); net.step(); net.restart(); net.step(); net.close()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["run-001", "run-002"]


def dynamics(x, y, z, roll=0, pitch=0, yaw=0):
    data = [0.0] * 18
    data[6:9], data[15:18] = [x, y, z], [roll, pitch, yaw]
    return data


def test_pose_readers():
    assert pose_from_sensors({"DynamicsSensor": dynamics(1, 2, -3, 4, 5, 6)}) == Pose(1, 2, -3, 6, 5, 4)
    with pytest.raises(ValueError):
        pose_from_sensors({"DynamicsSensor": [0.0] * 19})
    yaw90 = [[0, -1, 0, 5], [1, 0, 0, 6], [0, 0, 1, -7], [0, 0, 0, 1]]
    pose = pose_from_sensors({"PoseSensor": yaw90})
    assert (pose.x, pose.y, pose.z) == (5, 6, -7) and pose.yaw == pytest.approx(90)
    assert pose_from_sensors({"LocationSensor": [1, 2, 3], "RotationSensor": [10, 20, 30]}) == Pose(1, 2, 3, 30, 20, 10)
    with pytest.raises(ValueError):
        pose_from_sensors({"IMUSensor": []})


def test_holoocean_link_uses_poses_of_previous_tick():
    net, backend = session()
    link = HoloOceanLink(net, {"leader": "auv_01", "follower": "auv_02"}, ticks_per_sec=net.scenario.physics_hz)
    with net:
        link.attach({"leader": {"DynamicsSensor": dynamics(0, 0, -20)},
                     "follower": {"DynamicsSensor": dynamics(30, 0, -20)}})
        # The caller already ticked HoloOcean: the network covers that tick with
        # the poses measured at its start, then stores the new ones.
        link.sync({"leader": {"DynamicsSensor": dynamics(1, 0, -20)},
                   "follower": {"DynamicsSensor": dynamics(29, 0, -20)}})
        positions = [e for e in backend.log if e[0] == "POSITION"]
        assert [p[2][0] for p in positions] == [0, 30]
        link.sync({"leader": {"DynamicsSensor": dynamics(2, 0, -20)},
                   "follower": {"DynamicsSensor": dynamics(28, 0, -20)}})
        positions = [e for e in backend.log if e[0] == "POSITION"]
        assert [p[2][0] for p in positions[2:]] == [1, 29]
        assert net.node("auv_01").pose.x == 2
        before = net.time
        with pytest.raises(KeyError):
            link.sync({"leader": {"DynamicsSensor": dynamics(3, 0, -20)}})
        assert net.time == before


def test_message_creation_time_equals_barrier():
    net, backend = session()
    with net:
        net.run_until(0.5)
        net.node("auv_01").send("auv_02", b"t")
        net.step()
        sends = [e for e in backend.log if e[0] == "SEND"]
        assert sends == [("SEND", "auv_01", "auv_02", pytest.approx(0.5))]
    assert isinstance(Message.decode(Message("auv_01", "auv_02", b"", 0).encode()), Message)
