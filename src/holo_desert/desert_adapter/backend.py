from __future__ import annotations

import abc
import json
import math
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time

from ..common.models import Message, Pose
from ..scenarios.config import RESOURCE_ROOT, Scenario


class BackendError(RuntimeError):
    pass


class CommunicationBackend(abc.ABC):
    @abc.abstractmethod
    def start(self, scenario: Scenario): ...
    @abc.abstractmethod
    def send(self, message: Message): ...
    @abc.abstractmethod
    def validate_positions(self, poses: dict):
        """Raise ValueError for geometry the configured model rejects; sends nothing."""
        for pose in poses.values():
            if self.woss_depth is not None:
                from ..resources.docker.environment_config import validate_woss_position
                validate_woss_position((pose.x, pose.y, pose.z), self.woss_depth)
            if self.medium == 'optical' and not -20 <= pose.z < 0:
                raise ValueError('Optical noise LUT covers underwater depths through 20 m')
        if self.woss_depth is not None:
            from ..resources.docker.environment_config import validate_woss_separation
            validate_woss_separation([(p.x, p.y, p.z) for p in poses.values()])

    def update_node_position(self, node: str, pose: Pose, timestamp: float): ...
    @abc.abstractmethod
    def advance(self, target: float) -> list[dict]: ...
    @abc.abstractmethod
    def stop(self): ...


def docker_executable() -> str:
    executable = shutil.which("docker")
    if executable:
        return executable
    if os.name == "nt":
        candidate = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Docker/Docker/resources/bin/docker.exe"
        if candidate.is_file():
            return str(candidate)
    raise BackendError("Docker CLI unavailable. Install Docker Desktop or Docker Engine + Compose.")


def docker_command(*args, timeout=120, check=True):
    executable = docker_executable()
    env = dict(os.environ)
    env["PATH"] = str(Path(executable).parent) + os.pathsep + env.get("PATH", "")
    try:
        result = subprocess.run([executable, *args], capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=timeout, env=env)
    except subprocess.TimeoutExpired as exc:
        raise BackendError("Docker did not respond within the timeout. Check Docker Desktop's engine status.") from exc
    if check and result.returncode:
        detail = (result.stdout.strip() + "\n" + result.stderr.strip()).strip()
        raise BackendError(f"Docker failed: {detail[-12000:]}")
    return result


COMPOSE = ["compose", "-p", "holo-desert", "-f", str(RESOURCE_ROOT / "docker/compose.yaml")]


