"""Pose helpers for the HELENE gripper (no ROS imports beyond geometry_msgs).

The tool frame is `tcp`: the point between the finger pads. Its +X axis is the
approach direction (out of the gripper) and its +Y axis is the jaw (finger
travel) axis.
"""
import math
from typing import Tuple

from geometry_msgs.msg import Pose


def quat_multiply(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz)


def top_down_quat(yaw: float) -> Tuple[float, float, float, float]:
    """tcp +X (approach) pointing straight down; then rotated `yaw` about world Z.

    The jaw axis (tcp +Y) then lies horizontally at angle yaw + 90 deg.
    """
    qz = (0.0, 0.0, math.sin(yaw / 2), math.cos(yaw / 2))
    qy = (0.0, math.sin(math.pi / 4), 0.0, math.cos(math.pi / 4))   # +90 deg about Y: X -> -Z
    return quat_multiply(qz, qy)


def jaw_angle(yaw: float) -> float:
    return yaw + math.pi / 2


def tcp_pose(x: float, y: float, z: float, yaw: float) -> Pose:
    """tcp pose with the grasp centre at (x, y, z), gripper pointing down."""
    p = Pose()
    p.position.x, p.position.y, p.position.z = x, y, z
    q = top_down_quat(yaw)
    p.orientation.x, p.orientation.y, p.orientation.z, p.orientation.w = q
    return p
