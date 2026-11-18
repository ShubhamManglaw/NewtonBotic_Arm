# NewtonBotic Arm: Simulated Chess-Playing Robot

A 6-DOF arm (from SolidWorks CAD) that plays chess against a human in Gazebo Sim, with MoveIt 2 for motion planning.

Stack: ROS 2 Jazzy · Gazebo Harmonic (gz sim 8) · ros2_control · MoveIt 2 · python-chess (+ Stockfish, optional)

## Status

| Phase | State |
|---|---|
| 0 Audit | Done. See [docs/PROJECT_AUDIT.md](docs/PROJECT_AUDIT.md) |
| 1 Robot description | Done. Base frame fixed, collision hulls, `tool0` flange |
| 2 Gripper | **Waiting for gripper CAD** (see "Integrating the gripper") |
| 3 Chess world | Done. Generated board and 32 pieces, reset, promotion swap |
| 4 MoveIt 2 | Done for the arm. Plan and execute verified to ≤0.4 mm |
| 5 Pick and place | Pipeline done. Real grasping needs the gripper; runs in `teleport` test mode for now |
| 6 Game controller | Done. Validates and verifies before commit; unit tested |
| 7 End-to-end loop | Works in `teleport` test mode |
| 8 Special moves | Captures, castling, en passant and promotion are planned and tested in logic and in sim (teleport) |

> **`teleport` mode is a test mode.**
> - The arm performs every real motion: pre-grasp, approach, lift, transfer, lower and retreat.
> - The piece itself is moved by Gazebo `set_pose`. Nothing grips it.
> - This mode proves the planning, sequencing, verification and game logic. It does **not** prove that grasping works.
> - Use `execution_mode:=gripper` once the gripper is integrated.

## Setup

```bash
sudo apt install stockfish                      # optional; without it a simple fallback policy plays
pip install --user --break-system-packages chess   # python-chess (no apt package on Ubuntu 24.04)

cd ~/NewtonBotic_Arm
source /opt/ros/jazzy/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

## Run

```bash
# Full system: Gazebo + arm + MoveIt + manipulation + game (add headless:=true rviz:=false for no GUI)
ros2 launch robot_bringup chess_game.launch.py

# In a second terminal: play as white
ros2 run chess_game play
#   your move> e4        (UCI or SAN; also: board, new, quit)
```

Other entry points:

| Command | Purpose |
|---|---|
| `ros2 launch robot_description display.launch.py` | RViz + joint sliders, no simulation |
| `ros2 launch robot_bringup gazebo.launch.py headless:=true` | Arm and controllers in an empty world |
| `ros2 launch robot_bringup sim_moveit.launch.py` | The above plus MoveIt |
| `ros2 launch robot_bringup chess_sim.launch.py` | Chess world plus MoveIt, no game |
| `ros2 run chess_manipulation reachability --ros-args -p tcp_offset:=0.11` | IK reachability of every square |
| `ros2 run chess_manipulation motion_check` | MoveIt plan/execute accuracy test |
| `python3 tools/integration_scenarios.py` | Capture, castling, promotion and failure scenarios |
| `ros2 service call /chess_world/reset std_srvs/srv/Trigger` | Restore the start position |

Tests: `colcon test --packages-select chess_simulation chess_game && colcon test-result --verbose`

## Architecture

```
chess_game (rules, engine, commit)            chess_simulation (world)
   │  /execute_moves (action)                    world_interface: /chess_world/{get_piece_states,
   ▼                                               reset, replace_piece, set_piece_pose}
chess_manipulation (pick/place stages) ──────►  board.py + config/board.yaml  ◄── single source
   │  move_group services/actions                  of square ↔ world geometry
   ▼
newtonbotic_moveit_config ──► arm_controller (JTC) ──► gz_ros2_control ──► Gazebo
robot_description (URDF/Xacro)     robot_bringup (launch, controllers.yaml)
chess_interfaces (PieceMove, PieceState, ExecuteMoves, SubmitMove, …)
```

- **Game.** Every move, the human's or the robot's, runs as one transaction:
  1. Validate the move with python-chess.
  2. Plan the piece moves (REMOVE, MOVE, REPLACE).
  3. Execute them.
  4. Compare the **whole** observed board against the expected one.
  5. Commit.

  If anything fails, the last committed state is kept.
- **Manipulation.** Each piece move runs these stages: VALIDATE → PRE_GRASP → OPEN → APPROACH → CLOSE → VERIFY_GRASP → LIFT → VERIFY_LIFT → TRANSFER → LOWER → RELEASE → RETREAT → VERIFY_PLACE.
  - A failure returns its stage, a category (INVALID, PLANNING, CONTROLLER, GRASP, RELEASE, VERIFY, WORLD or CANCELLED) and a message.
  - Free-space motion uses OMPL. Vertical motion and level transfer use Cartesian paths.
  - The board, the trays and every piece are in the MoveIt planning scene, and a held piece is attached to `tool0`.

### Board convention (`chess_simulation/config/board.yaml`)

- `chessboard_frame`:
  - **Origin:** the centre of the board's top surface.
  - **+X:** toward the h-file.
  - **+Y:** toward rank 8.
  - **Square centres:** `((f-3.5)s, (r-3.5)s)`.
- The squares are 30 mm, scaled down to the arm's reach.
- The board centre is at world (0, 0.22). It is rotated 180°, so **rank 8 faces the robot**: the robot plays black and the human sits at rank 1.
- Captured pieces go to two 2×8 trays beside the board.
- Piece IDs are stable, e.g. `white_pawn_e2`. Promoted pieces get IDs like `white_queen_promo1`.

## Integrating the gripper (Phase 2)

What's needed from the gripper CAD: STL meshes for the palm and fingers, plus a URDF export.

1. Add `robot_description/urdf/gripper.xacro` defining `<xacro:macro name="gripper" params="parent">`, mounted on `tool0`.
   - `tool0` is the Link_6 flange face, with +Z pointing out of the flange.
   - The fingers need real collision geometry and high friction, because grasping is pure friction.
2. Add a `gripper_controller` (`position_controllers/GripperActionController`) to `robot_bringup/config/controllers.yaml`, and the finger joint to `arm.ros2_control.xacro`.
3. In the SRDF, add a `gripper` group and an end-effector, and regenerate the ACM with `collisions_updater`.
4. In `chess_manipulation/config/manipulation.yaml`, set:
   - `tcp_offset`: the distance from `tool0` to the fingertip grasp centre;
   - `gripper.open_position`, `close_position` and `holding_min_position`.

   Then run with `execution_mode:=gripper use_gripper:=true`.
5. Run `reachability` with the real `tcp_offset`. All 64 squares are reachable up to about 0.14 m; a1/h1 fail at 0.17 m. If needed, move the board via `board.pose.y`.

Piece grasp body: a Ø15 mm cylinder whose grasp centre is 16 mm above the board. Pieces weigh 20 g and are spaced 30 mm apart; diagonal neighbours are 42 mm apart, and the gripper approaches along the diagonal. The fingers must open wider than 15 mm and fit in the gaps between neighbouring pieces.
