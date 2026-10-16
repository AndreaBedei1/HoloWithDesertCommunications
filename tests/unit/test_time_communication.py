import json
import pytest
from holo_desert.common.models import Message, Delivery
from holo_desert.communications.manager import CommunicationManager
from holo_desert.synchronization.clock import ClockSynchronizer


class TestOnlyBackend:
    __test__ = False
    limit = 4096
    def __init__(self):
        self.sent = []
    def send(self, message):
        self.sent.append(message)


class TestOnlyTelemetry:
    __test__ = False
    def __init__(self):
        self.events = []
    def emit(self, *args, **kwargs):
        self.events.append((args, kwargs))
    def generated(self, message):
        pass
    def received(self, delivery):
        self.events.append(delivery)


def setup_manager(limit=1000):
    clock = ClockSynchronizer(10, False)
    backend = TestOnlyBackend()
    telemetry = TestOnlyTelemetry()
    manager = CommunicationManager(backend, clock, telemetry, ["auv_01", "auv_02"], queue_limit=limit)
    return clock, backend, telemetry, manager


def event(message, timestamp):
    return {"event": "rx", "time": timestamp, "node": 2,
            "wire_hex": message.encode().hex(), "observed_wall_time": 9999}


def test_no_early_delivery_and_network_order():
    clock, backend, telemetry, manager = setup_manager()
    late = Message("auv_01", "auv_02", b"later", 0)
    early = Message("auv_01", "auv_02", b"earlier", 0)
    manager.ingest(event(late, .3), {2: "auv_02"})
    manager.ingest(event(early, .1), {2: "auv_02"})
    manager.deliver_due()
    assert not manager.receive("auv_02")
    clock.step()
    manager.deliver_due()
    assert manager.receive("auv_02")[0].message == early
    clock.step()
    clock.step()
    manager.deliver_due()
    assert manager.receive("auv_02")[0].message == late


def test_duplicate_suppression():
    clock, backend, telemetry, manager = setup_manager()
    message = Message("auv_01", "auv_02", b"same", 0)
    for _ in range(2):
        manager.ingest(event(message, 0), {2: "auv_02"})
    manager.deliver_due()
    assert len(manager.receive("auv_02")) == 1


def test_send_queue_json_and_capacity():
    clock, backend, telemetry, manager = setup_manager(1)
    drone = manager.drone("auv_01")
    drone.send(destination="auv_02", payload={"hello": "sea"})
    with pytest.raises(BufferError):
        drone.send("auv_02", b"overflow")
    manager.flush()
    assert backend.sent[0].json() == {"hello": "sea"}
    with pytest.raises(ValueError):
        drone.send("auv_99", b"bad")


def test_bad_receiver_and_negative_latency():
    clock, backend, telemetry, manager = setup_manager()
    message = Message("auv_01", "auv_02", b"x", 2)
    with pytest.raises(RuntimeError):
        manager.ingest(event(message, 1), {2: "auv_02"})
    with pytest.raises(RuntimeError):
        manager.ingest(event(message, 3), {2: "auv_01"})


def test_logical_clock_pause_and_wall_separation():
    clock = ClockSynchronizer(30)
    for _ in range(3):
        clock.step()
    assert clock.time == .1
    clock.verify(.1)
    with pytest.raises(RuntimeError):
        clock.verify(.2)
    clock.pause()
    old = clock.time
    clock.resume()
    assert clock.time == old
    assert not clock.can_deliver(.11)
