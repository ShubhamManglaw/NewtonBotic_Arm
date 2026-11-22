# CHANGES.md: everything Claude changed after the assembled arm

This file records **every change made by Claude Code** after your last own commit:

> `d69a6ca` "Complted module 41 and the urdf and gazebo finally": the SolidWorks arm
> (`Joint0..5`, `Link_1..6`) with a URDF and a Gazebo launch.

**Size of the work** (source, docs and tools; meshes and screenshots excluded): 87 files changed,
about **4,480 lines added** and 710 removed, across 9 commits.

For each commit you'll find:
- **Goal:** what the commit was for;
- **Files:** what changed in each file, and *why*;
- **Bugs found:** what went wrong and how it was fixed;
- **Verified by:** how it was proven to work.

### How to inspect any change yourself
```bash
git log --oneline d69a6ca..main                  # all commits after your arm
git show --stat <commit>                         # files changed in one commit
git show <commit> -- <path>                      # the exact diff for one file
git diff d69a6ca main -- src/robot_bringup       # total change in one package
git checkout reference/ai-build -- <path>        # bring a reference file into your branch (last resort!)
```

### Commits at a glance
| # | Commit | Title | Main result |
|---|---|---|---|
| 0 | `4c829b9` | Baseline | **Your own uncommitted work**, committed as-is so there was a clean starting point |
| 1 | `411d39c` | Phase 0 audit | `docs/PROJECT_AUDIT.md`: the state of the project, its defects, and the plan |
| 2 | `58506ef` | Phase 1 | Old arm fixed: base frame, collision meshes, `tool0`, launch fixes |
| 3 | `4b8456d` | Phases 3–4 | Chess world, ROS interfaces, MoveIt config, motion tools |
| 4 | `10c9624` | Phases 5–7 | Manipulation server, chess game node, end-to-end game |
| 5 | `0ec57d1` | HELENE swap | New arm with gripper, real friction grasping, old arm removed |
| 6 | `3ca9150` | Board fix | Chessboard squares were invisible; screenshots added |
| 7 | `f960b13` | Startup demo | Automatic pick-and-place after launch; pick screenshots |
| 8 | `705bd78` | CLAUDE.md | Project memory for AI sessions |

---

## 0. `4c829b9`: Baseline (your work, not Claude's)

**Goal:** you had a large set of uncommitted changes (Gazebo launch and controllers moved from
`robot_description` to `robot_bringup`, `install/` and `build/` removed from git, a new
`.gitignore`, a `robot.urdf.xacro`). Claude committed them **unchanged** so every later change
has a clean "before".

**Files:** the launch and controllers moved to `robot_bringup/`; `check_stl.py` moved to `tools/`;
`robot.urdf.xacro` added; `.gitignore` rewritten for ROS 2 / colcon; about 700 build-artefact files untracked.

---

## 1. `411d39c`: Phase 0, project audit

**Goal:** understand the project *before* changing it: what builds, what runs, and what's broken.

**Files**
- `docs/PROJECT_AUDIT.md` (**new**):
  - the environment (Jazzy, Gazebo Harmonic 8.15, MoveIt installed, no python-chess or Stockfish yet);
  - the package table; the joint table (axes and limits); forward kinematics at zero;
  - the controllers and the launch command;
  - a list of defects.

**Defects it found**
1. **Base frame offset.** The base mesh sat about 1.5 m away from its own frame, and two opposite offsets
   (`world_to_base` and `Joint0`) cancelled each other out. The base inertia was also rotated 90°.
2. **Huge meshes.** About 917k triangles, also used for collision, which makes physics slow.
3. **A skewed CAD zero pose** (consistent, so harmless).
4. **`display.launch.py` crashed** with a NameError on undefined variables.
5. **No headless option.** The Gazebo GUI crashed with no display and took the server down with it.
6. **Repo clutter:** a `.save` file, duplicate URDFs, an empty README.

**Verified by:** the build passed (5 packages). Headless Gazebo showed both controllers active,
a test trajectory returned SUCCEEDED, and TF matched the computed FK.

---

