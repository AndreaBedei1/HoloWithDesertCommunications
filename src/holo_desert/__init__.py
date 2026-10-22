"""HoloOcean-DESERT: real simulator adapters, no substitute acoustic model.

Public API (see docs/api.md)::

    from holo_desert import NetworkSession, HoloOceanLink, ManagedSimulation, load_scenario
"""

__version__ = "0.2.0"

from .api import (CallbackError, Delivery, Flow, HoloOceanLink, ManagedSimulation, Message, Network, NetworkNode,  # noqa: E402
                  NetworkSession, NodeConfig, Pose, Scenario, SessionError, list_examples, load_scenario,
                  pose_from_sensors)

__all__ = ["CallbackError", "NetworkSession", "NetworkNode", "HoloOceanLink", "ManagedSimulation", "SessionError", "Scenario",
           "NodeConfig", "Network", "Flow", "Pose", "Message", "Delivery", "load_scenario", "list_examples",
           "pose_from_sensors", "__version__"]
