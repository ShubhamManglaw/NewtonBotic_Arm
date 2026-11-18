"""Thin synchronous client for move_group's ROS 2 services/actions.

MoveIt's Python bindings (moveit_py) are not installed on this system, so this
talks to move_group directly:

  /compute_ik               moveit_msgs/srv/GetPositionIK
  /compute_cartesian_path   moveit_msgs/srv/GetCartesianPath
  /move_action              moveit_msgs/action/MoveGroup      (plan + execute)
  /execute_trajectory       moveit_msgs/action/ExecuteTrajectory
  /apply_planning_scene     moveit_msgs/srv/ApplyPlanningScene

The owning node MUST be spun by an executor in another thread (see
``spin_in_background``); every method here blocks on futures.
"""
import threading
from dataclasses import dataclass
from typing import List, Optional, Sequence

from geometry_msgs.msg import Pose, PoseStamped
from moveit_msgs.action import ExecuteTrajectory, MoveGroup
from moveit_msgs.msg import (AttachedCollisionObject, CollisionObject,
                             Constraints, JointConstraint, MoveItErrorCodes,
                             PlanningScene, RobotState, RobotTrajectory)
from moveit_msgs.srv import (ApplyPlanningScene, GetCartesianPath,
                             GetPositionIK)
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.duration import Duration
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from sensor_msgs.msg import JointState
from shape_msgs.msg import SolidPrimitive

ARM_JOINTS = ['Joint0', 'Joint1', 'Joint2', 'Joint3', 'Joint4', 'Joint5']


def spin_in_background(node: Node) -> MultiThreadedExecutor:
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    threading.Thread(target=executor.spin, daemon=True).start()
    return executor


def error_name(code: int) -> str:
    for k, v in MoveItErrorCodes.__dict__.items():
        if k.isupper() and v == code:
            return k
    return str(code)


@dataclass
class MotionResult:
    ok: bool
    message: str = ''
    trajectory: Optional[RobotTrajectory] = None
    fraction: float = 0.0


