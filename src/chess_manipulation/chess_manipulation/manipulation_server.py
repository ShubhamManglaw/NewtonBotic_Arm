"""Chess piece manipulation action server (no chess rules here).

Action  /execute_moves  chess_interfaces/action/ExecuteMoves

Each PieceMove is executed as explicit, individually verified stages:

  VALIDATE -> SCENE -> PRE_GRASP -> OPEN -> APPROACH -> CLOSE -> VERIFY_GRASP
  -> LIFT -> VERIFY_LIFT -> TRANSFER -> LOWER -> RELEASE -> RETREAT -> VERIFY_PLACE

Motion uses MoveIt (OMPL for free-space moves, Cartesian paths for vertical
approach/lift/lower/retreat and level transfer). Success is reported only after
the piece is observed (via the chess_world interface) on its destination.
"""
import math
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import rclpy
from control_msgs.action import GripperCommand
from geometry_msgs.msg import Point, Pose
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.node import Node

from chess_interfaces.action import ExecuteMoves
from chess_interfaces.msg import PieceMove, PieceState
from chess_interfaces.srv import GetPieceStates, ReplacePiece, SetPiecePose
from chess_manipulation.geometry import tool_pose_for_tcp
from chess_manipulation.moveit_client import MoveItClient, spin_in_background
from chess_simulation.board import BoardGeometry


class StageError(Exception):
    def __init__(self, stage: str, category: str, message: str):
        super().__init__(message)
        self.stage, self.category, self.message = stage, category, message


@dataclass
class Grasp:
    yaw: float
    grasp_q: List[float]


