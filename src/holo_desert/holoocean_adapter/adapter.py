from __future__ import annotations

import importlib.metadata
from ..common.models import Pose


class HoloOceanAdapter:
    """Only HoloOcean owns vehicle state and dynamics. Uses its built-in PD controller."""
    def __init__(self, scenario, show_viewport=True):
        self.scenario = scenario
        self.show_viewport = show_viewport
        self.env = None
        self.poses = {}

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
               "agents": [{"agent_name": n.id, "agent_type": "HoveringAUV", "control_scheme": 1,
                           "location": list(n.position), "rotation": [0, 0, n.yaw],
                           "sensors": [{"sensor_type": "DynamicsSensor", "socket": "COM", "configuration": {"UseCOM": True, "UseRPY": True}}]}
                          for n in self.scenario.nodes]}
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
            data = sensors["DynamicsSensor"]
            self.poses[node.id] = Pose(float(data[6]), float(data[7]), float(data[8]), float(data[17]))

    def command(self, node, action):
        self.env.act(node, list(action))

    def tick(self):
        self._read(self.env.tick(publish=False))
        return dict(self.poses)

    def stop(self):
        if self.env is not None:
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
