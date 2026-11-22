# CLAUDE.md: NewtonBotic Arm (chess-playing robot, simulation)

Project memory for AI coding sessions and developers working on this repo.
Read it before changing anything.

## What this is

A ROS 2 project where the **HELENE 6-DOF arm with a parallel-jaw gripper plays chess against a
human in Gazebo Sim**:
- MoveIt 2 plans every arm motion;
- pieces are grasped by **friction only**;
- python-chess and Stockfish (with adjustable strength) decide the moves;
- a game node keeps the logical board and the simulated board in sync.

Stack: Ubuntu 24.04 · ROS 2 **Jazzy** · Gazebo **Harmonic** (gz sim 8, *not* Classic) ·
gz_ros2_control · MoveIt 2 (KDL, OMPL, Pilz) · python-chess 1.11 · Stockfish 16 (`/usr/games/stockfish`).

## Branches

| Ref | Contents |
|---|---|
| `main` (and tag `reference/ai-build`) | The finished reference build described below |
| `learn/chess-arm` | The owner's **learning rebuild** from `4c829b9`, following `ROADMAP.md`. On that branch, follow `~/LEARNING_MODE.md`: teach, scaffold and review. **Don't write the solutions.** |

## History: what was built after the assembled arm

The owner built the arm up to `d69a6ca` ("Complted module 41 and the urdf and gazebo finally"):
a SolidWorks-exported 6-DOF arm (`Joint0..5`, `Link_1..6`), URDF/xacro, and a Gazebo
launch with an `arm_controller`. Everything after that was built with Claude Code:

| Commit | Work |
|---|---|
| `4c829b9` | Baseline snapshot of the owner's working tree (launch and controllers moved to `robot_bringup`, build artefacts untracked) |
| `411d39c` | Phase 0 audit: `docs/PROJECT_AUDIT.md` (environment, joints, controllers, defects) |
| `58506ef` | Phase 1: fixed the base-frame offset (two offsets were cancelling each other), convex-hull collision meshes, a `tool0` frame, launch fixes. *Later replaced by HELENE.* |
| `4b8456d` | Phases 3–4: `chess_simulation` (board geometry, generated world, world interface), `chess_interfaces`, MoveIt config, reachability and motion checks |
| `10c9624` | Phases 5–7: manipulation action server, chess game node (rules, engine, transactional commit), terminal client, integration scenarios |
| `0ec57d1` | **Swapped the robot to HELENE + gripper** (`helene_description`), regenerated the MoveIt config, tcp-based grasping, a real friction gripper, and removed the old arm files |
| `3ca9150` | Fixed hidden board squares (rendering), added Gazebo screenshots |
| `f960b13` | Startup pick-and-place demo, pick screenshots |

Full detail: `docs/PROJECT_AUDIT.md` (sections 1–9) and `README.md`.

## Packages (`src/`)

