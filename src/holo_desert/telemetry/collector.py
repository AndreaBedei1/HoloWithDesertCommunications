from __future__ import annotations

from collections import deque
from dataclasses import asdict
import copy
import csv
import io
import json
import math
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
        self.mac_specific_stats = {}
        self.application_states = {}
        self.transitions = deque(maxlen=100)
        self.observations = deque(maxlen=300)
        self.mac_nodes = {}
        self.queue_peak = None
        self.node_phy = {}
        self.series = deque(maxlen=1000)
        self.generated_count = self.received_count = self.expired_count = 0
        self.generated_bytes = self.received_bytes = self.wire_received_bytes = 0
        self.delay_sum = 0.0
        self.last_sample = 0.0
        self.last_bytes = self.last_wire_bytes = 0
        self.time = 0.0
        self.network_metrics = dict(data_tx_frames=0,control_tx_frames=0,data_tx_bits=0,control_tx_bits=0,data_airtime_s=0,control_airtime_s=0,late_received=0)
        self.phy_errors = {"noise_error": 0, "interference_error": 0, "not_synchronized": 0}

    def emit(self, event, timestamp, **fields):
        data = {"event": event, "time": timestamp, "wall_time": time.time(), **fields}
        with self.lock:
            if event == 'late_receive':
                self.network_metrics['late_received'] += 1
                row=self.packets.get(fields.get('packet_id'))
                if row:
                    row['late_receive_time']=timestamp
                    self._packet_event(row,data)
            self.events.append(data)
            if event in ("application_state", "power_applied"):
                self.transitions.append(data)
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
                if self.packets[old]["status"] in ("queued", "in_flight", "phy_tx_observed"):
                    raise BufferError("Too many pending packets; reduce traffic or TTL")
                self.packet_order.popleft()
                del self.packets[old]
            self.emit("generated", message.creation_time, packet_id=message.id, source=message.source,
                      destination=message.destination, size=len(message.payload), wire_size=len(message.encode()))

    def engine_event(self, event, inverse):
        with self.lock:
            if event['event'] in ('phy_tx_start','phy_control_tx_start'):
                prefix='control' if event['event']=='phy_control_tx_start' else 'data'
                self.network_metrics[prefix+'_tx_frames'] += 1
                for suffix, source in (('_tx_bits','phy_bits'),('_airtime_s','duration_s')):
                    key=prefix+suffix
                    self.network_metrics[key]=(self.network_metrics[key]+event[source] if self.network_metrics[key] is not None and source in event else None)
            data = {k: v for k, v in event.items() if k != "wire_hex"}
            if "node" in data:
                data["node_id"] = inverse[data["node"]]
            if event["event"] == "node_info":
                self.mac_nodes[event["mac_address"]] = data["node_id"]
            if "next_hop_mac" in data:
                data["next_hop_id"] = self.mac_nodes.get(data["next_hop_mac"])
            if "transmitter_mac" in data:
                data["transmitter_id"] = self.mac_nodes.get(data["transmitter_mac"])
            if "next_hop_address" in data:
                data["next_hop_id"] = inverse.get(data["next_hop_address"])
            if "wire_hex" in event:
                message = Message.decode(bytes.fromhex(event["wire_hex"]))
                data["packet_id"] = message.id
                row = self.packets.get(message.id)
                if row:
                    self._packet_event(row, data)
                    if event["event"] == "app_tx":
                        row["status"] = "in_flight"
                        row["network_tx_time"] = event["time"]
                    if event["event"] == "phy_tx_start":
                        row.setdefault("physical_tx_time", event["time"])
                        if row["status"] in ("queued", "in_flight"):
                            row["status"] = "phy_tx_observed"
                if event["event"] == "phy_rx_end" and event.get("outcome") in self.phy_errors:
                    self.phy_errors[event["outcome"]] += 1
                if event["event"] in ("forward", "phy_tx_start", "phy_rx_start", "phy_rx_end", "rx"):
                    self.observations.append(data)
                if event["event"] == "phy_rx_end":
                    counters = self.node_phy.setdefault(data["node_id"], {})
                    outcome = event["outcome"]
                    counters[outcome] = counters.get(outcome, 0) + 1
            if event['event']=='mac_specific_stats':
                self.mac_specific_stats[data['node_id']]=data['values']
            if event["event"] == "stats":
                self.stats[inverse[event["node"]]] = data
                if data.get("mac_queue") is not None:
                    self.queue_peak = max(self.queue_peak or 0, data["mac_queue"])
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
                self._packet_event(self.packets[message.id], {"event": "delivered", "time": delivery.network_time,
                                                            "node_id": delivery.receiver})
            # This is an end-to-end application edge, not a physical one-hop claim.
            self.edges[f"{message.source}>{delivery.receiver}"] = {
                "source": message.source, "destination": delivery.receiver,
                "last_receive": delivery.network_time, "evidence": "application_receive",
            }
            self.emit("delivered", delivery.network_time, packet_id=message.id,
                      source=message.source, destination=delivery.receiver, delay=delay,
                      observed_wall_time=delivery.transport_observed_wall_time, size=len(message.payload))

    def positions(self, poses: dict[str, Pose], timestamp, origin="holoocean"):
        with self.lock:
            self.fleet = {node: asdict(pose) for node, pose in poses.items()}
            for node, pose in poses.items():
                self.trails.setdefault(node, deque(maxlen=200)).append([pose.x, pose.y])
            # One event per fleet snapshot, no hidden trajectory/physics in DESERT.
            self.emit("fleet", timestamp, nodes=self.fleet, origin=origin)

    def sample(self, timestamp, drift=0):
        with self.lock:
            self.time = timestamp
            for row in self.packets.values():
                if row["status"] in ("queued", "in_flight", "phy_tx_observed") and timestamp > row["deadline"]:
                    row["status"] = "timeout_unknown_cause"
                    self._packet_event(row, {"event": "ttl_expired", "time": timestamp, "cause": "unknown"})
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
                point["nodes"] = {node: {"mac_queue": self.stats.get(node, {}).get("mac_queue"),
                                          "stats_time": self.stats.get(node, {}).get("time"),
                                          "phy": dict(self.node_phy.get(node, {}))}
                                  for node in self.fleet}
                point["distances_m"] = self._distances()
                self.series.append(point)
                self.emit("metrics", timestamp, **{k: v for k, v in point.items() if k != "time"})
                self.last_sample, self.last_bytes, self.last_wire_bytes = timestamp, self.received_bytes, self.wire_received_bytes

    def snapshot(self):
        with self.lock:
            return copy.deepcopy({"time": self.time, "fleet": dict(self.fleet),
                    "trails": {k: list(v) for k, v in self.trails.items()},
                    "edges": list(self.edges.values()), "stats": dict(self.stats), "mac_specific_stats":self.mac_specific_stats,
                    "observations": list(self.observations), "configured_routes": self.configured_routes(),
                    "applications": self.application_states, "transitions": list(self.transitions),
                    "distances_m": self._distances(), "node_phy": self.node_phy, "network_metrics": self.network_metrics,
                    "packets": [dict(self.packets[k]) for k in list(self.packet_order)[-500:]],
                    "events": list(self.events)[-100:], "series": list(self.series),
                    "counts": {"generated": self.generated_count, "received": self.received_count,
                               "timed_out": self.expired_count,
                               "pending": self.generated_count - self.received_count - self.expired_count}})

    @staticmethod
    def _packet_event(row, data):
        row["events"].append(data)
        if len(row["events"]) > 256:
            row["events"].pop(0)
            row["omitted_events"] = row.get("omitted_events", 0) + 1

    def applications(self, states):
        with self.lock:
            self.application_states = states

    def _distances(self):
        nodes = list(self.fleet)
        return {f"{a}>{b}": math.dist([self.fleet[a][k] for k in ("x", "y", "z")],
                                     [self.fleet[b][k] for k in ("x", "y", "z")])
                for i, a in enumerate(nodes) for b in nodes[i + 1:]}

    def configured_routes(self):
        if self.config["network"].get("routing", "static") != "static":
            return []
        ids = [n["id"] for n in self.config["nodes"]]
        routes = self.config["network"]["routes"]
        return [{"source": src, "destination": dst,
                 "next_hop": routes.get(src, {}).get(dst, dst),
                 "explicit": dst in routes.get(src, {})}
                for src in ids for dst in ids if src != dst]

    def summary(self):
        with self.lock:
            resolved = self.received_count + self.expired_count
            return {"duration_s": self.time, "generated": self.generated_count, "received": self.received_count,
                    "pending": self.generated_count - resolved, "timed_out": self.expired_count,
                    "pdr_resolved": self.received_count / resolved if resolved else None,
                    "pdr_generated": self.received_count / self.generated_count if self.generated_count else None,
                    "goodput_bps": 8 * self.received_bytes / self.time if self.time else None,
                    "application_wire_throughput_bps": 8 * self.wire_received_bytes / self.time if self.time else None,
                    "mean_latency_s": self.delay_sum / self.received_count if self.received_count else None,
                    "phy_observations": dict(self.phy_errors), "mac_queue_peak": self.queue_peak, "network_metrics": dict(self.network_metrics), "mac_stats": copy.deepcopy(self.stats), "mac_specific_stats":copy.deepcopy(self.mac_specific_stats)}

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
