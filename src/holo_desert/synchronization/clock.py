from __future__ import annotations

import time


class ClockSynchronizer:
    """One logical timeline; wall time only controls pacing and measures drift.

    Network events carry NS timestamps. Events are delivered to applications
    only once HoloOcean has reached or passed those timestamps.
    """
    def __init__(self, hz: int, realtime=True):
        self.hz = hz
        self.realtime = realtime
        self.tick = 0
        self.wall_origin = time.monotonic()
        self.paused_at = None
        self.paused_total = 0.0

    @property
    def time(self):
        return self.tick / self.hz

    def step(self):
        self.tick += 1
        return self.time

    def verify(self, network_time):
        if abs(network_time - self.time) > 1e-6:
            raise RuntimeError(f"Clock mismatch: HoloOcean={self.time}, DESERT={network_time}")

    def can_deliver(self, timestamp):
        if timestamp < 0:
            raise ValueError("Negative network timestamp")
        return timestamp <= self.time + 1e-9

    @property
    def drift(self):
        end = self.paused_at if self.paused_at is not None else time.monotonic()
        return end - self.wall_origin - self.paused_total - self.time

    def pace(self, stop_event):
        if self.realtime:
            remaining = -self.drift
            if remaining > 0:
                stop_event.wait(remaining)

    def pause(self):
        if self.paused_at is None:
            self.paused_at = time.monotonic()

    def resume(self):
        if self.paused_at is not None:
            self.paused_total += time.monotonic() - self.paused_at
            self.paused_at = None
