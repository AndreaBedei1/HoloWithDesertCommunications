from __future__ import annotations

import math
from pathlib import Path
from typing import Literal
import yaml
from .network import Acoustic, Mac, Network, NodeCommunication
from pydantic import BaseModel, ConfigDict, Field, model_validator

RESOURCE_ROOT = Path(__file__).resolve().parents[1] / "resources"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Node(Strict):
    id: str = Field(pattern=r"^auv_[0-9]{2}$")
    position: tuple[float, float, float]
    communication: NodeCommunication | None = None
    yaw: float = 0
    vehicle: Literal["HoveringAUV"] = "HoveringAUV"
    # Waypoints are commands to HoloOcean's built-in pose controller, not a physics model.
    waypoints: list[tuple[float, float, float, float]] = Field(default_factory=list)

    @model_validator(mode="after")
    def ordered(self):
        times = [w[0] for w in self.waypoints]
        if times != sorted(set(times)) or any(t < 0 for t in times):
            raise ValueError("Waypoint times must be unique, increasing and nonnegative")
        return self


class Flow(Strict):
    source: str
    destination: str
    start: float = Field(default=1, ge=0)
    stop: float | None = Field(default=None, gt=0)
    pattern: Literal['periodic','poisson','burst','events'] = 'periodic'
    generator: Literal['python','desert_cbr','desert_vbr'] = 'python'
    native_packet_bytes: int = Field(default=125,ge=16,le=2048)
    native_period2_s: float = Field(default=2,gt=0)
    native_duration1_s: float = Field(default=5,gt=0)
    native_duration2_s: float = Field(default=5,gt=0)
    interface: str = Field(default='inherit',pattern=r'^[a-z][a-z0-9_]{0,31}$')
    burst_count: int = Field(default=3,ge=1,le=100)
    burst_interval_s: float = Field(default=.25,gt=0)
    burst_period_s: float = Field(default=5,gt=0)
    events: list[float] = Field(default_factory=list)
    interval: float = Field(default=3, gt=0)
    final_interval: float | None = Field(default=None, gt=0)
    payload_bytes: int = Field(default=32, ge=1, le=2048)
    ttl: float = Field(default=20, gt=0)
    reply: bool = False
    message_type: str = "data"

    @model_validator(mode='after')
    def variable_interval_window(self):
        if self.final_interval is not None and self.stop is None:
            raise ValueError('Variable interval requires flow stop')
        if self.generator!='python' and (self.reply or self.message_type!='data' or self.pattern not in ('periodic','poisson') or self.final_interval is not None):
            raise ValueError('Native generators support data without Python replies, periodic/Poisson timing and native VBR switching')
        return self


class PowerEvent(Strict):
    time: float = Field(ge=0)
    node: str
    tx_power_db: float = Field(ge=0, le=200)


class Scenario(Strict):
    name: str
    description: str
    duration: float = Field(default=30, gt=0)
    physics_hz: int = Field(default=30, ge=1, le=240)
    realtime: bool = True
    world: str = "OpenWater"
    nodes: list[Node] = Field(min_length=2, max_length=32)
    network: Network = Field(default_factory=Network)
    flows: list[Flow] = Field(default_factory=list)
    power_events: list[PowerEvent] = Field(default_factory=list)
    coordination: bool = False

    @model_validator(mode="after")
    def valid_references(self):
        ids = {n.id for n in self.nodes}
        if len(ids) != len(self.nodes):
            raise ValueError("Duplicate node identifiers")
        for f in self.flows:
            if f.source not in ids or f.destination not in ids or f.source == f.destination:
                raise ValueError("Flows require distinct configured source/destination nodes")
            if f.stop is not None and f.stop <= f.start:
                raise ValueError("Flow stop must follow start")
        for src, routes in self.network.routes.items():
            if src not in ids or any(dst not in ids or hop not in ids for dst, hop in routes.items()):
                raise ValueError("Unknown node in static route")
            if src in routes or src in routes.values():
                raise ValueError("Static routes cannot route to or through their own source")
        if self.network.routing != 'static' and self.network.routes:
            raise ValueError('Static routes cannot be used with Flooding')
        # Unspecified entries are direct routes, exactly as rendered by the backend.
        for src in ids:
            for dst in ids - {src}:
                seen, current = set(), src
                while current != dst:
                    if current in seen:
                        raise ValueError(f"Static routing loop from {src} to {dst}")
                    seen.add(current)
                    current = self.network.routes.get(current, {}).get(dst, dst)
        if any(e.node not in ids for e in self.power_events):
            raise ValueError("Unknown node in power event")
        if self.coordination and len(self.nodes) != 2:
            raise ValueError("Coordination demo requires two nodes")
        if self.coordination and self.flows:
            raise ValueError("Coordination uses heartbeat traffic; additional flows are unsupported")
        from ..resources.docker.stack_builder import validate
        validate(self.model_dump())
        return self

    @property
    def node_map(self):
        return {node.id: i + 1 for i, node in enumerate(self.nodes)}


class ScenarioManager:
    def __init__(self, root: Path | None = None, user_root: Path | None = None):
        self.root = root or RESOURCE_ROOT / "examples"
        from .library import ScenarioLibrary
        self.library = ScenarioLibrary(user_root, self.list())

    def list_user(self):
        return self.library.list()

    def get_user(self, identifier):
        return self.library.get(identifier)

    def save_user(self, configuration, identifier=None, expected_revision=None):
        return self.library.save(configuration, identifier, expected_revision)

    def delete_user(self, identifier, expected_revision):
        return self.library.delete(identifier, expected_revision)

    def list(self):
        return sorted(p.parent.name for p in self.root.glob("*/scenario.yaml"))

    def load(self, name_or_path: str) -> Scenario:
        if name_or_path.startswith("user_") and self.library.ID.fullmatch(name_or_path):
            return Scenario.model_validate(self.get_user(name_or_path)["configuration"])
        path = Path(name_or_path)
        if not path.is_file():
            if name_or_path not in self.list():
                raise ValueError(f"Unknown scenario {name_or_path!r}; choose {', '.join(self.list())}")
            path = self.root / name_or_path / "scenario.yaml"
        return Scenario.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


NetworkConfigurator = Network
