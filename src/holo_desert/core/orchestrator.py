from __future__ import annotations

from dataclasses import asdict
import importlib.metadata
import math
from pathlib import Path
import threading
import time
import uuid

from ..common.coordinates import CoordinateConverter
from ..communications.manager import CommunicationManager
from ..desert_adapter.backend import DESERTAdapter
from ..holoocean_adapter.adapter import HoloOceanAdapter, StaticNetworkFixture
from ..synchronization.clock import ClockSynchronizer
from ..telemetry.collector import TelemetryCollector
from .applications import TrafficApplication, HeartbeatCoordinator


class SimulationOrchestrator:
    def __init__(self, scenario, *, standalone=False, manage_docker=True, persist=None,
                 backend=None, physics=None, show_viewport=True, application_factory=None):
        self.scenario = scenario
        self.run_id = str(uuid.uuid4())
        self.standalone = standalone
        self.backend = backend or DESERTAdapter(manage_docker=manage_docker)
        self.physics = physics or (StaticNetworkFixture(scenario) if standalone else HoloOceanAdapter(scenario, show_viewport))
        self.converter = CoordinateConverter()
        self.telemetry = TelemetryCollector(scenario.model_dump(), Path(persist) if persist else None)
        self.clock = ClockSynchronizer(scenario.physics_hz, scenario.realtime)
        self.communication = CommunicationManager(self.backend, self.clock, self.telemetry, scenario.node_map,
                                                  max_message_bytes=scenario.network.max_wire_bytes)
        self.inverse = {v: k for k, v in scenario.node_map.items()}
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.state = "idle"
        self.error = None
        self.services = {"holoocean": "not_started" if not standalone else "standalone_fixture", "desert": "not_started"}
        self.thread = None
        self.lock = threading.RLock()
        self.applications = {}
        self.application_factory = application_factory
        self._make_applications()

    def _make_applications(self):
        for i, node in enumerate(self.scenario.nodes):
            comm = self.communication.drone(node.id)
            if self.application_factory:
                self.applications[node.id] = self.application_factory(node, comm, self.scenario)
            elif self.scenario.coordination:
                peer = self.scenario.nodes[1 - i].id
                target = (node.position[0] + 20, node.position[1], node.position[2])
                self.applications[node.id] = HeartbeatCoordinator(comm, peer, target, leader=i == 0)
            else:
                self.applications[node.id] = TrafficApplication(comm, [f for f in self.scenario.flows if f.source == node.id])

    def start_background(self):
        with self.lock:
            if self.state != "idle":
                raise RuntimeError("Create/reset a run before starting")
            self.state = "starting"
            self.thread = threading.Thread(target=self.run, name="holo-desert-simulation", daemon=True)
            self.thread.start()

    def run(self):
        self.state = "starting"
        terminal_state = "stopped"
        try:
            self.services["desert"] = "starting"
            self.backend.start(self.scenario)
            for event in getattr(self.backend, "initial_events", []):
                self.telemetry.engine_event(event, self.inverse)
            self.services["desert"] = "running"
            if not self.standalone:
                self.services["holoocean"] = "starting"
            poses = self.physics.start()
            if not self.standalone:
                self.services["holoocean"] = "running"
            self.clock = ClockSynchronizer(self.scenario.physics_hz, self.scenario.realtime)
            self.communication.clock = self.clock
            versions = {"platform": importlib.metadata.version("holoocean-desert"), "desert": "4.0.0",
                        "holoocean": None if self.standalone else importlib.metadata.version("holoocean"),
                        "engine": self.backend.versions}
            self.telemetry.emit("run_started", 0, versions=versions, seed=self.scenario.network.seed,
                                rng_substream=self.scenario.network.seed,
                                mode="desert_standalone" if self.standalone else "integrated",
                                node_map=self.scenario.node_map)
            self.state = "running"
            power_events = list(sorted(self.scenario.power_events, key=lambda e: e.time))
            ticks = math.ceil(self.scenario.duration * self.scenario.physics_hz)
            last_pose_time = -1.0
            for tick in range(ticks):
                if self.stop_event.is_set():
                    break
                if self.pause_event.is_set():
                    self.clock.pause()
                    self.state = "paused"
                    # NS is blocked in its current barrier, HoloOcean in shared-memory wait.
                    while self.pause_event.is_set() and not self.stop_event.wait(0.05):
                        pass
                    self.clock.resume()
                    self.state = "running"
                    if self.stop_event.is_set():
                        break
                now = self.clock.time
                self.clock.verify(self.backend.time)
                # Each geometry sample applies before all SENDs at this barrier.
                for node, pose in poses.items():
                    self.backend.update_node_position(node, self.converter.to_network(pose), now)
                while power_events and power_events[0].time <= now + 1e-9:
                    event = power_events.pop(0)
                    self.backend.set_power(event.node, event.tx_power_db)
                for node in self.scenario.nodes:
                    application = self.applications[node.id]
                    previous = getattr(application, "state", None)
                    action = application.update(now, poses[node.id], self.communication.drone(node.id).receive())
                    if getattr(application, "state", None) != previous:
                        self.telemetry.emit("application_state", now, node=node.id, state=application.state)
                    if action is not None:
                        self.physics.command(node.id, action)
                    elif not self.standalone and node.waypoints:
                        target = node.position
                        # Piecewise-linear desired pose; actual trajectory is always HoloOcean's.
                        points = [(0.0, *node.position), *node.waypoints]
                        for left, right in zip(points, points[1:]):
                            if left[0] <= now <= right[0]:
                                ratio = (now - left[0]) / max(right[0] - left[0], 1e-9)
                                target = tuple(left[j] + ratio * (right[j] - left[j]) for j in (1, 2, 3))
                                break
                            if now > right[0]:
                                target = right[1:]
                        self.physics.command(node.id, (*target, 0, 0, node.yaw))
                self.communication.flush()
                if tick % self.scenario.physics_hz == 0:
                    self.backend.request_stats()
                # Advance physical clock once, then consume network events up to that time.
                poses = self.physics.tick()
                target = self.clock.step()
                events = self.backend.advance(target)
                self.clock.verify(self.backend.time)
                applied = set()
                for event in events:
                    self.telemetry.engine_event(event, self.inverse)
                    if event["event"] == "position_applied":
                        applied.add(event["node"])
                    elif event["event"] == "rx":
                        self.communication.ingest(event, self.inverse)
                if applied != set(self.inverse):
                    raise RuntimeError("DESERT did not acknowledge every physics position update")
                self.communication.deliver_due()
                if self.clock.time - last_pose_time >= 0.1:
                    self.telemetry.positions(poses, self.clock.time,
                                             origin="standalone_fixture" if self.standalone else "holoocean")
                    last_pose_time = self.clock.time
                self.telemetry.sample(self.clock.time, self.clock.drift)
                self.clock.pace(self.stop_event)
            terminal_state = "stopped" if self.stop_event.is_set() else "finished"
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"
            terminal_state = "failed"
            self.telemetry.emit("run_error", self.clock.time, reason=self.error)
        finally:
            self.state = "stopping"
            for name, component in (("holoocean", self.physics), ("desert", self.backend)):
                try:
                    component.stop()
                    if self.services[name] in ("running", "starting"):
                        self.services[name] = "stopped"
                except Exception as exc:
                    self.telemetry.emit("cleanup_error", self.clock.time, service=name, reason=str(exc))
                    self.services[name] = "cleanup_failed"
                    self.error = self.error or f"Failed to stop {name}: {exc}"
                    terminal_state = "failed"
            self.state = terminal_state
            self.telemetry.emit("run_ended", self.clock.time, state=self.state)

    def stop(self):
        self.stop_event.set()
        self.pause_event.clear()

    def pause(self):
        if self.state != "running" or not self.backend.pause_supported:
            raise RuntimeError("Pause is unavailable in this state/backend")
        self.pause_event.set()

    def resume(self):
        if self.state != "paused":
            raise RuntimeError("Simulation is not paused")
        self.pause_event.clear()

    def snapshot(self):
        self.telemetry.applications({node: app.snapshot(self.clock.time)
                                     for node, app in self.applications.items() if hasattr(app, "snapshot")})
        return {"state": self.state, "error": self.error, "services": dict(self.services),
                "run_id": self.run_id,
                "standalone": self.standalone, "configuration": self.scenario.model_dump(),
                "pause_supported": self.backend.pause_supported, **self.telemetry.snapshot()}

    def close(self):
        self.stop()
        if self.thread:
            self.thread.join(timeout=40)
            if self.thread.is_alive():
                raise RuntimeError("Simulation is still shutting down; cannot reset yet")
        self.telemetry.close()
