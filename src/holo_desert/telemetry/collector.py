from __future__ import annotations

from collections import deque
from dataclasses import asdict
import csv
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import zipfile

from ..common.models import Message, Delivery, Pose


class TelemetryCollector:
    """Bounded dashboard memory; ordinary artifacts live in an owned temp dir."""
    def __init__(self, config, persist: Path | None = None):
        self.lock = threading.RLock()
        self.config = config
        self._temp = tempfile.TemporaryDirectory(prefix="holo-desert-") if persist is None else None
        self.directory = Path(self._temp.name) if self._temp else Path(persist)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.config_path = self.directory / "config.json"
        self.config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        self.log = (self.directory / "events.jsonl").open("w", encoding="utf-8", buffering=1)
        self.events = deque(maxlen=2000)
        self.packets = {}
        self.packet_order = deque()
        self.fleet = {}
        self.trails = {}
        self.edges = {}
        self.stats = {}
        self.series = deque(maxlen=1000)
        self.generated_count = self.received_count = self.expired_count = 0
        self.generated_bytes = self.received_bytes = self.wire_received_bytes = 0
        self.delay_sum = 0.0
        self.last_sample = 0.0
        self.last_bytes = self.last_wire_bytes = 0
        self.time = 0.0
        self.phy_errors = {"noise_error": 0, "interference_error": 0, "not_synchronized": 0}

    def emit(self, event, timestamp, **fields):
        data = {"event": event, "time": timestamp, "wall_time": time.time(), **fields}
        with self.lock:
            self.events.append(data)
            self.log.write(json.dumps(data, separators=(",", ":"), allow_nan=False) + "\n")

    def generated(self, message: Message):
        with self.lock:
            self.generated_count += 1
            self.generated_bytes += len(message.payload)
            self.packets[message.id] = {
                "id": message.id, "source": message.source, "destination": message.destination,
                "type": message.message_type, "size": len(message.payload), "wire_size": len(message.encode()),
                "creation_time": message.creation_time, "deadline": message.creation_time + message.ttl,
                "status": "queued", "delay": None, "protocol": self.config["network"]["mac"]["protocol"],
                "events": [], "payload_hex": message.payload.hex(),
            }
            self.packet_order.append(message.id)
            # Keep active packets until their deadline; prune only resolved old rows.
            while len(self.packet_order) > 5000:
                old = self.packet_order[0]
                if self.packets[old]["status"] in ("queued", "in_flight"):
                    raise BufferError("Too many pending packets; reduce traffic or TTL")
                self.packet_order.popleft()
                del self.packets[old]
            self.emit("generated", message.creation_time, packet_id=message.id, source=message.source,
                      destination=message.destination, size=len(message.payload), wire_size=len(message.encode()))

    def engine_event(self, event, inverse):
        with self.lock:
            data = {k: v for k, v in event.items() if k != "wire_hex"}
            if "node" in data:
                data["node_id"] = inverse[data["node"]]
            if "wire_hex" in event:
                message = Message.decode(bytes.fromhex(event["wire_hex"]))
                data["packet_id"] = message.id
                row = self.packets.get(message.id)
                if row:
                    row["events"].append(data)
                    if event["event"] == "app_tx":
                        row["status"] = "in_flight"
                        row["network_tx_time"] = event["time"]
                    if event["event"] == "phy_tx_start":
                        row.setdefault("physical_tx_time", event["time"])
                    if event["event"] == "phy_rx_end" and event.get("outcome") in self.phy_errors:
                        self.phy_errors[event["outcome"]] += 1
            if event["event"] == "stats":
                self.stats[inverse[event["node"]]] = data
            self.emit(data["event"], data["time"],
                      **{k: v for k, v in data.items() if k not in ("event", "time")}, origin="desert")

    def received(self, delivery: Delivery):
        message = delivery.message
        with self.lock:
            self.received_count += 1
            self.received_bytes += len(message.payload)
            self.wire_received_bytes += len(message.encode())
            delay = delivery.network_time - message.creation_time
            self.delay_sum += delay
            if message.id in self.packets:
                self.packets[message.id].update(status="received", receive_time=delivery.network_time, delay=delay)
            # This is an end-to-end application edge, not a physical one-hop claim.
            self.edges[f"{message.source}>{delivery.receiver}"] = {
                "source": message.source, "destination": delivery.receiver,
                "last_receive": delivery.network_time, "evidence": "application_receive",
            }
            self.emit("delivered", delivery.network_time, packet_id=message.id,
                      source=message.source, destination=delivery.receiver, delay=delay,
                      observed_wall_time=delivery.transport_observed_wall_time, size=len(message.payload))

    def positions(self, poses: dict[str, Pose], timestamp):
        with self.lock:
            self.fleet = {node: asdict(pose) for node, pose in poses.items()}
            for node, pose in poses.items():
                self.trails.setdefault(node, deque(maxlen=200)).append([pose.x, pose.y])
            # One event per fleet snapshot, no hidden trajectory/physics in DESERT.
            self.emit("fleet", timestamp, nodes=self.fleet, origin="holoocean")

    def sample(self, timestamp, drift=0):
        with self.lock:
            self.time = timestamp
            for row in self.packets.values():
                if row["status"] in ("queued", "in_flight") and timestamp > row["deadline"]:
                    row["status"] = "timeout_unknown_cause"
                    self.expired_count += 1
                    self.emit("timeout", timestamp, packet_id=row["id"], cause="unknown")
            if timestamp - self.last_sample >= 0.5:
                dt = timestamp - self.last_sample
                resolved = self.received_count + self.expired_count
                point = {"time": timestamp, "goodput_bps": 8 * (self.received_bytes - self.last_bytes) / dt,
                         "application_wire_throughput_bps": 8 * (self.wire_received_bytes - self.last_wire_bytes) / dt,
                         "pdr_resolved": self.received_count / resolved if resolved else None,
                         "mean_latency_s": self.delay_sum / self.received_count if self.received_count else None,
                         "generated": self.generated_count, "received": self.received_count,
                         "timed_out": self.expired_count,
                         "pending": self.generated_count - resolved, "wall_drift_s": drift,
                         "phy_noise_observations": self.phy_errors["noise_error"],
                         "phy_interference_observations": self.phy_errors["interference_error"],
                         "phy_unsynced_observations": self.phy_errors["not_synchronized"]}
                self.series.append(point)
                self.emit("metrics", timestamp, **{k: v for k, v in point.items() if k != "time"})
                self.last_sample, self.last_bytes, self.last_wire_bytes = timestamp, self.received_bytes, self.wire_received_bytes

    def snapshot(self):
        with self.lock:
            return {"time": self.time, "fleet": dict(self.fleet),
                    "trails": {k: list(v) for k, v in self.trails.items()},
                    "edges": list(self.edges.values()), "stats": dict(self.stats),
                    "packets": [dict(self.packets[k]) for k in list(self.packet_order)[-500:]],
                    "events": list(self.events)[-100:], "series": list(self.series),
                    "counts": {"generated": self.generated_count, "received": self.received_count,
                               "timed_out": self.expired_count,
                               "pending": self.generated_count - self.received_count - self.expired_count}}

    def export(self):
        with self.lock:
            self.log.flush()
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.write(self.config_path, "config.json")
                archive.write(self.directory / "events.jsonl", "events.jsonl")
                csv_file = io.StringIO()
                writer = csv.DictWriter(csv_file, fieldnames=["id", "source", "destination", "size", "wire_size", "creation_time", "status", "delay"])
                writer.writeheader()
                for row in self.packets.values():
                    writer.writerow({key: row.get(key) for key in writer.fieldnames})
                archive.writestr("packets.csv", csv_file.getvalue())
            return buffer.getvalue()

    def close(self):
        with self.lock:
            self.log.close()
            if self._temp:
                self._temp.cleanup()
