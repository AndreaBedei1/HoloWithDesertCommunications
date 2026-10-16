from __future__ import annotations

import math
from pathlib import Path
from typing import Literal
import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

RESOURCE_ROOT = Path(__file__).resolve().parents[1] / "resources"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Acoustic(Strict):
    bitrate_bps: float = Field(default=4800, gt=0)
    tx_power_db: float = Field(default=135, ge=0, le=200)
    frequency_hz: float = Field(default=25000, gt=0)
    bandwidth_hz: float = Field(default=5000, gt=0)
    propagation: Literal["underwater"] = "underwater"
    interference: Literal["miv"] = "miv"

    @model_validator(mode="after")
    def check_band(self):
        if self.bandwidth_hz >= 2 * self.frequency_hz:
            raise ValueError("Acoustic band must stay above zero Hz")
        return self


class Mac(Strict):
    protocol: Literal["csma_aloha", "aloha"] = "csma_aloha"
    ack: bool = False
    max_tx_tries: int = Field(default=3, ge=1, le=20)
    buffer_packets: int = Field(default=100, ge=1, le=10000)


class Network(Strict):
    backend: Literal["desert"] = "desert"
    acoustic: Acoustic = Field(default_factory=Acoustic)
    mac: Mac = Field(default_factory=Mac)
    routing: Literal["static"] = "static"
    max_wire_bytes: int = Field(default=4096, ge=256, le=4096)
    seed: int = Field(default=1, ge=1, le=100000)
    routes: dict[str, dict[str, str]] = Field(default_factory=dict)


class Node(Strict):
    id: str = Field(pattern=r"^auv_[0-9]{2}$")
    position: tuple[float, float, float]
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
    interval: float = Field(default=3, gt=0)
    final_interval: float | None = Field(default=None, gt=0)
    payload_bytes: int = Field(default=32, ge=1, le=2048)
    ttl: float = Field(default=20, gt=0)
    reply: bool = False
    message_type: str = "data"


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
        return self

    @property
    def node_map(self):
        return {node.id: i + 1 for i, node in enumerate(self.nodes)}


class ScenarioManager:
    def __init__(self, root: Path | None = None):
        self.root = root or RESOURCE_ROOT / "examples"

    def list(self):
        return sorted(p.parent.name for p in self.root.glob("*/scenario.yaml"))

    def load(self, name_or_path: str) -> Scenario:
        path = Path(name_or_path)
        if not path.is_file():
            if name_or_path not in self.list():
                raise ValueError(f"Unknown scenario {name_or_path!r}; choose {', '.join(self.list())}")
            path = self.root / name_or_path / "scenario.yaml"
        return Scenario.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


NetworkConfigurator = Network
