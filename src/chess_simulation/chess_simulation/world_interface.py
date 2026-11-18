"""Chess world interface: piece tracking, reset and promotion swaps in Gazebo Sim.

Piece poses are read directly with gz-transport (the ros_gz bridge drops
entity names when converting Pose_V, and names identify pieces). Spawn/delete/
set-pose go through the ros_gz_bridge service bridge: gz-transport's Python
request() holds the GIL while blocking, which stalls the pose subscription
and makes every request run to its timeout.

ROS API (node name: chess_world)
  ~/get_piece_states  chess_interfaces/srv/GetPieceStates
  ~/reset             std_srvs/srv/Trigger     restore the standard start position
  ~/replace_piece     chess_interfaces/srv/ReplacePiece   (promotion)
  TF  world -> chessboard_frame  (static)
"""
import math
import threading
import time
from typing import Dict, Optional, Tuple

import rclpy
from geometry_msgs.msg import Pose, TransformStamped
from gz.msgs10.pose_v_pb2 import Pose_V
from gz.transport13 import Node as GzNode
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.node import Node
from ros_gz_interfaces.msg import Entity
from ros_gz_interfaces.srv import DeleteEntity, SetEntityPose, SpawnEntity
from std_srvs.srv import Trigger
from tf2_ros.static_transform_broadcaster import StaticTransformBroadcaster

from chess_interfaces.msg import PieceState
from chess_interfaces.srv import GetPieceStates, ReplacePiece
from chess_simulation.board import PIECE_NAMES, BoardGeometry, PieceSpec
from chess_simulation.world_gen import WORLD_NAME, piece_model_sdf

UPRIGHT_COS = math.cos(math.radians(15.0))


