"""Pose helpers (no ROS imports beyond geometry_msgs)."""
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
    """Tool +Z pointing straight down (world -Z), rotated `yaw` about world Z."""
    qz = (0.0, 0.0, math.sin(yaw / 2), math.cos(yaw / 2))
    qx = (1.0, 0.0, 0.0, 0.0)   # 180 deg about X
    return quat_multiply(qz, qx)


def tool_pose_for_tcp(x: float, y: float, z: float, yaw: float, tcp_offset: float) -> Pose:
    """tool0 pose that puts the TCP (tcp_offset along tool +Z) at (x, y, z), pointing down."""
    p = Pose()
    p.position.x, p.position.y, p.position.z = x, y, z + tcp_offset
    q = top_down_quat(yaw)
    p.orientation.x, p.orientation.y, p.orientation.z, p.orientation.w = q
    return p