class MoveItClient:
    def __init__(self, node: Node, group: str = 'arm', ee_link: str = 'tool0',
                 frame: str = 'world', joint_names: Sequence[str] = ARM_JOINTS):
        self.node = node
        self.group = group
        self.ee_link = ee_link
        self.frame = frame
        self.joint_names = list(joint_names)
        self.velocity_scaling = 0.4
        self.acceleration_scaling = 0.4
        cb = ReentrantCallbackGroup()
        self._ik = node.create_client(GetPositionIK, 'compute_ik', callback_group=cb)
        self._cart = node.create_client(GetCartesianPath, 'compute_cartesian_path',
                                        callback_group=cb)
        self._scene = node.create_client(ApplyPlanningScene, 'apply_planning_scene',
                                         callback_group=cb)
        self._move = ActionClient(node, MoveGroup, 'move_action', callback_group=cb)
        self._exec = ActionClient(node, ExecuteTrajectory, 'execute_trajectory',
                                  callback_group=cb)
        self._js_lock = threading.Lock()
        self._js: Optional[JointState] = None
        node.create_subscription(JointState, 'joint_states', self._on_js, 10,
                                 callback_group=cb)

    # ------------------------------------------------------------------ utils
    def _on_js(self, msg: JointState):
        with self._js_lock:
            if self._js is None:
                self._js = JointState()
            # merge (gripper and arm may come from different broadcasters)
            d = dict(zip(self._js.name, self._js.position))
            d.update(zip(msg.name, msg.position))
            self._js.name = list(d.keys())
            self._js.position = list(d.values())

    def wait_ready(self, timeout: float = 30.0) -> bool:
        ok = (self._ik.wait_for_service(timeout) and self._cart.wait_for_service(timeout)
              and self._scene.wait_for_service(timeout)
              and self._move.wait_for_server(timeout_sec=timeout)
              and self._exec.wait_for_server(timeout_sec=timeout))
        return ok and self.current_joints(timeout) is not None

    def current_joints(self, timeout: float = 5.0) -> Optional[List[float]]:
        end = self.node.get_clock().now() + Duration(seconds=timeout)
        while True:
            with self._js_lock:
                if self._js is not None:
                    d = dict(zip(self._js.name, self._js.position))
                    if all(j in d for j in self.joint_names):
                        return [d[j] for j in self.joint_names]
            if self.node.get_clock().now() > end:
                return None
            threading.Event().wait(0.05)

    def _robot_state(self, joints: Optional[Sequence[float]] = None) -> RobotState:
        rs = RobotState()
        rs.is_diff = True
        if joints is not None:
            rs.joint_state.name = list(self.joint_names)
            rs.joint_state.position = [float(x) for x in joints]
        return rs

    @staticmethod
    def _wait(future, timeout: float):
        ev = threading.Event()
        future.add_done_callback(lambda _: ev.set())
        if not ev.wait(timeout):
            return None
        return future.result()

    def _stamped(self, pose: Pose) -> PoseStamped:
        ps = PoseStamped()
        ps.header.frame_id = self.frame
        ps.pose = pose
        return ps

    # --------------------------------------------------------------- queries
    def compute_ik(self, pose: Pose, seed: Optional[Sequence[float]] = None,
                   avoid_collisions: bool = True, timeout: float = 0.2,
                   attempts: int = 1) -> Optional[List[float]]:
        req = GetPositionIK.Request()
        r = req.ik_request
        r.group_name = self.group
        r.ik_link_name = self.ee_link
        r.pose_stamped = self._stamped(pose)
        r.avoid_collisions = avoid_collisions
        r.timeout = Duration(seconds=timeout).to_msg()
        for _ in range(attempts):
            r.robot_state = self._robot_state(seed if seed is not None
                                              else self.current_joints(1.0))
            res = self._wait(self._ik.call_async(req), timeout + 5.0)
            if res is not None and res.error_code.val == MoveItErrorCodes.SUCCESS:
                d = dict(zip(res.solution.joint_state.name,
                             res.solution.joint_state.position))
                return [d[j] for j in self.joint_names]
            seed = None  # retry from a random-ish (current) seed
        return None

    # -------------------------------------------------------------- planning
    def move_to_joints(self, joints: Sequence[float], plan_only: bool = False,
                       planning_time: float = 5.0, attempts: int = 3,
                       timeout: float = 60.0) -> MotionResult:
        goal = MoveGroup.Goal()
        req = goal.request
        req.group_name = self.group
        req.num_planning_attempts = attempts
        req.allowed_planning_time = planning_time
        req.max_velocity_scaling_factor = self.velocity_scaling
        req.max_acceleration_scaling_factor = self.acceleration_scaling
        req.start_state = self._robot_state()
        c = Constraints()
        for name, val in zip(self.joint_names, joints):
            c.joint_constraints.append(JointConstraint(
                joint_name=name, position=float(val), tolerance_above=1e-3,
                tolerance_below=1e-3, weight=1.0))
        req.goal_constraints = [c]
        goal.planning_options.plan_only = plan_only
        goal.planning_options.replan = True
        goal.planning_options.replan_attempts = 2
        return self._run_action(self._move, goal, timeout, planned=True)

    def cartesian_path(self, waypoints: Sequence[Pose], eef_step: float = 0.005,
                       avoid_collisions: bool = True,
                       start_joints: Optional[Sequence[float]] = None) -> MotionResult:
        req = GetCartesianPath.Request()
        req.header.frame_id = self.frame
        req.start_state = self._robot_state(start_joints)
        req.group_name = self.group
        req.link_name = self.ee_link
        req.waypoints = list(waypoints)
        req.max_step = eef_step
        req.jump_threshold = 0.0
        req.prismatic_jump_threshold = 0.0
        req.revolute_jump_threshold = 0.0
        req.avoid_collisions = avoid_collisions
        req.max_velocity_scaling_factor = self.velocity_scaling * 0.5
        req.max_acceleration_scaling_factor = self.acceleration_scaling * 0.5
        res = self._wait(self._cart.call_async(req), 15.0)
        if res is None:
            return MotionResult(False, 'compute_cartesian_path timed out')
        if res.error_code.val != MoveItErrorCodes.SUCCESS:
            return MotionResult(False, 'cartesian: ' + error_name(res.error_code.val))
        return MotionResult(res.fraction > 0.999, f'fraction={res.fraction:.3f}',
                            res.solution, res.fraction)

    def execute(self, trajectory: RobotTrajectory, timeout: float = 60.0) -> MotionResult:
        goal = ExecuteTrajectory.Goal()
        goal.trajectory = trajectory
        return self._run_action(self._exec, goal, timeout)

    def move_cartesian(self, waypoints: Sequence[Pose], **kw) -> MotionResult:
        res = self.cartesian_path(waypoints, **kw)
        if not res.ok:
            return res
        return self.execute(res.trajectory)

    def _run_action(self, client, goal, timeout, planned=False) -> MotionResult:
        gh = self._wait(client.send_goal_async(goal), 10.0)
        if gh is None or not gh.accepted:
            return MotionResult(False, 'goal rejected / server unavailable')
        res = self._wait(gh.get_result_async(), timeout)
        if res is None:
            self._wait(gh.cancel_goal_async(), 5.0)
            return MotionResult(False, f'timed out after {timeout:.0f}s (cancelled)')
        code = res.result.error_code.val
        traj = getattr(res.result, 'planned_trajectory', None) if planned else None
        return MotionResult(code == MoveItErrorCodes.SUCCESS, error_name(code), traj)

    # ---------------------------------------------------------- planning scene
    def apply_scene(self, scene: PlanningScene) -> bool:
        scene.is_diff = True
        scene.robot_state.is_diff = True
        res = self._wait(self._scene.call_async(ApplyPlanningScene.Request(scene=scene)), 10.0)
        return bool(res and res.success)

    def box(self, obj_id: str, size, pose: Pose) -> CollisionObject:
        return self._primitive(obj_id, SolidPrimitive.BOX, list(size), pose)

    def cylinder(self, obj_id: str, height: float, radius: float, pose: Pose) -> CollisionObject:
        return self._primitive(obj_id, SolidPrimitive.CYLINDER, [height, radius], pose)

    def _primitive(self, obj_id, kind, dims, pose) -> CollisionObject:
        co = CollisionObject()
        co.header.frame_id = self.frame
        co.id = obj_id
        co.primitives = [SolidPrimitive(type=kind, dimensions=[float(d) for d in dims])]
        co.primitive_poses = [pose]
        co.operation = CollisionObject.ADD
        return co

    def add_objects(self, objects: Sequence[CollisionObject]) -> bool:
        scene = PlanningScene()
        scene.world.collision_objects = list(objects)
        return self.apply_scene(scene)

    def remove_objects(self, ids: Sequence[str]) -> bool:
        scene = PlanningScene()
        for i in ids:
            co = CollisionObject()
            co.header.frame_id = self.frame
            co.id = i
            co.operation = CollisionObject.REMOVE
            scene.world.collision_objects.append(co)
        return self.apply_scene(scene)

    def attach(self, obj_id: str, link: str, touch_links: Sequence[str]) -> bool:
        """Move a world object onto the robot (planning only)."""
        scene = PlanningScene()
        aco = AttachedCollisionObject()
        aco.link_name = link
        aco.object.id = obj_id
        aco.object.header.frame_id = self.frame
        aco.object.operation = CollisionObject.ADD
        aco.touch_links = list(touch_links)
        scene.robot_state.attached_collision_objects = [aco]
        rm = CollisionObject()
        rm.id = obj_id
        rm.header.frame_id = self.frame
        rm.operation = CollisionObject.REMOVE
        scene.world.collision_objects = [rm]
        return self.apply_scene(scene)

    def detach(self, obj_id: str, link: str) -> bool:
        """Return an attached object to the world at its current pose."""
        scene = PlanningScene()
        aco = AttachedCollisionObject()
        aco.link_name = link
        aco.object.id = obj_id
        aco.object.operation = CollisionObject.REMOVE
        scene.robot_state.attached_collision_objects = [aco]
        return self.apply_scene(scene)