## 2. `58506ef`: Phase 1, stabilising the robot description (old arm)

**Goal:** a clean, fast, correct robot model before adding anything on top.
*(This arm was later replaced by HELENE in commit 5, but the lessons still apply.)*

**Files**
- `robot_description/urdf/newtonbotic_arm.xacro` (**new**): links and joints as a macro.
  - A `cad_link` macro removed repeated code.
  - **Base re-origined:** `world_to_base` became the identity, the mesh offset moved into the visual
    origin, and `Joint0` went to z = 0.04051. Every downstream frame stayed numerically identical.
  - The base inertia was re-expressed in the mesh frame.
  - Added a `tool0` flange frame (+Z out of the flange).
- `robot_description/urdf/arm.ros2_control.xacro` (**new**): position command, plus position and velocity state, for 6 joints.
- `robot_description/urdf/arm.gazebo.xacro` (**new**): the `gz_ros2_control` plugin.
- `robot_description/urdf/robot.urdf.xacro`: rewritten as the entry point (args `use_gazebo`, `controllers_file`, `use_gripper`).
- `robot_description/meshes/collision/*.stl` (**new**): convex hulls, about 5k triangles in total instead of 917k.
- `tools/make_collision_meshes.py` (**new**): regenerates those hulls (trimesh).
- `robot_bringup/launch/gazebo.launch.py`:
  - `headless`, `world` and spawn-position arguments;
  - `robot_description` built with `Command(xacro …)`;
  - `GZ_SIM_RESOURCE_PATH` set;
  - spawner timeouts.
- `robot_description/launch/display.launch.py` and `rsp.launch.py`: NameError fixed; they now use xacro.
- **Removed:** `robot.urdf`, `robot.urdf.backup`, `gazebo.launch.py.save` (duplicates, still in history).

**Verified by:** FK before and after was identical for every link. TF in Gazebo matched FK exactly.
A strongly bent pose rendered with no detached links.

---

## 3. `4b8456d`: Phases 3–4, chess world, interfaces, MoveIt

**Goal:** a simulated chessboard with pieces, typed ROS interfaces, and MoveIt planning.

### `chess_interfaces` (**new** package, typed messages between nodes)
| File | Purpose |
|---|---|
| `msg/PieceMove.msg` | One physical relocation: `piece_id`, from, to, operation `MOVE` / `REMOVE` (to the tray) / `REPLACE` (promotion) |
| `msg/PieceState.msg` | A piece's pose, square, `upright` flag, and whether it's in the graveyard tray |
| `action/ExecuteMoves.action` | A list of `PieceMove`s. The result gives success, the stage that failed, a failure category and a message. Feedback gives the current stage. |
| `srv/GetPieceStates.srv` | Read all pieces from the simulation |
| `srv/ReplacePiece.srv` | Swap a pawn's model for a promoted piece |
| `srv/SubmitMove.srv` | A human move in, the robot's reply out (used by the game node) |

### `chess_simulation` (**new** package)
- `config/board.yaml`: **the single source of truth** for board and piece geometry: square size,
  board pose, piece sizes and masses, friction, capture-tray layout.
- `chess_simulation/board.py`: pure Python, no ROS.
  - `parse_square`, `square_to_board`, `board_to_world`, `world_to_square`;
  - `graveyard_world`, the tray slot for each captured piece;
  - `starting_pieces`, which gives stable IDs like `white_pawn_e2`.
- `chess_simulation/world_gen.py`: generates the Gazebo world SDF (board, trays, 32 pieces, physics
  plugins) from `board.yaml`, so coordinates are never typed in by hand.
- `chess_simulation/world_interface.py`: node `chess_world`.
  - Reads piece poses, and offers the services `get_piece_states`, `reset` and `replace_piece`.
  - Publishes the static TF `world → chessboard_frame`.
- `test/test_board.py`: 6 tests (round trips, spacing, orientation, tray slots, starting pieces).

### `newtonbotic_moveit_config` (**new** package)
- `config/newtonbotic_arm.srdf`:
  - planning group `arm` (`base_link → tool0`);
  - a `home` pose;
  - an allowed-collision matrix **generated** with `collisions_updater` (20,000 random samples).
