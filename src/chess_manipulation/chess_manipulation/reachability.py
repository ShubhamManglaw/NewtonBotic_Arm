"""Reachability study: can the arm reach each board square top-down?

  ros2 run chess_manipulation reachability --ros-args -p tcp_offset:=0.11
  ros2 run chess_manipulation reachability --ros-args -p mode:=grid

Requires move_group running. Uses MoveIt IK (/compute_ik) with collision checking.
"""
import math

import rclpy
from rclpy.node import Node

from chess_manipulation.geometry import tool_pose_for_tcp
from chess_manipulation.moveit_client import MoveItClient, spin_in_background
from chess_simulation.board import BoardGeometry, square_name


def yaw_candidates(x, y):
    radial = math.atan2(y, x)
    return [radial + k * math.pi / 2 for k in range(4)]


def reachable(mc, x, y, z, tcp, clearance):
    for yaw in yaw_candidates(x, y):
        q = mc.compute_ik(tool_pose_for_tcp(x, y, z, yaw, tcp), attempts=2)
        if q is None:
            continue
        q2 = mc.compute_ik(tool_pose_for_tcp(x, y, z + clearance, yaw, tcp), seed=q)
        if q2 is not None:
            return True
    return False


def main():
    rclpy.init()
    node = Node('reachability')
    tcp = node.declare_parameter('tcp_offset', 0.11).value
    mode = node.declare_parameter('mode', 'board').value
    clearance = node.declare_parameter('clearance', 0.07).value
    spin_in_background(node)
    mc = MoveItClient(node)
    if not mc.wait_ready():
        node.get_logger().error('move_group not available')
        return
    geo = BoardGeometry()
    if mode == 'grid':
        z = geo.top_z + geo.grasp_height
        print(f'tcp_offset={tcp} z={z:.3f}  rows: y, cols: x (#=reachable)')
        xs = [round(-0.24 + 0.02 * i, 3) for i in range(25)]
        print('      ' + ''.join('|' if abs(x) < 1e-6 else ' ' for x in xs))
        for y in [round(0.44 - 0.02 * i, 3) for i in range(24)]:
            row = ''.join('#' if reachable(mc, x, y, z, tcp, clearance) else '.' for x in xs)
            print(f'{y:5.2f} {row}')
    else:
        bad = []
        for r in range(7, -1, -1):
            row = ''
            for f in range(8):
                sq = square_name(f, r)
                x, y, z = geo.square_world(sq, geo.grasp_height)
                ok = reachable(mc, x, y, z, tcp, clearance)
                row += ' ok ' if ok else ' XX '
                if not ok:
                    bad.append(sq)
            print(f'{r + 1} {row}')
        print('   ' + ''.join(f'  {c} ' for c in 'abcdefgh'))
        for color in ('white', 'black'):
            for i in range(16):
                x, y, z = geo.graveyard_world(color, i)
                if not reachable(mc, x, y, z + geo.grasp_height, tcp, clearance):
                    bad.append(f'{color}_graveyard_{i}')
        print('UNREACHABLE:', bad if bad else 'none')
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
