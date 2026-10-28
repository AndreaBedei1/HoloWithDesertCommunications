"""HoloOcean-DESERT: real simulator adapters, no substitute acoustic model.

Public API (see docs/api.md)::

    from holo_desert import NetworkSession, HoloOceanLink, ManagedSimulation, load_scenario
"""

__version__ = "1.1.0"

from .api import (CallbackError, CommunicationProfile, Delivery, Flow, HoloOceanLink, ManagedSimulation,  # noqa: E402
                  Message, Network, NetworkNode, NetworkSession, NodeConfig, Pose, ProfileLibrary, Scenario,
                  ScenarioConflict, ScenarioLibrary, ScenarioManager, SessionError, builtin_profiles, list_examples,
                  load_scenario, network_catalog, network_inventory, pose_from_sensors)

__all__ = ["CallbackError", "NetworkSession", "NetworkNode", "HoloOceanLink", "ManagedSimulation", "SessionError", "Scenario",
           "NodeConfig", "Network", "Flow", "Pose", "Message", "Delivery", "load_scenario", "list_examples",
           "pose_from_sensors", "network_catalog", "network_inventory", "ScenarioManager", "ScenarioLibrary",
           "ScenarioConflict", "ProfileLibrary", "CommunicationProfile", "builtin_profiles", "__version__"]
