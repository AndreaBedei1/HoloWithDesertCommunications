from __future__ import annotations

from collections import deque
import heapq
import json
import itertools
from ..common.models import Message, Delivery


class DroneCommunication:
    """Per-drone capability; exposes no ground truth of other vehicles."""
    def __init__(self, manager, node):
        self._manager = manager
        self.node = node

    def send(self, destination, payload: bytes | dict, **options):
        if isinstance(payload, dict):
            return self.send_json(destination, payload, **options)
        return self._manager.send(self.node, destination, payload, **options)

    def send_json(self, destination, payload, **options):
        return self._manager.send(self.node, destination,
            json.dumps(payload, separators=(",", ":"), allow_nan=False).encode(), message_type="json", **options)

    def receive(self) -> list[Delivery]:
        return self._manager.receive(self.node)


class CommunicationManager:
    def __init__(self, backend, clock, telemetry, nodes, queue_limit=1000, max_message_bytes=4096, listeners=None):
        self.backend, self.clock, self.telemetry = backend, clock, telemetry
        self.nodes = set(nodes)
        self.inbox = {n: deque() for n in nodes}
        self.seen = {n: {} for n in nodes}
        self.outbox = deque()
        self.pending = []
        self.counter = itertools.count()
        self.queue_limit = queue_limit
        self.max_message_bytes = max_message_bytes
        # node -> callbacks. A node with callbacks receives deliveries through
        # them instead of its inbox, so an unread inbox cannot overflow.
        self.listeners = listeners if listeners is not None else {}
        self.callback_errors = []

    def drone(self, node):
        if node not in self.nodes:
            raise ValueError(f"Unknown node {node}")
        return DroneCommunication(self, node)

    def send(self, source, destination, payload, **options):
        if source not in self.nodes or destination not in self.nodes or source == destination:
            raise ValueError("Unicast requires two distinct configured nodes; broadcast is not supported")
        if len(self.outbox) >= self.queue_limit:
            raise BufferError("Application transmit queue is full")
        message = Message(source, destination, payload, self.clock.time, **options)
        if len(message.encode()) > self.max_message_bytes:
            raise ValueError("Encoded message exceeds configured communication payload limit")
        self.outbox.append(message)
        self.telemetry.generated(message)
        return message.id

    def flush(self):
        while self.outbox:
            message = self.outbox.popleft()
            self.backend.send(message)

    def ingest(self, event, inverse_nodes):
        message = Message.decode(bytes.fromhex(event["wire_hex"]))
        receiver = inverse_nodes[event["node"]]
        if receiver != message.destination:
            raise RuntimeError("DESERT delivered message to the wrong node")
        if event["time"] + 1e-9 < message.creation_time:
            raise RuntimeError("Network delivered a packet before creation")
        delivery = Delivery(message, receiver, event["time"], event["observed_wall_time"],
                            {k: v for k, v in event.items() if k != "wire_hex"})
        heapq.heappush(self.pending, (delivery.network_time, next(self.counter), delivery))

    def deliver_due(self):
        while self.pending and self.clock.can_deliver(self.pending[0][0]):
            _, _, delivery = heapq.heappop(self.pending)
            message = delivery.message
            seen = self.seen[delivery.receiver]
            # Bound duplicate history to the message validity window.
            for key, expiry in list(seen.items()):
                if expiry < self.clock.time:
                    del seen[key]
            if message.id in seen:
                self.telemetry.emit("duplicate", delivery.network_time, packet_id=message.id)
                continue
            seen[message.id] = message.creation_time + message.ttl
            if delivery.network_time > message.creation_time + message.ttl:
                self.telemetry.emit("late_receive", delivery.network_time, packet_id=message.id)
                continue
            callbacks = self.listeners.get(delivery.receiver)
            if not callbacks and len(self.inbox[delivery.receiver]) >= self.queue_limit:
                self.telemetry.emit("bridge_receive_overflow", delivery.network_time, packet_id=message.id)
                continue
            self.telemetry.received(delivery)
            if callbacks:
                for callback in list(callbacks):
                    try:
                        callback(delivery)
                    except Exception as exc:  # reported after the tick, never lost mid-delivery
                        self.callback_errors.append(exc)
            else:
                self.inbox[delivery.receiver].append(delivery)

    def receive(self, node):
        queue = self.inbox[node]
        result = list(queue)
        queue.clear()
        return result
