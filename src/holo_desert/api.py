"""Public Python API: DESERT networking with or without HoloOcean, no dashboard.

Three usage modes share one synchronisation implementation:

* :class:`NetworkSession` drives DESERT alone. The caller supplies node poses
  and advances simulated time (standalone network mode). It is also the core of
  the HoloOcean attachment.
* :class:`HoloOceanLink` attaches a :class:`NetworkSession` to a HoloOcean
  environment created and controlled by the caller. The link only reads each
  vehicle's own pose sensor after the caller's ``env.tick()``.
* :class:`ManagedSimulation` starts HoloOcean (or fixed network fixtures) and
  DESERT, runs a scenario with its traffic and returns results; it is the same
  orchestrator used by the dashboard.

All network decisions (PHY, MAC, routing, propagation) are taken by DESERT.
Python never computes link quality or chooses routes. See docs/api.md for the
clock model, operation order and lifecycle.
"""
from __future__ import annotations

import importlib.metadata
import json
import math
from pathlib import Path
from typing import Callable, Mapping

from .common.models import Delivery, Message, Pose
from .communications.manager import CommunicationManager
from .desert_adapter.backend import BackendError, DESERTAdapter
from .scenarios.config import Flow, Node as NodeConfig, Scenario, ScenarioManager
from .scenarios.library import ScenarioConflict, ScenarioLibrary
from .scenarios.network import CommunicationProfile, Network
from .scenarios.profiles import ProfileLibrary, builtin_profiles
from .synchronization.clock import ClockSynchronizer
from .telemetry.collector import TelemetryCollector

__all__ = ["NetworkSession", "NetworkNode", "HoloOceanLink", "ManagedSimulation", "SessionError", "CallbackError",
           "Scenario", "NodeConfig", "Network", "Flow", "Pose", "Message", "Delivery",
           "load_scenario", "list_examples", "pose_from_sensors", "network_catalog", "network_inventory",
           "ScenarioManager", "ScenarioLibrary", "ScenarioConflict", "ProfileLibrary", "CommunicationProfile",
           "builtin_profiles"]


class SessionError(RuntimeError):
    """A session operation failed; the session must be restarted or closed."""


class CallbackError(RuntimeError):
    """A receive callback raised. The tick completed; the session keeps running."""


def load_scenario(name_or_path: str | Path) -> Scenario:
    """Load a bundled example (``"e01_chat"``), a saved user scenario or a YAML path."""
    return ScenarioManager().load(str(name_or_path))


def list_examples() -> list[str]:
    return ScenarioManager().list()


def network_catalog() -> dict:
    """Catalogue of DESERT modules: verification status, parameters, units, defaults and limits.

    The same document is copied into the engine image and validates every
    configuration there; unknown parameters can never reach generated Tcl.
    """
    from .resources.docker.stack_builder import catalog
    return catalog()


def network_inventory() -> dict:
    """Audit of what the pinned DESERT image installs (libraries, Tcl classes, samples)."""
    path = Path(__file__).parent / "resources/docker/desert-inventory.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _as_pose(value) -> Pose:
    if isinstance(value, Pose):
        return value
    values = [float(v) for v in value]
    if len(values) not in (3, 4, 6):
        raise ValueError("Pose needs (x, y, z), (x, y, z, yaw) or (x, y, z, yaw, pitch, roll)")
    return Pose(*values)


def pose_from_sensors(sensors: Mapping) -> Pose:
    """Pose of one HoloOcean agent from its own sensors (metres, degrees).

    Supported: ``DynamicsSensor`` with ``UseRPY: true``, ``PoseSensor``, or
    ``LocationSensor`` with an optional ``RotationSensor``.
    """
    if "DynamicsSensor" in sensors:
        data = [float(v) for v in sensors["DynamicsSensor"]]
        if len(data) != 18:
            raise ValueError("DynamicsSensor must be configured with UseRPY: true (18 values)")
        return Pose(data[6], data[7], data[8], data[17], data[16], data[15])
    if "PoseSensor" in sensors:
        m = [[float(v) for v in row] for row in sensors["PoseSensor"]]
        yaw = math.degrees(math.atan2(m[1][0], m[0][0]))
        pitch = math.degrees(math.atan2(-m[2][0], math.hypot(m[2][1], m[2][2])))
        roll = math.degrees(math.atan2(m[2][1], m[2][2]))
        return Pose(m[0][3], m[1][3], m[2][3], yaw, pitch, roll)
    if "LocationSensor" in sensors:
        x, y, z = (float(v) for v in sensors["LocationSensor"])
        roll, pitch, yaw = (float(v) for v in sensors.get("RotationSensor", (0, 0, 0)))
        return Pose(x, y, z, yaw, pitch, roll)
    raise ValueError("Agent needs a DynamicsSensor (UseRPY), PoseSensor or LocationSensor")


