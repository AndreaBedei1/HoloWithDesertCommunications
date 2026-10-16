from __future__ import annotations

import importlib.metadata
import os
import subprocess
from ..common.models import Pose
from .vehicles import VEHICLE_PROFILES


def _kernel_exit_code(process):
    """Windows can publish termination before its process handle is signalled.

    Query only our Popen handle. A STILL_ACTIVE result never counts as stopped.
    """
    if os.name != "nt" or not hasattr(process, "_handle"):
        return None
    import _winapi
    try:
        code = _winapi.GetExitCodeProcess(process._handle)
        return None if code == _winapi.STILL_ACTIVE else code
    except OSError:
        return None


class HoloOceanAdapter:
    """Only HoloOcean owns vehicle state and dynamics. Uses its built-in PD controller."""
    def __init__(self, scenario, show_viewport=True):
        self.scenario = scenario
        self.show_viewport = show_viewport
        self.env = None
        self.poses = {}
        self.profiles = {n.id: VEHICLE_PROFILES[n.vehicle] for n in scenario.nodes}

    def start(self):
        import holoocean
        if holoocean.__version__ != "2.3.0":
            raise RuntimeError(f"HoloOcean 2.3.0 required; found {holoocean.__version__}")
        if "Ocean" not in holoocean.packagemanager.installed_packages():
            raise RuntimeError("HoloOcean Ocean package is missing. Install Ocean for HoloOcean 2.3.0.")
        cfg = {"name": self.scenario.name, "package_name": "Ocean", "world": self.scenario.world,
               "main_agent": self.scenario.nodes[0].id,
               "ticks_per_sec": self.scenario.physics_hz, "frames_per_sec": False,
               "window_width": 960, "window_height": 640,
               "agents": [self.profiles[n.id].configuration(n) for n in self.scenario.nodes]}
        self.env = holoocean.make(scenario_cfg=cfg, show_viewport=self.show_viewport,
                                  frames_per_sec=False, ticks_per_sec=self.scenario.physics_hz)
        self.env.should_render_viewport(self.show_viewport)
        for node in self.scenario.nodes:
            self.command(node.id, (*node.position, 0, 0, node.yaw))
        # Sensor values, not the spawn configuration, are the initial ground truth.
        state = self.env.tick(tick_clock=False, publish=False)
        self._read(state)
        return self.poses

    def _read(self, state):
        for node in self.scenario.nodes:
            sensors = state[node.id] if node.id in state else state
            self.poses[node.id] = self.profiles[node.id].pose(sensors)

    def command(self, node, action):
        self.env.act(node, self.profiles[node].action(action))

    def tick(self):
        self._read(self.env.tick(publish=False))
        return dict(self.poses)

    def stop(self):
        if self.env is not None:
            try:
                self.env.__exit__(None, None, None)
            except subprocess.TimeoutExpired:
                # The upstream Windows teardown allows only 10 seconds for
                # Unreal/driver shutdown. Reap only our owned Popen, then let
                # the official cleanup finish; do not kill by process name.
                process = getattr(self.env, "_world_process", None)
                if process is None:
                    raise
                code = _kernel_exit_code(process)
                if code is None:
                    try:
                        process.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        code = _kernel_exit_code(process)
                        if code is None:
                            raise
                if code is not None:
                    process.returncode = code
                self.env.__exit__(None, None, None)
            self.env = None


class StaticNetworkFixture:
    """DESERT standalone fixture: fixed configured positions, no vehicle physics.

    Explicitly forbidden for integrated/E2E claims; does not support movement.
    """
    def __init__(self, scenario):
        self.scenario = scenario
        self.poses = {n.id: Pose(*n.position, n.yaw) for n in scenario.nodes}

    def start(self):
        if any(n.waypoints for n in self.scenario.nodes) or self.scenario.coordination:
            raise ValueError("This scenario needs HoloOcean; standalone supports fixed network fixtures only")
        return self.poses

    def tick(self):
        return self.poses

    def command(self, node, action):
        raise RuntimeError("No vehicle control in DESERT standalone mode")

    def stop(self):
        pass
