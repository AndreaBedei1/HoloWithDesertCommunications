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
BASE_IMAGE = "uwsignet/desert:4.0.0@sha256:59c734d2980de64e4b36429c3fb4a60aceb1cb7efc5f9d605f9b7781fbc51ca6"


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

    def start(self, scenario: Scenario):
        if self.socket:
            raise BackendError("Backend already started")
        self.nodes = scenario.node_map
        self.limit = scenario.network.max_wire_bytes
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
            from ..resources.docker.stack_builder import CATALOG_VERSION
            if self.versions.get('stack_builder') != CATALOG_VERSION:
                raise BackendError('DESERT engine image is outdated: rebuild with holo-desert engine up before using this laboratory version')
            if self.time != 0 or any(e["event"] == "rx" for e in initial):
                raise BackendError("DESERT did not initialize at time zero")
        except Exception:
            self.stop()
            raise

    def health(self):
        try:
            with socket.create_connection((self.host, self.port), 1) as s:
                s.sendall(b"HEALTH\n")
                return json.loads(s.recv(4096)).get("event") == "health"
        except (OSError, ValueError):
            return False

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

    def update_node_position(self, node: str, pose: Pose, timestamp: float):
        if not math.isfinite(timestamp) or abs(timestamp - self.time) > 1e-6:
            raise BackendError("Position timestamp must equal DESERT barrier time")
        self._command(f"POSITION {self.nodes[node]} {pose.x:.12g} {pose.y:.12g} {pose.z:.12g} {timestamp:.12g}")

    def set_power(self, node: str, power_db: float):
        if not math.isfinite(power_db) or not 0 <= power_db <= 200:
            raise ValueError("Transmit power must be within 0..200 dB")
        self._command(f"POWER {self.nodes[node]} {power_db:.12g}")

    def advance(self, target: float):
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