class NetworkNode:
    """Communication handle of one node. It exposes no pose of other vehicles."""

    def __init__(self, session: NetworkSession, node_id: str):
        self._session = session
        self.id = node_id

    def send(self, destination: str, payload: bytes | dict | list, *, ttl: float = 20.0,
             message_type: str | None = None, priority: int = 0) -> str:
        """Queue a unicast message; it enters DESERT at the next ``step``. Returns its id."""
        if isinstance(payload, (bytes, bytearray)):
            data, kind = bytes(payload), message_type or "binary"
        else:
            data = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode()
            kind = message_type or "json"
        return self._session._communication.send(self.id, destination, data, message_type=kind,
                                                 ttl=ttl, priority=priority)

    def send_json(self, destination: str, payload, **options) -> str:
        if isinstance(payload, (bytes, bytearray)):
            raise TypeError("send_json expects a JSON-serialisable object; use send() for bytes")
        return self.send(destination, payload, **options)

    def receive(self) -> list[Delivery]:
        """Deliveries received since the last call (empty when callbacks are registered)."""
        return self._session._communication.receive(self.id)

    def on_receive(self, callback: Callable[[Delivery], None]):
        """Call ``callback(delivery)`` during ``step`` for each delivery; usable as decorator."""
        self._session._listeners.setdefault(self.id, []).append(callback)
        return callback

    def remove_callback(self, callback):
        self._session._listeners.get(self.id, []).remove(callback)

    def update_pose(self, pose) -> None:
        self._session.update_pose(self.id, pose)

    @property
    def pose(self) -> Pose:
        """This node's own pose as last supplied to the network."""
        return self._session._poses[self.id]

    def set_tx_power(self, value: float, interface: str | None = None) -> None:
        """Transmit power in the medium's native unit (dB re uPa SPL, W optical, dBm EM).

        With multi-PHY, ``interface`` names the interface to change (default: the node's
        first one) and the unit is that interface's medium.
        """
        self._session._command(lambda backend: backend.set_power(self.id, value, interface))

    def select_interface(self, interface: str) -> None:
        """Choose the active interface; requires a multi-PHY stack with ``policy: manual``."""
        self._session._command(lambda backend: backend.set_interface(self.id, interface))


