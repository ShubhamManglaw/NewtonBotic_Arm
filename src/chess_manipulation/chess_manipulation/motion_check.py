"""MoveIt integration smoke test (Phase 4 gate).

Plans + executes (via move_group -> arm_controller -> Gazebo) to top-down poses
above several board squares, then checks the achieved tcp pose with TF.

  ros2 run chess_manipulation motion_check
"""
import math
import time

import rclpy
from rclpy.node import Node
from tf2_ros import Buffer, TransformListener

from chess_manipulation.geometry import tcp_pose
from chess_manipulation.moveit_client import MoveItClient, spin_in_background
from chess_simulation.board import BoardGeometry

SQUARES = ['e4', 'a1', 'h1', 'a8', 'h8', 'd5']


def main():
    rclpy.init()
    node = Node('motion_check', parameter_overrides=[])
    height = node.declare_parameter('height', 0.08).value
    spin_in_background(node)
    buf = Buffer()
    TransformListener(buf, node)
    mc = MoveItClient(node)
    if not mc.wait_ready():
        node.get_logger().error('move_group not ready')
        return 1
    geo = BoardGeometry()
    failures = 0
    for sq in SQUARES:
        x, y, z = geo.square_world(sq, height)
        yaw = math.atan2(y, x)
        target = tcp_pose(x, y, z, yaw)
        q = mc.compute_ik(target, attempts=3)
        if q is None:
            print(f'{sq}: IK FAILED')
            failures += 1
            continue
        t0 = time.time()
        res = mc.move_to_joints(q)
        dt = time.time() - t0
        time.sleep(0.5)
        tf = buf.lookup_transform('world', 'tcp', rclpy.time.Time())
        p = tf.transform.translation
        err = math.dist((p.x, p.y, p.z), (target.position.x, target.position.y,
                                         target.position.z))
        ok = res.ok and err < 0.005
        failures += not ok
        print(f'{sq}: {res.message:8s} {dt:4.1f}s  pos_err={err * 1000:5.1f} mm  '
              f'{"PASS" if ok else "FAIL"}')
    # straight-line descent / ascent (Cartesian) at e4
    x, y, z = geo.square_world('e4', height)
    yaw = math.atan2(y, x)
    mc.move_to_joints(mc.compute_ik(tcp_pose(x, y, z, yaw), attempts=3))
    down = tcp_pose(x, y, z - 0.05, yaw)
    up = tcp_pose(x, y, z, yaw)
    r1 = mc.move_cartesian([down])
    r2 = mc.move_cartesian([up])
    print(f'cartesian down: {r1.ok} ({r1.message})  up: {r2.ok} ({r2.message})')
    failures += (not r1.ok) + (not r2.ok)
    print('RESULT:', 'PASS' if failures == 0 else f'{failures} FAILURES')
    node.destroy_node()
    rclpy.shutdown()
    return 0 if failures == 0 else 1


if __name__ == '__main__':
    main()
