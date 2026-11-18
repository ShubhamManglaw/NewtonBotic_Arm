# Project Audit — NewtonBotic Arm (Phase 0 baseline)

Audit date: 2026-11-18. Audited commit: `d69a6ca` plus the uncommitted working tree.

## 1. Environment

| Item | Value |
|---|---|
| OS | Ubuntu 24.04.5 LTS |
| ROS 2 | Jazzy (`/opt/ros/jazzy`) |
| Simulator | Modern Gazebo (gz sim **8.15 / Harmonic**) via `ros_gz_sim`, not Gazebo Classic |
| ros2_control | `gz_ros2_control` (`GazeboSimSystem`) |
| MoveIt 2 | Installed (`moveit`, OMPL, KDL, `moveit_setup_assistant`, `moveit_simple_controller_manager`) |
| Gripper controllers | `parallel_gripper_controller`, `gripper_controllers` installed |
| Chess | `python-chess` **not installed**, `stockfish` **not installed** |

## 2. Workspace layout

The repository root is the colcon workspace (`src/`, plus `build/ install/ log/`, which are ignored).

| Package | Type | Status |
|---|---|---|
| `robot_description` | ament_cmake | URDF/Xacro, 7 STL meshes, RViz config, `rsp.launch.py`, `display.launch.py` |
| `robot_bringup` | ament_cmake | `gazebo.launch.py`, `config/controllers.yaml` |
| `robot_control` | ament_python | Empty stub |
| `robot_utils` | ament_python | Empty stub |
| `robot_interfaces` | ament_cmake | Empty stub (no msg/srv/action) |

Other root files: `Assem1.gv/pdf` and `frames_*.gv/pdf` (TF snapshots), `tools/check_stl.py`, and an empty `README.md`.

## 3. Build baseline

`colcon build --symlink-install` builds all 5 packages with no errors.
`check_urdf` parses the expanded Xacro: `world → base_link → Link_1 → … → Link_6`.

## 4. Robot model

Authoritative entry point: `src/robot_description/urdf/robot.urdf.xacro`. It is plain URDF with no macros or includes. `robot.urdf` is a near-identical copy and `robot.urdf.backup` is an older backup.

| Joint | Parent → Child | Axis (local) | Approx. world axis at q=0 | Limits (rad) | Role |
|---|---|---|---|---|---|
| `world_to_base` | world → base_link | fixed | — | — | anchor |
| `Joint0` | base_link → Link_1 | y | +Z | ±3.1416 | base yaw |
| `Joint1` | Link_1 → Link_2 | x | +X | ±1.5708 | shoulder pitch |
| `Joint2` | Link_2 → Link_3 | x | +X | ±2.618 | elbow pitch |
| `Joint3` | Link_3 → Link_4 | x | ≈+Y (forearm) | ±3.1416 | forearm roll |
| `Joint4` | Link_4 → Link_5 | z | ≈−X | ±2.0944 | wrist pitch |
| `Joint5` | Link_5 → Link_6 | y | ≈+Y | ±6.2832 | tool roll |

Forward kinematics at q=0, computed from the URDF and confirmed by TF in Gazebo:

| Frame | World position (m) |
|---|---|
| Joint0 (base yaw) | (0, 0, 0.0405) |
| Joint1 (shoulder) | (−0.001, 0.020, 0.145) |
| Joint2 / Joint3 origin | (−0.001, 0.023, 0.345), so the upper arm is 0.200 m |
| Joint4 (wrist) | (−0.008, 0.197, 0.313), so the forearm is ≈0.177 m |
| Link_6 (flange) | (−0.011, 0.224, 0.311) |

- **Root link:** `world` (fixed) → `base_link`.
- **End-effector:** `Link_6`, a 48 mm-diameter flange. There is no tool frame or TCP link.
- **Reach:** about 0.38 m horizontally from the shoulder axis to the wrist centre, before any gripper is added.
- **Mass:** about 2 kg in total.

## 5. Simulation baseline

