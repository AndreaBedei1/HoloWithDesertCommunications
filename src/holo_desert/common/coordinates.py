from dataclasses import dataclass
from .models import Pose


@dataclass(frozen=True)
class CoordinateConverter:
    """HoloOcean sensors: metres, right-handed X forward/Y left/Z up.

    DESERT Cartesian underwater examples also use metres and negative Z below
    the surface. Identity is explicit; no Unreal centimetres enter this API.
    Optional origin translates all nodes together; never scales acoustic range.
    """
    origin: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def to_network(self, pose: Pose) -> Pose:
        return Pose(pose.x - self.origin[0], pose.y - self.origin[1],
                    pose.z - self.origin[2], pose.yaw)