class NetworkSession:
    """A DESERT run whose time and node poses are driven from Python.

    Life cycle: ``created`` -> ``start()`` -> ``running`` -> ``close()`` ->
    ``closed``. Any engine/transport failure moves the session to ``failed``;
    ``restart()`` then starts a new DESERT run from t=0 with the same scenario.

    Time advances only in ``step``/``run_until`` by whole ticks of
    ``1/scenario.physics_hz`` seconds. At each step the session, in order:
    applies all current node poses at the barrier time ``t``, injects messages
    queued since the previous step (creation time ``t``), advances DESERT to
    ``t + dt`` and delivers every reception with network time ``<= t + dt``.
    """

    def __init__(self, scenario: Scenario | str | Path, *, host: str = "127.0.0.1", port: int | None = None,
                 manage_engine: bool = True, persist: str | Path | None = None, timeout: float = 30,
                 backend=None, mode: str = "network_session"):
        self.scenario = scenario if isinstance(scenario, Scenario) else load_scenario(scenario)
        self._backend_factory = (lambda: backend) if backend is not None else (
            lambda: DESERTAdapter(host=host, port=port, manage_docker=manage_engine, timeout=timeout))
        self._persist = Path(persist) if persist else None
        self._mode = mode
        self._listeners: dict[str, list] = {}
        self._poses = {n.id: Pose(*n.position, n.yaw) for n in self.scenario.nodes}
        self._inverse = {v: k for k, v in self.scenario.node_map.items()}
        self.state = "created"
        self.error: str | None = None
        self._backend = self._telemetry = self._communication = self._clock = None
        self._last_fleet = -1.0
        self._runs = 0

    # -- life cycle -------------------------------------------------------
    def start(self) -> NetworkSession:
        if self.state not in ("created", "closed", "failed"):
            raise SessionError(f"Cannot start a session in state {self.state}")
        self._release(results=True)
        persist = None
        if self._persist:
            # Never overwrite an earlier run, also one from another session object.
            existing = [int(p.name[4:]) for p in self._persist.glob("run-[0-9][0-9][0-9]")]
            persist = self._persist / f"run-{max(existing, default=0) + 1:03d}"
        self._backend = self._backend_factory()
        self._telemetry = TelemetryCollector(self.scenario.model_dump(), persist)
        self._clock = ClockSynchronizer(self.scenario.physics_hz, realtime=False)
        self._communication = CommunicationManager(self._backend, self._clock, self._telemetry,
                                                   self.scenario.node_map, listeners=self._listeners,
                                                   max_message_bytes=self.scenario.network.max_wire_bytes)
        self._last_fleet = -1.0
        try:
            self._backend.start(self.scenario)
            for event in getattr(self._backend, "initial_events", []):
                self._telemetry.engine_event(event, self._inverse)
        except Exception as exc:
            self._fail(exc, release=True)
        self._telemetry.emit("run_started", 0, mode=self._mode, seed=self.scenario.network.seed,
                             rng_substream=self.scenario.network.seed, scenario_name=self.scenario.name,
                             node_map=self.scenario.node_map,
                             versions={"platform": _version(), "desert": "4.0.0", "engine": self._backend.versions})
        self.state = "running"
        return self

    def restart(self) -> NetworkSession:
        """Start a fresh DESERT run (t=0) after a failure or a deliberate reset."""
        self.close()
        self._poses = {n.id: Pose(*n.position, n.yaw) for n in self.scenario.nodes}
        return self.start()

    def close(self) -> None:
        """Stop DESERT and release the event log (persisted runs keep their files)."""
        if self.state == "running":
            self._telemetry.emit("run_ended", self._clock.time, state="closed")
        self._release()
        self.state = "closed"

    stop = close

    def __enter__(self):
        return self.start() if self.state != "running" else self

    def __exit__(self, *exc):
        self.close()

    # -- configuration and state -----------------------------------------
    @property
    def time(self) -> float:
        """Synchronised simulated time in seconds (HoloOcean and DESERT agree)."""
        return self._clock.time if self._clock else 0.0

    @property
    def dt(self) -> float:
        return 1 / self.scenario.physics_hz

    @property
    def node_ids(self) -> list[str]:
        return [n.id for n in self.scenario.nodes]

    @property
    def engine_info(self) -> dict:
        """Engine identity and the effective configuration reported by DESERT."""
        return dict(self._backend.versions) if self._backend else {}

    @property
    def applied_configuration(self) -> dict:
        """Values read back from the native DESERT objects at t=0, per node ("shared": channel)."""
        return json.loads(json.dumps(self._telemetry.applied_configuration)) if self._telemetry else {}

    def node(self, node_id: str) -> NetworkNode:
        if node_id not in self._poses:
            raise ValueError(f"Unknown node {node_id!r}; configured: {', '.join(self._poses)}")
        return NetworkNode(self, node_id)

    def update_pose(self, node_id: str, pose) -> None:
        """Pose measured at the current time; applied to DESERT at the next step."""
        if node_id not in self._poses:
            raise ValueError(f"Unknown node {node_id!r}")
        self._poses[node_id] = _as_pose(pose)

    def update_poses(self, poses: Mapping[str, object]) -> None:
        for node_id, pose in poses.items():
            self.update_pose(node_id, pose)

    def send(self, source: str, destination: str, payload, **options) -> str:
        return self.node(source).send(destination, payload, **options)

    # -- time -------------------------------------------------------------
    def step(self, ticks: int = 1) -> list[dict]:
        """Advance ``ticks`` physics ticks; returns the raw DESERT events observed."""
        if not isinstance(ticks, int) or ticks < 1:
            raise ValueError("ticks must be a positive integer")
        backend = self._require_running()
        observed = []
        for _ in range(ticks):
            # Geometry errors are the caller's: reject them before any command is sent.
            getattr(backend, "validate_positions", lambda poses: None)(self._poses)
            try:
                observed.extend(self._tick(backend))
            except SessionError:
                raise
            except Exception as exc:
                # Commands may already be in DESERT: the barrier state is unknown.
                self._fail(exc)
            errors, self._communication.callback_errors = self._communication.callback_errors, []
            if errors:
                raise CallbackError(f"{len(errors)} receive callback(s) raised at t={self.time:g}") from errors[0]
        return observed

    def _tick(self, backend) -> list[dict]:
        now = self._clock.time
        for node_id, pose in self._poses.items():
            backend.update_node_position(node_id, pose, now)
        self._communication.flush()
        if self._clock.tick % self.scenario.physics_hz == 0:
            backend.request_stats()
        # The shared clock moves only once DESERT has reached the new barrier.
        events = backend.advance((self._clock.tick + 1) / self.scenario.physics_hz)
        self._clock.step()
        self._clock.verify(backend.time)
        applied = set()
        for event in events:
            self._telemetry.engine_event(event, self._inverse)
            if event["event"] == "position_applied":
                applied.add(event["node"])
            elif event["event"] == "rx":
                self._communication.ingest(event, self._inverse)
        if applied != set(self._inverse):
            raise BackendError("DESERT did not acknowledge every position update")
        self._communication.deliver_due()
        if self._clock.time - self._last_fleet >= 0.1:
            self._telemetry.positions(dict(self._poses), self._clock.time,
                                      origin="holoocean" if self._mode == "holoocean_attached" else "caller")
            self._last_fleet = self._clock.time
        self._telemetry.sample(self._clock.time)
        return events

    def run_until(self, time_s: float) -> list[dict]:
        """Step until simulated time reaches ``time_s`` (rounded up to a tick)."""
        ticks = math.ceil(round((time_s - self.time) * self.scenario.physics_hz, 9))
        return self.step(ticks) if ticks > 0 else []

    # -- results ----------------------------------------------------------
    def summary(self) -> dict:
        """Application-level counts, PDR, latency and DESERT protocol statistics."""
        return self._telemetry.summary() if self._telemetry else {}

    def snapshot(self) -> dict:
        """Full telemetry snapshot (packets, observations, fleet, series)."""
        return self._telemetry.snapshot() if self._telemetry else {}

    def packets(self) -> list[dict]:
        """Per-message records with status, network events and end-to-end delay."""
        return [dict(row) for row in self._telemetry.packets.values()] if self._telemetry else []

    def export(self, path: str | Path) -> Path:
        """Write config.json, events.jsonl, packets.csv and summary.json to a ZIP.

        Results stay available after close() or a failure, until the next start()."""
        if not self._telemetry:
            raise SessionError("Nothing to export before start()")
        return _export(self._telemetry, self.summary(), path)

    # -- internals --------------------------------------------------------
    def _command(self, action):
        backend = self._require_running()
        try:
            action(backend)
        except BackendError as exc:
            self._fail(exc)

    def _require_running(self):
        if self.state != "running":
            raise SessionError(f"Session is {self.state}; call start()" +
                               (f" (last error: {self.error})" if self.error else ""))
        return self._backend

    def _fail(self, exc, release=False):
        """Record the failure, stop DESERT and raise; results stay exportable unless released."""
        self.error = f"{type(exc).__name__}: {exc}"
        self.state = "failed"
        if self._telemetry:
            self._telemetry.emit("run_error", self.time, reason=self.error)
        try:
            self._backend.stop()
        except Exception:
            pass
        if release:
            self._release(results=True)
        raise SessionError(self.error) from exc

    def _release(self, results=False):
        """Stop DESERT and close the log; ``results`` also deletes a temporary run directory."""
        if self._backend is not None:
            self._backend.stop()
        if self._telemetry is not None:
            if results:
                if not self._telemetry.log.closed or self._telemetry._temp:
                    self._telemetry.close()
            elif not self._telemetry.log.closed:
                self._telemetry.log.close()