Launch command: `ros2 launch robot_bringup gazebo.launch.py`, which loads `empty.sdf` and spawns entity `NewtonBotic_Arm`.

- **GUI mode** aborts the whole `gz sim` process when no display is available (Qt xcb). The launch has no headless option.
- **Headless mode** (`gz_args: -s -r empty.sdf`) works:
  - `joint_state_broadcaster` and `arm_controller` (JointTrajectoryController) are both **active**.
  - The action is `/arm_controller/follow_joint_trajectory`, with position command and position/velocity state interfaces.
  - `/clock` runs at about 1000 Hz, which is real time.
  - A test trajectory to `[0.5, 0.4, 0.6, 0.3, 0.5, 0.2]` over 3 s returned **SUCCEEDED**, and `/joint_states` matched the goal to within 1e-11.
  - TF `world→Link_6` at q=0 is `[-0.011, 0.224, 0.311]`, which agrees with the FK above.

## 6. Status of the larger system

| Component | Status |
|---|---|
| Gripper | **Missing.** There is no gripper CAD in the repo. |
| MoveIt config | **Missing.** There is no SRDF or moveit_config package. |
| Chess world/assets | **Missing.** |
| Interfaces | **Missing.** `robot_interfaces` is empty. |
| Chess logic | **Missing.** Dependencies are also not installed. |

## 7. Known defects and risks

1. **Base frame offset compensation.** The `base_link.STL` geometry sits about 1.5 m away from its own frame origin.
   - `world_to_base` (−0.588, 1.356, −0.783) and the `Joint0` origin (+0.588, −1.356, +0.824) cancel each other out.
   - The `base_link` inertial origin is expressed in a frame rotated 90° about X relative to the mesh.
   - It renders correctly, but `base_link` is not a meaningful frame for MoveIt, the planning scene or board placement.
   - **Fix:** move the offset into the base visual/collision `<origin>`, so `base_link` sits at the floor under the yaw axis. The STL files are not edited.
2. **Mesh complexity.** The meshes total about 917k triangles (Link_2 alone is 349k), and the full-resolution STLs are also used as **collision** geometry. This makes Gazebo contact and MoveIt collision checking slow.
   - **Fix:** generate simplified collision meshes in a separate folder and keep the CAD visual meshes unchanged.
3. **Non-orthogonal zero pose.** The CAD assembly pose is baked into the joint origins: Joint0 yaw 0.042, Joint1 roll −1.5859, Joint2 roll 1.4024 and Joint3 roll 0.1066.
   - This is kinematically consistent: pivots and axes line up with the link geometry.
   - The cost is that q=0 is a slightly skewed pose, which only affects named poses.
4. **`display.launch.py` is broken.** It references the undefined names `pkg_robot_description` and `robot_description`, so it raises a NameError.
5. **No headless launch argument**, and `gz_ros2_control` reports `position_proportional_gain 0.1`. Position control is effectively kinematic, which is fine for this project.
6. **Repository hygiene:**
   - Stray `gazebo.launch.py.save` and `__pycache__` in `src/`.
   - Duplicate `robot.urdf`, `robot.urdf.backup`, and an empty README.
   - A large uncommitted change set: the package restructure and the removal of `install/` from the index.
7. **No tool/TCP frame and no gripper.** These are required before MoveIt end-effector planning.

## 8. Phase 1 resolution (robot description)

- §7.1 fixed: `base_link` now sits at the floor under the yaw axis, `world_to_base` is the identity, and `Joint0` is at z=0.04051. The base inertia was re-expressed in the mesh frame. Every downstream frame is numerically unchanged, verified by FK and by Gazebo TF.
- §7.2 fixed: convex-hull collision meshes are in `meshes/collision/`, generated by `tools/make_collision_meshes.py` (about 5k triangles in total). The CAD STLs are untouched.
- §7.4/7.5 fixed: `display.launch.py` works, and `gazebo.launch.py` takes the arguments `headless`, `world`, `use_gripper`, `controllers_file` and `spawn_x/y/z`.
- Added a `tool0` flange frame (Link_6 face, +Z out of the flange) for mounting the gripper.
- The Xacro is split into `newtonbotic_arm.xacro` (links and joints), `arm.ros2_control.xacro` and `arm.gazebo.xacro`. The entry point `robot.urdf.xacro` takes the args `use_gazebo` and `use_gripper`.
- Removed the stale duplicates `robot.urdf`, `robot.urdf.backup` and `gazebo.launch.py.save` (they remain in git history).
- §7.3 (skewed CAD zero pose) is kept on purpose: it is consistent, and named poses will be defined in the SRDF.