class ChessWorld(Node):
    def __init__(self):
        super().__init__('chess_world')
        self.world = self.declare_parameter('world_name', WORLD_NAME).value
        self.geo = BoardGeometry(path=self.declare_parameter('board_config', '').value or None)
        self.square_tol = self.geo.s * 0.35

        self._lock = threading.Lock()
        self._poses: Dict[str, Tuple[Tuple[float, float, float],
                                     Tuple[float, float, float, float]]] = {}
        self._stamp = 0.0
        self.start = {p.piece_id: p for p in BoardGeometry.starting_pieces()}
        self.registry: Dict[str, PieceSpec] = dict(self.start)
        self._promo_count = 0

        self.gz = GzNode()
        topic = f'/world/{self.world}/pose/info'
        if not self.gz.subscribe(Pose_V, topic, self._on_poses):
            raise RuntimeError(f'cannot subscribe to {topic}')

        cb = ReentrantCallbackGroup()
        w = f'/world/{self.world}'
        self._set_cli = self.create_client(SetEntityPose, f'{w}/set_pose', callback_group=cb)
        self._spawn_cli = self.create_client(SpawnEntity, f'{w}/create', callback_group=cb)
        self._remove_cli = self.create_client(DeleteEntity, f'{w}/remove', callback_group=cb)

        self.create_service(GetPieceStates, '~/get_piece_states', self._get_states,
                            callback_group=cb)
        self.create_service(Trigger, '~/reset', self._reset, callback_group=cb)
        self.create_service(ReplacePiece, '~/replace_piece', self._replace, callback_group=cb)

        self._tf = StaticTransformBroadcaster(self)
        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = 'world'
        t.child_frame_id = 'chessboard_frame'
        t.transform.translation.x = self.geo.x0
        t.transform.translation.y = self.geo.y0
        t.transform.translation.z = self.geo.top_z
        t.transform.rotation.z = math.sin(self.geo.yaw / 2)
        t.transform.rotation.w = math.cos(self.geo.yaw / 2)
        self._tf.sendTransform(t)
        self.get_logger().info(f'chess world interface up (world={self.world})')

    # ------------------------------------------------------------ gz helpers
    def _on_poses(self, msg: Pose_V):
        with self._lock:
            for p in msg.pose:
                if p.name in self.registry:
                    self._poses[p.name] = (
                        (p.position.x, p.position.y, p.position.z),
                        (p.orientation.x, p.orientation.y, p.orientation.z,
                         p.orientation.w))
            self._stamp = time.monotonic()

    def pose_of(self, piece_id: str):
        with self._lock:
            return self._poses.get(piece_id)

    def _fresh_snapshot(self, timeout=2.0) -> Optional[Dict]:
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout:
            with self._lock:
                if self._stamp > t0:
                    return dict(self._poses)
            time.sleep(0.02)
        return None

    def _call(self, client, req, timeout=5.0) -> bool:
        if not client.wait_for_service(timeout_sec=timeout):
            self.get_logger().error(f'service {client.srv_name} unavailable')
            return False
        ev = threading.Event()
        fut = client.call_async(req)
        fut.add_done_callback(lambda _: ev.set())
        if not ev.wait(timeout):
            self.get_logger().warn(f'{client.srv_name} timed out')
            return False
        return bool(fut.result().success)

    @staticmethod
    def _pose_msg(xyz, yaw=0.0) -> Pose:
        p = Pose()
        p.position.x, p.position.y, p.position.z = (float(v) for v in xyz)
        p.orientation.z = math.sin(yaw / 2)
        p.orientation.w = math.cos(yaw / 2)
        return p

    def _set_pose(self, name, xyz, yaw=0.0) -> bool:
        req = SetEntityPose.Request()
        req.entity.name = name
        req.entity.type = Entity.MODEL
        req.pose = self._pose_msg(xyz, yaw)
        return self._call(self._set_cli, req)

    def _spawn(self, spec: PieceSpec, xyz) -> bool:
        req = SpawnEntity.Request()
        req.entity_factory.name = spec.piece_id
        req.entity_factory.allow_renaming = False
        req.entity_factory.sdf = ('<sdf version="1.9">'
                                  + piece_model_sdf(self.geo, spec, include_pose=False)
                                  + '</sdf>')
        req.entity_factory.pose = self._pose_msg(xyz)
        return self._call(self._spawn_cli, req)

    def _remove(self, name) -> bool:
        req = DeleteEntity.Request()
        req.entity.name = name
        req.entity.type = Entity.MODEL
        ok = self._call(self._remove_cli, req)
        with self._lock:
            self._poses.pop(name, None)
        return ok

    # ------------------------------------------------------------- queries
    def piece_state(self, pid: str, pose) -> PieceState:
        spec = self.registry[pid]
        (x, y, z), (qx, qy, qz, qw) = pose
        st = PieceState(piece_id=pid, color=spec.color, kind=spec.kind)
        st.pose.position.x, st.pose.position.y, st.pose.position.z = x, y, z
        st.pose.orientation.x, st.pose.orientation.y = qx, qy
        st.pose.orientation.z, st.pose.orientation.w = qz, qw
        # z-axis of piece in world: R[2][2] = 1 - 2(qx^2 + qy^2)
        st.upright = (1 - 2 * (qx * qx + qy * qy)) > UPRIGHT_COS
        on_board_height = abs(z - self.geo.top_z) < 0.005
        sq = self.geo.world_to_square(x, y, tol=self.square_tol)
        st.square = sq if (sq and on_board_height) else ''
        st.in_graveyard = any(
            math.hypot(x - gx, y - gy) < self.geo.graveyard['spacing'] * 0.5
            for c in ('white', 'black') for gx, gy, _ in
            (self.geo.graveyard_world(c, i) for i in range(16)))
        return st

    def _get_states(self, _req, res):
        snap = self._fresh_snapshot()
        if snap is None:
            res.success, res.message = False, 'no pose data from Gazebo'
            return res
        res.pieces = [self.piece_state(pid, snap[pid]) for pid in self.registry if pid in snap]
        missing = [pid for pid in self.registry if pid not in snap]
        res.success = True
        res.message = f'{len(res.pieces)} pieces' + (f'; missing {missing}' if missing else '')
        return res

    # --------------------------------------------------------------- reset
    def _reset(self, _req, res):
        for pid in [p for p in self.registry if p not in self.start]:
            self._remove(pid)
            del self.registry[pid]
        self._promo_count = 0
        with self._lock:
            self.registry = dict(self.start)   # re-register pieces removed by promotion
        snap = self._fresh_snapshot() or {}
        for pid, spec in self.start.items():
            x, y, z = self.geo.square_world(spec.square)
            if pid in snap:
                self._set_pose(pid, (x, y, z + 0.001))
            else:
                self._spawn(spec, (x, y, z + 0.001))
        # verify
        time.sleep(1.5)
        bad = []
        snap = self._fresh_snapshot() or {}
        for pid, spec in self.start.items():
            if pid not in snap:
                bad.append(f'{pid}: missing')
                continue
            st = self.piece_state(pid, snap[pid])
            if st.square != spec.square or not st.upright:
                bad.append(f'{pid}: at {st.square or "off-board"} upright={st.upright}')
        res.success = not bad
        res.message = 'board reset to start position' if not bad else '; '.join(bad)
        self.get_logger().info(f'reset: {res.message}')
        return res

    # ----------------------------------------------------------- promotion
    def _replace(self, req, res):
        old = self.registry.get(req.piece_id)
        kind = req.new_kind.upper()
        if old is None or kind not in ('Q', 'R', 'B', 'N'):
            res.success, res.message = False, 'unknown piece or invalid kind'
            return res
        pose = self.pose_of(req.piece_id)
        if pose is None:
            res.success, res.message = False, f'no pose for {req.piece_id}'
            return res
        (x, y, _), _q = pose
        sq = self.geo.world_to_square(x, y) or old.square
        self._promo_count += 1
        new_id = f'{old.color}_{PIECE_NAMES[kind]}_promo{self._promo_count}'
        spec = PieceSpec(new_id, old.color, kind, sq)
        self._remove(req.piece_id)
        del self.registry[req.piece_id]
        self.registry[new_id] = spec
        cx, cy, cz = self.geo.square_world(sq)
        self._spawn(spec, (cx, cy, cz + 0.001))
        time.sleep(1.0)
        snap = self._fresh_snapshot() or {}
        ok = new_id in snap and self.piece_state(new_id, snap[new_id]).square == sq
        res.success, res.new_piece_id = ok, new_id
        res.message = f'{req.piece_id} -> {new_id} on {sq}' if ok else 'spawn not confirmed'
        self.get_logger().info(f'replace: {res.message}')
        return res


def main():
    rclpy.init()
    node = ChessWorld()
    from rclpy.executors import MultiThreadedExecutor
    ex = MultiThreadedExecutor(num_threads=3)
    ex.add_node(node)
    try:
        ex.spin()
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.try_shutdown()


if __name__ == '__main__':
    main()