- `config/kinematics.yaml` (KDL IK), `joint_limits.yaml` (adds acceleration limits, which are needed for
  time parameterisation), `moveit_controllers.yaml` (maps to `arm_controller`), `pilz_cartesian_limits.yaml`.
- `launch/moveit_config.py`: one shared `MoveItConfigsBuilder`. `launch/move_group.launch.py`: `move_group` plus RViz.

### `chess_manipulation` (**new** package, first part)
- `moveit_client.py`: talks to `move_group` directly (IK, joint-goal planning, Cartesian paths,
  execution, planning-scene objects, attach and detach), because `moveit_py` isn't installed.
- `geometry.py`: quaternion helpers for a top-down tool pose.
- `reachability.py`: IK checks for every square and tray slot. `motion_check.py`: plans and executes to squares and measures the error with TF.

### `robot_bringup`
- `launch/sim_moveit.launch.py` (**new**): Gazebo plus MoveIt (MoveIt starts 8 s later).
- `launch/chess_sim.launch.py` (**new**): generates the world, plus Gazebo, MoveIt, the service bridge and the world interface.

**Bugs found**
- **SDF rejected the pieces:** collision and visual elements had the same names. Renamed to `*_col`.
- **Reset took more than 30 s:** gz-transport's Python `request()` holds the GIL, which stalled the pose
  subscription, so every call ran to its timeout. Fix: send spawn, delete and set-pose through the
  **ros_gz service bridge**, and keep gz-transport only for reading poses. (The ROS bridge drops entity names, so poses can't come through it.)
- **After a promotion, reset lost a piece:** the removed pawn was never put back in the registry. Fixed.
- **The board was reachable but tight:** the board moved 15 mm closer to the robot, and the tray rows moved into the well-reached area.

**Verified by:** all 64 squares and 32 tray slots reachable. MoveIt plan-and-execute to 6 squares
landed within ≤0.4 mm. Reset, the promotion swap and a reset after promotion all passed.

---

## 4. `10c9624`: Phases 5–7, manipulation server, game node, full game

**Goal:** turn chess moves into verified physical robot actions, and play a full game.

### `chess_manipulation/manipulation_server.py` (**new**, action `/execute_moves`)
- Each piece move goes through explicit stages:
  `VALIDATE → PRE_GRASP → OPEN → APPROACH → CLOSE → VERIFY_GRASP → LIFT → VERIFY_LIFT →
  TRANSFER → LOWER → RELEASE → RETREAT → VERIFY_PLACE`, then `REST`.
- Free-space moves use OMPL. Vertical moves and the level transfer use Cartesian paths.
- The planning scene holds the board, the trays and every piece. The held piece is attached to the tool.
- The jaws close along the board diagonal, because neighbouring pieces are 42 mm away there instead of 30 mm.
- Captured pieces go to the next free tray slot. Promotion calls `replace_piece`.
- Failures return a category: `INVALID`, `PLANNING`, `CONTROLLER`, `GRASP`, `VERIFY`, `WORLD` or `CANCELLED`. Afterwards the arm tries to back away to the rest pose.
- `execution_mode: teleport`: a **test-only** mode for when no gripper existed yet. The arm motions are real, but the piece is moved by `set_pose`.
- `config/manipulation.yaml`: heights, yaw offsets, speed scaling, gripper settings.

### `chess_game` (**new** package)
- `game_logic.py` (pure Python):
  - `ChessGame` parses UCI or SAN moves and turns a chess move into physical steps
    (capture = REMOVE + MOVE; en passant removes the pawn beside it; castling = two MOVEs; promotion = MOVE + REPLACE).
  - `expected_after` and `compare` check the observed board.
  - `commit` re-syncs piece IDs from the simulation.
- `engine.py`: Stockfish (skill level and think time), or a documented fallback policy
  (mate if available, else the best capture, else a check, else a random move).
- `game_node.py`: node `chess_game`.
  - **Transaction:** validate → execute → compare the *whole* observed board → commit. If anything fails, the state is left unchanged.
  - Services `submit_move`, `new_game` and `state`; topic `fen`.
- `cli.py` (`ros2 run chess_game play`) and `config/game.yaml`.
- `test/test_game_logic.py`: 16 tests (illegal moves, captures, en passant, both castles, promotion with capture, checkmate status, fallback policy).

### Other files
- `chess_interfaces/srv/SetPiecePose.srv` (**new**) and a `set_piece_pose` service in `world_interface.py`: teleport, used only by the test mode.
- `robot_bringup/launch/chess_game.launch.py` (**new**): the full system in one command.
- `tools/integration_scenarios.py` (**new**): 8 scenarios against the running system.
- `README.md`: written from scratch (setup, running, architecture, board convention).

**Bugs found**
- **`chess_game` was invisible to ROS** ("package not found"). A comment in `package.xml` contained
  `--`, which is invalid XML, so colcon treated it as a plain Python package. Also, `chess` in
  `install_requires` made colcon skip it. Both fixed.
- **Leftover simulations interfered with new runs** (two worlds, two interface nodes). Old processes are now cleaned up before each test.

**Verified by:** 22 unit tests passed. The human played `e2e4`, then the robot executed, verified and committed it and replied `h5`.
8/8 integration scenarios passed *(in teleport mode, since there was no gripper yet)*.

---

## 5. `0ec57d1`: robot swapped to HELENE with the parallel-jaw gripper

**Goal:** replace the old arm with your HELENE model (generated from Fusion, with a gripper) and grasp by real friction.

### New and replaced files
- `src/helene_description/` (**new**, vendored): `urdf/helene_description.xacro` and `materials.xacro`,
  plus `meshes/visual` and `meshes/collision` (25 files), copied **unchanged** from commit `bf83584`
  of `ShubhamManglaw/helene_description`. Also a minimal `package.xml` / `CMakeLists.txt`, and
  `VENDORED.md` explaining what was and wasn't copied.
- `tools/sync_helene_description.sh` (**new**): re-copies the generated files after the model is regenerated.
- `robot_description/urdf/robot.urdf.xacro`: now only instantiates `<xacro:helene_arm parent="world"/>` and adds the project's own control files.
- `robot_description/urdf/arm.ros2_control.xacro`:
  - joint1–6 plus **both fingers** (no `<mimic>`; always command them equally, jaw gap = 2 × value);
  - the **fingers start at 0.005 m** (see "Bugs found").
- `robot_description/urdf/arm.gazebo.xacro`: high-friction, stiff finger-pad contacts.
- `robot_bringup/config/controllers.yaml`: `arm_controller` on joint1–6, plus a **new** `gripper_controller` (`JointGroupPositionController` on both fingers).
- `newtonbotic_moveit_config/config/helene.srdf` (replaces `newtonbotic_arm.srdf`):
  - groups `arm` (`base_link → tcp`) and `gripper`;
  - poses `home`, `ready`, `open` and `closed`;
  - an end effector at `tcp`;
  - a **regenerated** collision matrix.
- `joint_limits.yaml` (velocities taken from the URDF), `moveit_controllers.yaml` (new joint names), MoveIt launch and builder (robot name `helene`, no more `use_gripper`).
- All bringup and description launch files: the `use_gripper` argument removed, the gripper spawner added.

### Chess layer adapted
- `geometry.py`: the tool frame is now `tcp`, with **+X as the approach direction** ("down" = `qz(yaw) · qy(+90°)`).
- `moveit_client.py`, `reachability.py`, `motion_check.py`: new joint names, and the tcp frame as the end effector.
- `manipulation_server.py`:
  - the gripper is driven over `/gripper_controller/commands` (both fingers equal), waiting until the fingers stop moving;
  - a **grasp check** (fingers stopped wider than 13.6 mm means something is held);
  - a symmetry check, new touch links, and real gripping as the default mode.
- `config/manipulation.yaml`: open 12 mm / close 6 mm per finger, the `ready` rest pose, `execution_mode: gripper`.
- `chess_simulation/config/board.yaml`: board moved in front of the arm along +X (centre (0.22, 0), yaw +90°); **grasp height 24 mm**.

### Removed
- The old arm xacro, its 7 CAD meshes and the collision hulls, and `tools/make_collision_meshes.py`. They remain in git history.

**Bugs found**
- **`finger_l` stuck in Gazebo.** When both fingers spawned exactly at 0 (pads touching, at the joint
  limit), `finger_l` ignored commands until both fingers had been cycled once. Reproduced 3 times.
  Flipping the axis in a scratch copy did *not* fix it; starting both fingers at 0.005 m did.
  The generated model was **not** edited.
- **Grasping the base rim.** At a 20 mm grasp height the fingertips pinched the 22 mm base disc
  (the fingers stopped at a 22 mm gap). At 24 mm they grip the 15 mm body: the fingers stop at exactly 15.0 mm.

**Verified by:**
- `xacro` and `check_urdf` pass.
- In Gazebo: 3 controllers active, `ready` puts the TCP at (0.232, 0.000, 0.150), and the gripper reaches 40.0 mm and 0.0 mm.
- All 64 squares and tray slots are reachable. MoveIt plan-and-execute lands within ≤0.7 mm.
- **8/8 scenarios and a 6-move game against Stockfish with real friction grasps** (including a robot capture). 22/22 unit tests.

---

## 6. `3ca9150`: hidden chessboard squares fixed, screenshots added

- `chess_simulation/world_gen.py`: the 64 square tiles sat *inside* the board's frame (tile tops at
  6 mm, frame top at 9 mm), so the board looked plain brown. The tiles now sit just above the frame.
  Rendering only; the collision geometry is unchanged.