| Package | Type | Responsibility |
|---|---|---|
| `helene_description` | ament_cmake | **Vendored, generated** HELENE model: `urdf/helene_description.xacro` (macro `helene_arm`), `materials.xacro`, `meshes/visual` and `meshes/collision` (mm, scaled 0.001). See `VENDORED.md`. **Never edit by hand.** |
| `robot_description` | ament_cmake | Wrapper: `urdf/robot.urdf.xacro` (args `use_gazebo`, `controllers_file`), `arm.ros2_control.xacro`, `arm.gazebo.xacro` (plugin and pad friction), RViz config, `display.launch.py`, `rsp.launch.py` |
| `robot_bringup` | ament_cmake | `config/controllers.yaml` and the launch files: `gazebo`, `sim_moveit`, `chess_sim`, `chess_game` |
| `newtonbotic_moveit_config` | ament_cmake | MoveIt config: `helene.srdf` (groups `arm` (base_link→tcp) and `gripper`; poses home/ready/open/closed; end effector at `tcp`; generated ACM), KDL, joint limits, controllers, `move_group.launch.py`. The robot name inside is `helene`. |
| `chess_interfaces` | ament_cmake | `PieceMove`, `PieceState` msgs · `ExecuteMoves` action · `GetPieceStates`, `ReplacePiece`, `SetPiecePose` (test only), `SubmitMove` srvs |
| `chess_simulation` | ament_python | `config/board.yaml` (**the single source of board and piece geometry**), `board.py` (square ↔ world), `world_gen.py` (generated SDF world), `world_interface.py` (node `chess_world`) |
| `chess_manipulation` | ament_python | `moveit_client.py` (synchronous calls to move_group's services and actions), `geometry.py`, `manipulation_server.py` (`/execute_moves`), `reachability`, `motion_check`, `startup_demo` |
| `chess_game` | ament_python | `game_logic.py` (python-chess → piece moves, verification), `engine.py` (Stockfish or a fallback policy), `game_node.py` (node `chess_game`), `cli.py` (`play`) |
| `robot_control`, `robot_utils`, `robot_interfaces` | — | Empty stubs from the original project |

`tools/`: `integration_scenarios.py` (runs against a live system), `sync_helene_description.sh`, `check_stl.py`.

## Architecture

```
human ──(ros2 run chess_game play)──► /chess_game/submit_move
                                          │  validate (python-chess) → plan piece moves
                                          ▼
                              /execute_moves (action)  ◄── startup_demo (once, after launch)
                       chess_manipulation server: VALIDATE → PRE_GRASP → OPEN → APPROACH → CLOSE
                       → VERIFY_GRASP → LIFT → VERIFY_LIFT → TRANSFER → LOWER → RELEASE → RETREAT
                       → VERIFY_PLACE
                          │ move_group (/move_action, /compute_cartesian_path,
                          │             /execute_trajectory, /compute_ik)
                          ▼
              arm_controller (JTC, joint1–6)  +  gripper_controller (both fingers, /commands)
                          ▼ gz_ros2_control
                       Gazebo Sim ◄──── chess_world (piece poses via gz-transport;
                                         reset / promotion swap via the ros_gz service bridge)
game node: execute → read the whole board from chess_world → compare with python-chess
           → commit only if they match
```

## Commands

```bash
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install && source install/setup.bash

ros2 launch robot_bringup chess_game.launch.py                       # full system (GUI + RViz)
ros2 launch robot_bringup chess_game.launch.py headless:=true rviz:=false
#   startup_demo:=true|false  demo_delay:=5.0  demo_move:=e2e4  demo_return:=true
#   execution_mode:=gripper|teleport
ros2 run chess_game play                                             # play as white

ros2 launch robot_description display.launch.py                      # RViz + sliders
ros2 launch robot_bringup gazebo.launch.py headless:=true            # arm + controllers only
ros2 launch robot_bringup chess_sim.launch.py                        # world + MoveIt, no game

ros2 run chess_manipulation reachability      # IK for all squares and tray slots
ros2 run chess_manipulation motion_check      # MoveIt plan and execute accuracy
python3 tools/integration_scenarios.py        # capture, castling, promotion, failure cases (live system)
colcon test --packages-select chess_simulation chess_game && colcon test-result --verbose
ros2 service call /chess_world/reset std_srvs/srv/Trigger
```

Dependencies not installed by rosdep: `sudo apt install stockfish`, and
`pip install --user --break-system-packages chess` (Ubuntu 24.04 has no `python3-chess` apt package).

## Conventions and facts (verified; keep them consistent)

- **Joints:** `joint1..joint6` (revolute), `finger_r_joint` / `finger_l_joint` (prismatic, 0–0.02 m,
  positive = open). There is **no `<mimic>`**: always command both fingers equally, and the jaw gap is 2 × the value.
- **Zero pose** is an "L" (upper arm vertical, forearm along +X).
  **`ready` = [0, 11, 0.46, 0, −79.46, 0]°** puts the TCP at (0.232, 0, 0.150), pointing down. This is the rest pose.
- **Tool frame `tcp`:** between the finger pads. **+X is the approach direction** and +Y is the jaw axis.
  "Pointing down" = `qz(yaw) · qy(+90°)` (`chess_manipulation/geometry.py`). The pads span the TCP ±16 mm.
- **Gripper:** `JointGroupPositionController` on `/gripper_controller/commands` (`Float64MultiArray [v, v]`).
  - Open 0.012 per finger (24 mm), close target 0.006 (squeezes the 15 mm piece body).
  - "Holding" means the fingers stopped wider than 0.0068.
- **Fingers start at 0.005 m** (`initial_value` in `arm.ros2_control.xacro`). Spawning at exactly
  0 (pads touching, at the joint limit) left `finger_l` stuck in Gazebo until both fingers had been cycled. Keep it.
- **Board** (`chess_simulation/config/board.yaml`):
  - 30 mm squares; centre at world (0.22, 0); yaw +90°, so **rank 8 faces the robot** and the robot plays black;
  - top surface z = 0.010;
  - grasp height 24 mm above the board (the pads grip the 15 mm body, clear of the 22 mm base).

  All 64 squares and all 32 tray slots are reachable top-down. Don't hard-code square coordinates anywhere else.
- **Piece IDs:** `<colour>_<piece>_<start square>` (e.g. `white_pawn_e2`). Promoted pieces get IDs like `white_queen_promo1`.
- **Game transaction:** validate → execute → verify the **whole** observed board → commit, and re-sync piece
  IDs from the simulation. If anything fails, the last committed state is kept.
- **`execution_mode:=teleport` is TEST ONLY:** the arm motions are real, but the piece is moved by `set_pose`.
  The default is `gripper`. Never present teleport results as proof that grasping works.

## Gotchas learned the hard way

- `helene_description.xacro` and the meshes are **generated** upstream (private repo
  `ShubhamManglaw/helene_description`). Report problems instead of patching them. Update with
  `tools/sync_helene_description.sh <checkout>`.
- The ros_gz bridge **drops entity names** when converting `Pose_V`, so `world_interface` reads poses
  with gz-transport Python directly. gz-transport's Python `request()` holds the GIL and stalls that
  subscription, so spawn, delete and set-pose go through the **ros_gz service bridge** instead.
- `package.xml` comments must not contain `--` (invalid XML). colcon then silently treats the package
  as plain Python and drops its ROS environment hooks.
- Don't put `chess` in `setup.py` `install_requires`: colcon records it as a missing package and skips the package.
- Gazebo's GUI aborts with no display. Use `headless:=true` on servers or CI.
  For screenshots, add camera sensors plus the Sensors system and run `gz sim -s --headless-rendering`, then subscribe
  to the camera image topic. (The `<save>` element didn't write files.)
- With `gz_ros2_control` position interfaces the joints track almost perfectly. That's fine for sim,
  but much better than real servos will do.
- Agent tooling: `pgrep -f '<pattern>'` / `pkill -f` match the calling shell if the pattern
  appears in the same command line. Kill by PID or run guard scripts as separate commands. Make
  sure no earlier `gz sim` is still running before launching (duplicate controller managers cause
  "controller already loaded").

## Known limitations / next ideas

- Simulation only. A forced empty-grasp failure is implemented but has not been triggered in a test.
- Vision is not implemented yet: the human enters moves by command. It's planned on `learn/chess-arm` (Phase 5: OpenCV).
- An adjustable rating exists only as Stockfish `Skill Level` / `think_time` in `chess_game/config/game.yaml`.
  A rating-to-strength mapping (`UCI_Elo`) is planned in the learning roadmap.
- Effort and velocity limits are CAD estimates. The Gazebo entity is still named `NewtonBotic_Arm`.
  The old TF snapshot PDFs and `stl_files/` remain in the repo root.
