"""Vehicle-specific HoloOcean schema, sensor decoding and controller action.

Future vehicles implement this contract and register a profile here; the
orchestrator and applications continue using metres, yaw and pose targets.
Only HoveringAUV is currently supported and validated.
"""
from ..common.models import Pose


class HoveringAUVProfile:
    def configuration(self, node):
        return {"agent_name": node.id, "agent_type": "HoveringAUV", "control_scheme": 1,
                "location": list(node.position), "rotation": [0, 0, node.yaw],
                "sensors": [{"sensor_type": "DynamicsSensor", "socket": "COM",
                             "configuration": {"UseCOM": True, "UseRPY": True}}]}

    def pose(self, sensors):
        data = sensors["DynamicsSensor"]
        return Pose(float(data[6]), float(data[7]), float(data[8]), float(data[17]))

    def action(self, target):
        return list(target)


VEHICLE_PROFILES = {"HoveringAUV": HoveringAUVProfile()}
