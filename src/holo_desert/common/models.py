from __future__ import annotations

import base64
import json
import math
import uuid
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class Pose:
    x: float
    y: float
    z: float
    yaw: float = 0.0

    def __post_init__(self):
        if not all(math.isfinite(v) for v in asdict(self).values()):
            raise ValueError("Pose coordinates must be finite")


@dataclass(frozen=True)
class Message:
    source: str
    destination: str
    payload: bytes
    creation_time: float
    id: str = ""
    message_type: str = "binary"
    priority: int = 0
    ttl: float = 20.0
    version: int = 1

    def __post_init__(self):
        if not self.id:
            object.__setattr__(self, "id", uuid.uuid4().hex)
        if self.version != 1 or self.creation_time < 0 or not math.isfinite(self.creation_time):
            raise ValueError("Invalid message version or creation timestamp")
        if self.ttl <= 0 or not math.isfinite(self.ttl):
            raise ValueError("TTL must be positive and finite")
        if not isinstance(self.payload, bytes):
            raise TypeError("Payload must be bytes; use send_json for JSON")

    def encode(self) -> bytes:
        data = asdict(self)
        data["payload"] = base64.b64encode(self.payload).decode("ascii")
        return json.dumps(data, separators=(",", ":"), allow_nan=False).encode()

    @classmethod
    def decode(cls, wire: bytes) -> Message:
        data = json.loads(wire)
        data["payload"] = base64.b64decode(data["payload"], validate=True)
        return cls(**data)

    def json(self):
        return json.loads(self.payload)


@dataclass(frozen=True)
class Delivery:
    message: Message
    receiver: str
    network_time: float
    transport_observed_wall_time: float
    metadata: dict