class ManipulationServer(Node):
    def __init__(self):
        super().__init__('chess_manipulation')
        p = self.declare_parameter
        self.tcp = p('tcp_offset', 0.11).value
        self.approach_h = p('approach_height', 0.06).value
        self.transport_h = p('transport_height', 0.10).value
        self.release_clear = p('release_clearance', 0.002).value
        self.yaw_offsets = [math.radians(d) for d in
                            p('grasp_yaw_offsets_deg', [45.0, 135.0, -45.0, -135.0]).value]
        self.stage_timeout = p('stage_timeout', 30.0).value
        self.rest_joints = list(p('rest_joints', [0.0] * 6).value)
        self.mode = p('execution_mode', 'teleport').value
        self.place_tol = p('place_tolerance', 0.006).value
        self.g_action = p('gripper.action', '/gripper_controller/gripper_cmd').value
        self.g_open = p('gripper.open_position', 0.0).value
        self.g_close = p('gripper.close_position', 0.0).value
        self.g_effort = p('gripper.max_effort', 5.0).value
        self.g_hold_min = p('gripper.holding_min_position', 0.0).value
        self.g_settle = p('gripper.settle_time', 0.5).value
        vel = p('velocity_scaling', 0.4).value
        acc = p('acceleration_scaling', 0.4).value

        self.geo = BoardGeometry()
        cb = ReentrantCallbackGroup()
        self.mc = MoveItClient(self)
        self.mc.velocity_scaling, self.mc.acceleration_scaling = vel, acc
        self._states_cli = self.create_client(GetPieceStates, '/chess_world/get_piece_states',
                                              callback_group=cb)
        self._replace_cli = self.create_client(ReplacePiece, '/chess_world/replace_piece',
                                               callback_group=cb)
        self._teleport_cli = self.create_client(SetPiecePose, '/chess_world/set_piece_pose',
                                                callback_group=cb)
        self._gripper = ActionClient(self, GripperCommand, self.g_action, callback_group=cb)
        self._busy = threading.Lock()
        self._scene_ready = False
        self._server = ActionServer(
            self, ExecuteMoves, 'execute_moves', execute_callback=self._execute,
            goal_callback=self._on_goal, cancel_callback=lambda _: CancelResponse.ACCEPT,
            callback_group=cb)
        if self.mode == 'teleport':
            self.get_logger().warn(
                'execution_mode=teleport: TEST MODE. Arm motions are real, but pieces are '
                'moved by Gazebo set_pose, not grasped. Not evidence of grasp capability.')
        self.get_logger().info(f'manipulation server ready (mode={self.mode}, tcp={self.tcp})')

    # =============================================================== plumbing
    def _call(self, client, req, timeout=10.0):
        if not client.wait_for_service(timeout_sec=5.0):
            return None
        ev = threading.Event()
        fut = client.call_async(req)
        fut.add_done_callback(lambda _: ev.set())
        return fut.result() if ev.wait(timeout) else None

    def piece_states(self) -> Dict[str, PieceState]:
        res = self._call(self._states_cli, GetPieceStates.Request())
        if res is None or not res.success:
            raise StageError('VALIDATE', 'WORLD', 'cannot read piece states from chess_world')
        return {s.piece_id: s for s in res.pieces}

    def _on_goal(self, _goal):
        if self._busy.locked():
            self.get_logger().warn('rejecting goal: already executing')
            return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    # ================================================================ action
    def _execute(self, gh):
        req = gh.request
        res = ExecuteMoves.Result()
        log = self.get_logger()
        with self._busy:
            log.info(f'[{req.request_id}] {len(req.moves)} piece move(s)')
            try:
                if not self.mc.wait_ready(10.0):
                    raise StageError('VALIDATE', 'PLANNING', 'move_group not available')
                for i, mv in enumerate(req.moves):
                    self._goal, self._index, self._piece = gh, i, mv.piece_id
                    self._run_move(mv)
                    res.moves_completed = i + 1
                self._stage('REST')
                self.mc.move_to_joints(self.rest_joints)
                res.success = True
                res.message = 'all moves executed and verified'
                gh.succeed()
            except StageError as e:
                res.success = False
                res.failure_stage, res.failure_category = e.stage, e.category
                res.message = e.message
                log.error(f'[{req.request_id}] FAILED at {e.stage} ({e.category}): {e.message}')
                self._recover()
                if e.category == 'CANCELLED':
                    gh.canceled()
                else:
                    gh.abort()
            log.info(f'[{req.request_id}] result: success={res.success} '
                     f'completed={res.moves_completed}/{len(req.moves)}')
            return res

    def _stage(self, name: str):
        if self._goal.is_cancel_requested:
            raise StageError(name, 'CANCELLED', 'cancel requested')
        fb = ExecuteMoves.Feedback(move_index=self._index, piece_id=self._piece, stage=name)
        self._goal.publish_feedback(fb)
        self.get_logger().info(f'  [{self._index}] {self._piece}: {name}')

    def _recover(self):
        """Best effort: back away upward and release anything attached in the scene."""
        try:
            for pid in self._attached():
                self.mc.detach(pid, 'tool0')
            cur = self.mc.current_joints(1.0)
            if cur is not None:
                self.mc.move_to_joints(self.rest_joints)
        except Exception as e:  # noqa: BLE001
            self.get_logger().error(f'recovery failed: {e}')

    def _attached(self) -> List[str]:
        return [self._piece] if getattr(self, '_holding', False) else []

    # ============================================================ one move
    def _run_move(self, mv: PieceMove):
        self._holding = False
        self._stage('VALIDATE')
        states = self.piece_states()
        st = states.get(mv.piece_id)
        if st is None:
            raise StageError('VALIDATE', 'INVALID', f'unknown piece {mv.piece_id}')

        if mv.operation == PieceMove.REPLACE:
            return self._replace(mv, st)

        if st.square != mv.from_square or not st.upright:
            raise StageError('VALIDATE', 'INVALID',
                             f'{mv.piece_id} expected upright on {mv.from_square}, observed '
                             f'square={st.square or "none"} upright={st.upright}')
        if mv.operation == PieceMove.MOVE:
            occupied = [s.piece_id for s in states.values()
                        if s.square == mv.to_square and s.piece_id != mv.piece_id]
            if occupied:
                raise StageError('VALIDATE', 'INVALID',
                                 f'destination {mv.to_square} occupied by {occupied}')
            dest = self.geo.square_world(mv.to_square)
            dest_label = mv.to_square
        elif mv.operation == PieceMove.REMOVE:
            slot = self._free_graveyard_slot(st.color, states)
            dest = self.geo.graveyard_world(st.color, slot)
            dest_label = f'{st.color} graveyard slot {slot}'
        else:
            raise StageError('VALIDATE', 'INVALID', f'unknown operation {mv.operation}')

        src = (st.pose.position.x, st.pose.position.y, self.geo.top_z)
        self.get_logger().info(f'    {mv.piece_id}: ({src[0]:.3f},{src[1]:.3f}) -> '
                               f'{dest_label} ({dest[0]:.3f},{dest[1]:.3f})')
        self._update_scene(states, exclude=mv.piece_id)
        self._pick(mv.piece_id, src, st.kind)
        self._place(mv.piece_id, dest, st.kind)
        self._verify_place(mv, dest, dest_label)

    # -------------------------------------------------------------- stages
    def _grasp_z(self, base_z: float) -> float:
        return base_z + self.geo.grasp_height

    def _plan_grasp(self, x, y, z) -> Grasp:
        """Choose a gripper yaw for which grasp, approach and transport poses all have IK."""
        base_yaw = self.geo.yaw
        for off in self.yaw_offsets:
            yaw = base_yaw + off
            q_grasp = self.mc.compute_ik(tool_pose_for_tcp(x, y, z, yaw, self.tcp), attempts=3)
            if q_grasp is None:
                continue
            ok = all(self.mc.compute_ik(tool_pose_for_tcp(x, y, z + h, yaw, self.tcp),
                                        seed=q_grasp) is not None
                     for h in (self.approach_h, self.transport_h - self.geo.grasp_height))
            if ok:
                return Grasp(yaw, q_grasp)
        raise StageError('PRE_GRASP', 'PLANNING', f'no reachable grasp at ({x:.3f},{y:.3f})')

    def _move_joints(self, stage, q):
        r = self.mc.move_to_joints(q, timeout=self.stage_timeout)
        if not r.ok:
            raise StageError(stage, 'PLANNING' if 'PLAN' in r.message or 'INVALID' in r.message
                             else 'CONTROLLER', f'{stage}: {r.message}')

    def _move_linear(self, stage, pose: Pose, avoid_collisions=True):
        r = self.mc.move_cartesian([pose], avoid_collisions=avoid_collisions)
        if not r.ok:
            raise StageError(stage, 'PLANNING' if r.trajectory is None or r.fraction < 0.999
                             else 'CONTROLLER', f'{stage}: {r.message}')

    def _pick(self, pid, src, kind):
        x, y, base_z = src
        gz = self._grasp_z(base_z)
        g = self._plan_grasp(x, y, gz)
        self._yaw = g.yaw
        self._stage('PRE_GRASP')
        pre = self.mc.compute_ik(tool_pose_for_tcp(x, y, gz + self.approach_h, g.yaw, self.tcp),
                                 seed=g.grasp_q)
        self._move_joints('PRE_GRASP', pre)
        self._stage('OPEN')
        self._gripper_cmd('OPEN', self.g_open)
        self._stage('APPROACH')
        # Target piece was excluded from the scene; neighbours are still checked.
        self._move_linear('APPROACH', tool_pose_for_tcp(x, y, gz, g.yaw, self.tcp))
        self._stage('CLOSE')
        pos = self._gripper_cmd('CLOSE', self.g_close)
        self._stage('VERIFY_GRASP')
        if self.mode == 'gripper' and pos is not None and pos <= self.g_hold_min:
            raise StageError('VERIFY_GRASP', 'GRASP',
                             f'fingers closed to {pos:.4f} (<= {self.g_hold_min}): nothing held')
        self._attach_scene(pid, kind, x, y, base_z)
        self._holding = True
        self._stage('LIFT')
        self._move_linear('LIFT', tool_pose_for_tcp(x, y, base_z + self.transport_h,
                                                    g.yaw, self.tcp))
        self._stage('VERIFY_LIFT')
        if self.mode == 'gripper':
            time.sleep(0.3)
            st = self.piece_states().get(pid)
            if st is None or st.pose.position.z < base_z + 0.03:
                raise StageError('VERIFY_LIFT', 'GRASP',
                                 f'{pid} did not lift with the gripper (slipped)')

    def _place(self, pid, dest, kind):
        x, y, base_z = dest
        top = base_z + self.transport_h
        place_z = self._grasp_z(base_z) + self.release_clear
        self._stage('TRANSFER')
        transfer = tool_pose_for_tcp(x, y, top, self._yaw, self.tcp)
        r = self.mc.move_cartesian([transfer])
        if not r.ok:   # fall back to a collision-aware free-space plan at the same pose
            q = self.mc.compute_ik(transfer, attempts=3)
            if q is None:
                raise StageError('TRANSFER', 'PLANNING', 'no IK above destination')
            self._move_joints('TRANSFER', q)
        self._stage('LOWER')
        self._move_linear('LOWER', tool_pose_for_tcp(x, y, place_z, self._yaw, self.tcp))
        self._stage('RELEASE')
        if self.mode == 'teleport':
            res = self._call(self._teleport_cli, SetPiecePose.Request(
                piece_id=pid, position=Point(x=x, y=y, z=base_z)))
            if res is None or not res.success:
                raise StageError('RELEASE', 'WORLD', f'teleport of {pid} failed')
        self._gripper_cmd('RELEASE', self.g_open)
        self.mc.detach(pid, 'tool0')
        self._holding = False
        self._stage('RETREAT')
        # The released piece is now back in the planning scene directly below the
        # fingers, so the short vertical retreat skips collision checking.
        self._move_linear('RETREAT', tool_pose_for_tcp(x, y, place_z + self.approach_h,
                                                       self._yaw, self.tcp),
                          avoid_collisions=False)

    def _verify_place(self, mv, dest, label):
        self._stage('VERIFY_PLACE')
        time.sleep(0.3)
        st = self.piece_states().get(mv.piece_id)
        if st is None:
            raise StageError('VERIFY_PLACE', 'VERIFY', f'{mv.piece_id} disappeared')
        err = math.hypot(st.pose.position.x - dest[0], st.pose.position.y - dest[1])
        if not st.upright or err > self.place_tol:
            raise StageError('VERIFY_PLACE', 'VERIFY',
                             f'{mv.piece_id} at {label}: xy error {err * 1000:.1f} mm, '
                             f'upright={st.upright}')
        if mv.operation == PieceMove.MOVE and st.square != mv.to_square:
            raise StageError('VERIFY_PLACE', 'VERIFY', f'{mv.piece_id} observed on {st.square}')
        if mv.operation == PieceMove.REMOVE and not st.in_graveyard:
            raise StageError('VERIFY_PLACE', 'VERIFY', f'{mv.piece_id} not in graveyard')
        self.get_logger().info(f'    verified {mv.piece_id} at {label} '
                               f'(err {err * 1000:.1f} mm)')

    def _replace(self, mv, st):
        self._stage('REPLACE')
        if st.square != mv.to_square:
            raise StageError('REPLACE', 'INVALID',
                             f'{mv.piece_id} must be on {mv.to_square} to promote')
        res = self._call(self._replace_cli, ReplacePiece.Request(
            piece_id=mv.piece_id, new_kind=mv.promotion))
        if res is None or not res.success:
            raise StageError('REPLACE', 'WORLD', f'promotion swap failed: '
                             f'{res.message if res else "no response"}')
        self.get_logger().info(f'    {res.message}')

    # ------------------------------------------------------------ gripper
    def _gripper_cmd(self, stage, position) -> Optional[float]:
        if self.mode == 'teleport':
            return None
        if not self._gripper.wait_for_server(timeout_sec=5.0):
            raise StageError(stage, 'CONTROLLER', f'gripper action {self.g_action} unavailable')
        goal = GripperCommand.Goal()
        goal.command.position = float(position)
        goal.command.max_effort = float(self.g_effort)
        ev = threading.Event()
        fut = self._gripper.send_goal_async(goal)
        fut.add_done_callback(lambda _: ev.set())
        if not ev.wait(10.0) or not fut.result().accepted:
            raise StageError(stage, 'CONTROLLER', 'gripper goal rejected')
        ev2 = threading.Event()
        rf = fut.result().get_result_async()
        rf.add_done_callback(lambda _: ev2.set())
        if not ev2.wait(self.stage_timeout):
            raise StageError(stage, 'CONTROLLER', 'gripper timed out')
        time.sleep(self.g_settle)
        return rf.result().result.position

    # -------------------------------------------------------- planning scene
    def _update_scene(self, states: Dict[str, PieceState], exclude: str):
        objs = []
        g = self.geo
        if not self._scene_ready:
            board = Pose()
            board.position.x, board.position.y = g.x0, g.y0
            board.position.z = g.thickness / 2
            board.orientation.z, board.orientation.w = math.sin(g.yaw / 2), math.cos(g.yaw / 2)
            objs.append(self.mc.box('chessboard', (g.size, g.size, g.thickness), board))
            for color in ('white', 'black'):
                pts = [g.graveyard_world(color, i) for i in range(16)]
                tray = Pose()
                tray.position.x = sum(p[0] for p in pts) / 16
                tray.position.y = sum(p[1] for p in pts) / 16
                tray.position.z = g.thickness / 2
                tray.orientation.w = 1.0
                w = max(p[0] for p in pts) - min(p[0] for p in pts) + 0.03
                ln = max(p[1] for p in pts) - min(p[1] for p in pts) + 0.03
                objs.append(self.mc.box(f'graveyard_{color}', (w, ln, g.thickness), tray))
        for s in states.values():
            if s.piece_id == exclude:
                continue
            h = g.piece_height(s.kind)
            p = Pose()
            p.position.x, p.position.y = s.pose.position.x, s.pose.position.y
            p.position.z = s.pose.position.z + h / 2
            p.orientation.w = 1.0
            objs.append(self.mc.cylinder(s.piece_id, h, g.pieces['base_radius'], p))
        self.mc.remove_objects([exclude])
        if not self.mc.add_objects(objs):
            raise StageError('SCENE', 'PLANNING', 'failed to update planning scene')
        self._scene_ready = True

    def _attach_scene(self, pid, kind, x, y, base_z):
        h = self.geo.piece_height(kind)
        p = Pose()
        p.position.x, p.position.y, p.position.z = x, y, base_z + h / 2
        p.orientation.w = 1.0
        self.mc.add_objects([self.mc.cylinder(pid, h, self.geo.pieces['base_radius'], p)])
        self.mc.attach(pid, 'tool0', touch_links=['tool0', 'Link_6', 'Link_5'])

    # ---------------------------------------------------------- graveyard
    def _free_graveyard_slot(self, color, states) -> int:
        taken = set()
        for s in states.values():
            for i in range(16):
                gx, gy, _ = self.geo.graveyard_world(color, i)
                if math.hypot(s.pose.position.x - gx, s.pose.position.y - gy) < \
                        self.geo.graveyard['spacing'] * 0.5:
                    taken.add(i)
        for i in range(16):
            if i not in taken:
                return i
        raise StageError('VALIDATE', 'INVALID', f'{color} graveyard full')


def main():
    rclpy.init()
    node = ManipulationServer()
    ex = spin_in_background(node)
    try:
        while rclpy.ok():
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    ex.shutdown()
    node.destroy_node()
    rclpy.try_shutdown()


if __name__ == '__main__':
    main()