- `docs/images/gazebo_helene_ready_{oblique,side}.png` (**new**): rendered without a window
  (camera sensors plus `gz sim --headless-rendering`). `README.md` shows the first one.

---

## 7. `f960b13`: startup pick-and-place demo

- `chess_manipulation/startup_demo.py` (**new**):
  - waits until `/execute_moves` and `chess_world` are ready, then waits `delay` seconds;
  - picks the piece on the first square of `move` with the real gripper and places it on the second;
  - then (`return_piece`) carries it back, so the game state stays correct.
- `robot_bringup/launch/chess_game.launch.py`: the arguments `startup_demo` (default true),
  `demo_delay` (5.0), `demo_move` (e2e4) and `demo_return` (true).
- `chess_manipulation/setup.py`: the `startup_demo` entry point. `README.md`: usage.
- `docs/images/gazebo_pick_lifted.png` and `gazebo_pick_sequence.png` (**new**): the pick, stage by stage.

**Verified by:** the full launch showed e2 → e4 and back, both verified with real grasps. A game played afterwards (`d2d4`, Stockfish replied `a6`) was still in sync.

---

## 8. `705bd78`: CLAUDE.md

- `CLAUDE.md` (**new**): project memory for future AI sessions. It covers:
  - the packages and the architecture;
  - commands;
  - the conventions to keep consistent;
  - the bugs above as "gotchas";
  - the branch roles (`main` = reference, `learn/chess-arm` = your learning rebuild).

---

## Outside this branch

- `~/LEARNING_MODE.md` (your home folder, not in the repo): instructions that make the AI mentor you instead of coding everything.
- Branch `learn/chess-arm`: your rebuild from `4c829b9`, with `LEARNING_LOG.md` and `ROADMAP.md`.

## What to study first (if you want to understand this build)

1. **`chess_simulation/config/board.yaml` + `board.py`:** the geometry everything else relies on.
2. **`chess_game/game_logic.py` + its tests:** how chess moves become physical steps.
3. **`chess_manipulation/manipulation_server.py`, `_pick()` and `_place()`:** the grasp sequence.
4. **`robot_description/urdf/*.xacro` + `robot_bringup/config/controllers.yaml`:** how HELENE is controlled.
5. **`newtonbotic_moveit_config/config/helene.srdf`:** what MoveIt knows about the robot.