class HoloOceanLink:
    """Synchronise a NetworkSession with a HoloOcean environment you control.

    The application keeps creating, commanding and ticking its environment.
    After each ``state = env.tick()`` call ``link.sync(state)``: DESERT advances
    over the same physics tick using the poses applied at its start, then the
    new measured poses are stored for the next tick. Received messages are
    delivered before ``sync`` returns. No second HoloOcean is started.
    """

    def __init__(self, session: NetworkSession, agents: Mapping[str, str] | None = None, *,
                 ticks_per_sec: int | None = None, pose_reader: Callable[[Mapping], Pose] = pose_from_sensors):
        if ticks_per_sec is not None and ticks_per_sec != session.scenario.physics_hz:
            raise ValueError(f"Environment ticks_per_sec={ticks_per_sec} differs from "
                             f"scenario physics_hz={session.scenario.physics_hz}")
        self.session = session
        self.agents = dict(agents) if agents else {n: n for n in session.node_ids}
        unknown = set(self.agents.values()) - set(session.node_ids)
        if unknown:
            raise ValueError(f"Agents mapped to unknown network nodes: {sorted(unknown)}")
        self.pose_reader = pose_reader
        session._mode = "holoocean_attached"

    def read_poses(self, state: Mapping) -> dict[str, Pose]:
        poses = {}
        for agent, node in self.agents.items():
            sensors = state[agent] if agent in state else state if len(self.agents) == 1 else None
            if sensors is None:
                raise KeyError(f"HoloOcean state has no agent {agent!r}")
            poses[node] = self.pose_reader(sensors)
        return poses

    def attach(self, state: Mapping) -> None:
        """Set the t=0 poses from the state returned by ``env.reset()``.

        Pass the state of the same instant as the network clock: attaching an
        ``env.tick()`` result would leave HoloOcean one tick ahead of DESERT.
        """
        self.session.update_poses(self.read_poses(state))

    def sync(self, state: Mapping, ticks: int = 1) -> list[dict]:
        """Advance the network by the ``ticks`` physics ticks that produced ``state``."""
        poses = self.read_poses(state)  # validate before time moves
        events = self.session.step(ticks)
        self.session.update_poses(poses)
        return events