## 9. Robot swap: HELENE arm + gripper (branch `helene-arm-swap`)

The original CAD arm (`Joint0..5`, `Link_1..6`, `tool0`) was replaced by the HELENE model from `helene_description` (commit `bf83584`).

### Integration

- `src/helene_description` is a trimmed, vendored package that keeps the upstream package name.
- Its generated xacro, `materials.xacro` and meshes are copied unmodified. See `VENDORED.md` and `tools/sync_helene_description.sh`.
- `robot_description/urdf/robot.urdf.xacro` instantiates `<xacro:helene_arm parent="world"/>` and adds the project-owned ros2_control and Gazebo files.

### Name mapping (old → new)

| Old | New | Notes |
|---|---|---|
| Joint0 | joint1 | base yaw, +Z |
| Joint1 | joint2 | shoulder, +Y |
| Joint2 | joint3 | elbow, −Y |
| Joint3 | joint4 | forearm roll, +X |
| Joint4 | joint5 | wrist pitch, −Y |
| Joint5 | joint6 | tool roll, +X |
| base_link | base_link | |
| Link_1…Link_6 | link1…link6 | |
| tool0 (flange, +Z out) | tcp (between the pads, **+X** = approach) | `gripper_base` sits between link6 and tcp |
| none | finger_r_joint / finger_l_joint | prismatic, 0–0.02 m each, positive = open |

### Model checks against helene AGENTS.md (all passed)

- The chain, axes and positions match the spec table.
- TCP at zero is (0.3558, −0.0003, 0.3452).
- `ready` = [0, 11, 0.46, 0, −79.46, 0]° puts the TCP at (0.232, 0, 0.150) with +X pointing down. This was confirmed both offline and by Gazebo TF.
- All inertias are positive-definite and satisfy the triangle inequality, and every centre of mass lies inside its mesh.
- Finger visual and collision geometry agree. The racks cross the centreline near the pinion by design and have no collision geometry there.
- The pads give a 0 mm gap at 0 and 40 mm at 0.02.

### Finding: start-up stick of finger_l in Gazebo (not a model defect, mitigated in this project)

- **Symptom:** with both fingers spawned at 0, their lower limit, where the pad faces coincide exactly at y=0, `finger_l_joint` ignored commands under gz_ros2_control until both fingers had been closed together once. `finger_r_joint` tracked every command. This was reproduced 3 times.
- **Not the axis:** flipping finger_l's axis sign in a scratch copy did not fix it.
- **Fix:** starting both fingers at 0.005 m (`initial_value` in `robot_description/urdf/arm.ros2_control.xacro`) fixed it completely. Every command was then tracked, including 40 mm and 0 mm.
- The generated model was not edited.

### Chess adaptations

- **Board:** moved in front of the arm along +X (centre (0.22, 0), yaw +90°, rank 8 nearest the robot). The 30 mm squares are kept: all 64 squares and all 32 graveyard slots are reachable top-down with the real TCP.
- **Grasp height:** 24 mm. The pads span TCP ±16 mm, so this puts them on the 15 mm body, clear of the 22 mm base disc. At 20 mm the pads pinched the base rim (fingers stopped at a 22 mm gap).
- **Gripper control:** `JointGroupPositionController` on both fingers with equal values, so jaw gap = 2 × value. Open 12 mm/finger, close target 6 mm/finger (force-limited squeeze), and "holding" means the fingers stopped wider than 6.8 mm.