class DESERTAdapter(CommunicationBackend):
    """Synchronous, framed TCP client for the real NS-MIRACLE event scheduler."""
    pause_supported = True

    def __init__(self, host="127.0.0.1", port=None, manage_docker=True, timeout=30):
        self.host = host
        self.port = port or int(os.environ.get("DESERT_PORT", "5555"))
        self.manage_docker = manage_docker
        self.timeout = timeout
        self.socket = None
        self.reader = None
        self.time = 0.0
        self.nodes = {}
        self.limit = 4096
        self._owns_service = False
        self.versions = {}
        self.initial_events = []
        self.woss_depth = None
        self.medium = 'acoustic'

    def start(self, scenario: Scenario):
        if self.socket:
            raise BackendError("Backend already started")
        self.nodes = scenario.node_map
        from ..resources.docker.multiphy_config import effective_interfaces
        self.multi_interfaces = {n['id']:{p['id']:p['index'] for p in n['interfaces']} for n in effective_interfaces(scenario.model_dump())}
        self.multi_policy = scenario.network.multiphy.policy if scenario.network.multiphy else None
        self.limit = scenario.network.max_wire_bytes
        self.medium = scenario.network.medium
        self.woss_depth = scenario.network.woss.water_depth_m if self.medium=='acoustic' and scenario.network.acoustic.propagation=='woss' else None
        self.positions = {n.id:n.position for n in scenario.nodes}
        try:
            if self.manage_docker:
                # Reuse an existing healthy service; never tear down someone else's.
                if not self.health():
                    docker_command(*COMPOSE, "up", "-d", "--build", timeout=1200)
                    self._owns_service = True
                    deadline = time.monotonic() + 30
                    while not self.health():
                        if time.monotonic() >= deadline:
                            raise BackendError("DESERT service did not become healthy; run holo-desert logs")
                        time.sleep(0.25)
            self.socket = socket.create_connection((self.host, self.port), self.timeout)
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.reader = self.socket.makefile("rb")
            self.socket.sendall((scenario.model_dump_json() + "\n").encode())
            initial = self._until_barrier()
            self.initial_events = initial
            self.versions = next((e for e in initial if e["event"] == "engine_info"), {})
            from ..resources.docker.stack_builder import CATALOG_VERSION, engine_fingerprint
            expected = engine_fingerprint()
            if self.versions.get('stack_builder') != CATALOG_VERSION or self.versions.get('engine_fingerprint') != expected:
                raise BackendError(f"DESERT engine image is outdated or built from another base (engine "
                                   f"{self.versions.get('engine_fingerprint')} from {self.versions.get('desert_base_image')}, "
                                   f"package {expected}): rebuild with holo-desert engine up")
            if self.time != 0 or any(e["event"] == "rx" for e in initial):
                raise BackendError("DESERT did not initialize at time zero")
        except Exception:
            self.stop()
            raise

    def health(self):
        return self.health_info() is not None

    def health_info(self):
        """HEALTH reply of the service on this port, or None when unreachable."""
        try:
            with socket.create_connection((self.host, self.port), 1) as s:
                s.sendall(b"HEALTH\n")
                reply = json.loads(s.recv(4096))
                return reply if reply.get("event") == "health" else None
        except (OSError, ValueError):
            return None

    def _command(self, command: str):
        if self.socket is None:
            raise BackendError("DESERT is not started")
        try:
            self.socket.sendall((command + "\n").encode("ascii"))
        except OSError as exc:
            raise BackendError(f"DESERT transport disconnected: {exc}") from exc

    def _until_barrier(self):
        events = []
        try:
            while True:
                line = self.reader.readline(65536)
                if not line:
                    raise BackendError("DESERT process/socket closed unexpectedly; run holo-desert logs")
                event = json.loads(line)
                if event["event"] == "error" and event.get("reason") == "DESERT is busy":
                    raise BackendError(f"The DESERT service on port {self.port} is running another session "
                                       "(one session per service); wait for it or use another engine port")
                if event["event"] in ("error", "engine_exit"):
                    raise BackendError(f"DESERT: {event}")
                event["observed_wall_time"] = time.time()
                if event["event"] == "barrier":
                    self.time = float(event["time"])
                    return events
                events.append(event)
        except (OSError, ValueError) as exc:
            raise BackendError(f"Invalid or interrupted DESERT event stream: {exc}") from exc

    def send(self, message: Message):
        self._validate_environment_geometry()
        if abs(message.creation_time - self.time) > 1e-6:
            raise BackendError("Messages must be generated at the current synchronized barrier")
        wire = message.encode()
        if len(wire) > self.limit:
            raise ValueError(f"Encoded message is {len(wire)} bytes; maximum is {self.limit}")
        try:
            src, dst = self.nodes[message.source], self.nodes[message.destination]
        except KeyError as exc:
            raise ValueError(f"Unknown node: {exc}") from exc
        self._command(f"SEND {src} {dst} {wire.hex()}")

    def validate_positions(self, poses: dict):
        """Raise ValueError for geometry the configured model rejects; sends nothing."""
        for pose in poses.values():
            if self.woss_depth is not None:
                from ..resources.docker.environment_config import validate_woss_position
                validate_woss_position((pose.x, pose.y, pose.z), self.woss_depth)
            if self.medium == 'optical' and not -20 <= pose.z < 0:
                raise ValueError('Optical noise LUT covers underwater depths through 20 m')
        if self.woss_depth is not None:
            from ..resources.docker.environment_config import validate_woss_separation
            validate_woss_separation([(p.x, p.y, p.z) for p in poses.values()])

    def update_node_position(self, node: str, pose: Pose, timestamp: float):
        if not math.isfinite(timestamp) or abs(timestamp - self.time) > 1e-6:
            raise BackendError("Position timestamp must equal DESERT barrier time")
        if self.woss_depth is not None:
            from ..resources.docker.environment_config import validate_woss_position
            validate_woss_position((pose.x,pose.y,pose.z),self.woss_depth)
        if self.medium=='optical' and not -20<=pose.z<0:raise ValueError('Optical noise LUT covers underwater depths through 20 m')
        angles=(' '+' '.join(format(math.radians(v),'.12g') for v in (pose.yaw,pose.pitch,pose.roll))) if self.medium=='optical' else ''
        self._command(f"POSITION {self.nodes[node]} {pose.x:.12g} {pose.y:.12g} {pose.z:.12g} {timestamp:.12g}{angles}")
        self.positions[node]=(pose.x,pose.y,pose.z)

    def _validate_environment_geometry(self):
        if self.woss_depth is not None:
            from ..resources.docker.environment_config import validate_woss_separation
            validate_woss_separation(self.positions.values())

    def set_power(self, node: str, power_db: float):
        low,high,unit={'acoustic':(0,200,'dB acoustic SPL'),'optical':(1e-15,10000,'W'),'em':(-100,100,'dBm')}[self.medium]
        if not math.isfinite(power_db) or not low <= power_db <= high:
            raise ValueError(f"Transmit power must be within {low}..{high} {unit}")
        self._command(f"POWER {self.nodes[node]} {power_db:.12g}")

    def set_interface(self, node: str, interface: str):
        if self.multi_policy!='manual' or interface not in self.multi_interfaces.get(node,{}):
            raise ValueError('Manual multiPHY selection requires a configured interface on that node')
        self._command(f"INTERFACE {self.nodes[node]} {self.multi_interfaces[node][interface]}")

    def advance(self, target: float):
        self._validate_environment_geometry()
        if not math.isfinite(target) or target <= self.time:
            raise ValueError("Network time must increase")
        self._command(f"STEP {target:.12g}")
        events = self._until_barrier()
        if abs(self.time - target) > 1e-6:
            raise BackendError("DESERT returned the wrong barrier")
        return events

    def request_stats(self):
        self._command("STATS")

    def stop(self):
        if self.socket:
            try:
                self._command("STOP")
                self.socket.shutdown(socket.SHUT_RDWR)
            except (OSError, BackendError):
                pass
            if self.reader:
                self.reader.close()
            self.socket.close()
        self.reader = self.socket = None
        self.time = 0.0
        if self._owns_service:
            try:
                docker_command(*COMPOSE, "down", timeout=30)
            finally:
                self._owns_service = False