class ManagedSimulation:
    """Run a complete scenario: HoloOcean (or fixed fixtures) + DESERT + traffic.

    This is the orchestrator used by the dashboard. ``holoocean=False`` uses the
    configured fixed node positions and is suitable only for static scenarios.
    """

    def __init__(self, scenario: Scenario | str | Path, *, holoocean: bool = True, show_viewport: bool = False,
                 realtime: bool | None = None, manage_engine: bool = True, port: int | None = None,
                 persist: str | Path | None = None, application_factory=None):
        from .core.orchestrator import SimulationOrchestrator
        scenario = scenario if isinstance(scenario, Scenario) else load_scenario(scenario)
        if realtime is not None:
            scenario = Scenario.model_validate({**scenario.model_dump(), "realtime": realtime})
        self.scenario = scenario
        self.holoocean = holoocean
        self._run = SimulationOrchestrator(scenario, standalone=not holoocean, persist=persist,
                                           backend=DESERTAdapter(port=port, manage_docker=manage_engine),
                                           show_viewport=show_viewport, application_factory=application_factory)

    @property
    def run_id(self) -> str:
        return self._run.run_id

    @property
    def state(self) -> str:
        return self._run.state

    @property
    def error(self) -> str | None:
        return self._run.error

    @property
    def versions(self) -> dict:
        """Platform, HoloOcean and engine identity recorded when the run started."""
        return json.loads(json.dumps(self._run.telemetry.versions, default=str))

    @property
    def applied_configuration(self) -> dict:
        """Values read back from the native DESERT objects at t=0, per node ("shared": channel)."""
        return json.loads(json.dumps(self._run.telemetry.applied_configuration))

    def annotate(self, event: str, **fields) -> None:
        """Add a caller-defined event to this run's log; it is exported with the results."""
        self._run.telemetry.emit(event, self._run.clock.time, **fields)

    def trajectory_fingerprint(self) -> dict:
        """SHA-256 per vehicle of the observed fleet telemetry, to compare trajectories of runs."""
        return self._run.telemetry.trajectory()

    def run(self) -> dict:
        """Run to completion in this thread; returns the summary or raises SessionError."""
        self._run.run()
        if self._run.error:
            raise SessionError(self._run.error)
        return self.summary()

    def start_background(self) -> None:
        self._run.start_background()

    def wait(self, timeout: float | None = None) -> str:
        if self._run.thread:
            self._run.thread.join(timeout)
        return self._run.state

    def stop(self) -> None:
        self._run.stop()

    def pause(self) -> None:
        self._run.pause()

    def resume(self) -> None:
        self._run.resume()

    def summary(self) -> dict:
        return self._run.telemetry.summary()

    def snapshot(self) -> dict:
        return self._run.snapshot()

    def export(self, path: str | Path) -> Path:
        return _export(self._run.telemetry, self.summary(), path)

    def export_bytes(self) -> bytes:
        """The export ZIP of :meth:`export` as bytes."""
        return _export_bytes(self._run.telemetry, self.summary())

    def close(self) -> None:
        """Stop the run and release its temporary results; calling it again is harmless."""
        self._run.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def _export_bytes(telemetry, summary):
    import io
    import zipfile
    buffer = io.BytesIO(telemetry.export())
    with zipfile.ZipFile(buffer, "a", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("summary.json", json.dumps(summary, indent=2, default=str))
    return buffer.getvalue()


def _export(telemetry, summary, path):
    path = Path(path)
    path.write_bytes(_export_bytes(telemetry, summary))
    return path


def _version():
    try:
        return importlib.metadata.version("holoocean-desert")
    except importlib.metadata.PackageNotFoundError:
        return None
