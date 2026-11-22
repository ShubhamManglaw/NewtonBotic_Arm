# Roadmap: chess-playing robot arm (learning edition)

**Goal:** a HELENE arm with its gripper plays chess one-on-one against a person. The person
moves a piece, OpenCV detects the move from camera images, an engine with an **adjustable
rating** replies, and the arm moves the piece. Built in Gazebo first, then on a real arm and board.

## How this roadmap works

The project is split into **8 phases → steps → lessons**. A lesson is one small, finishable
piece of work, usually 1–3 hours. Every lesson has the same parts:

| Part | Meaning |
|---|---|
| 🎯 **Learn** | The concept or skill this lesson teaches |
| 📖 **Explain** | A short explanation to read before you start (the AI expands on it if you ask) |
| 🛠️ **Do** | The task. **You write the code.** |
| ✅ **Test** | How you prove it works. Don't move on until it passes. |
| 🤝 **AI helps** | What the AI does in this lesson (explain, scaffold, review, debug hints) |

**Help level per phase** (from your comfort ratings in `LEARNING_LOG.md`):
- 🟢 **Light**: topics you know well (ROS 2, URDF, ros2_control, Gazebo, hardware). Small steps, a short
  refresher, you write it, the AI reviews.
- 🟡 **Guided**: concept OK, syntax rusty (MoveIt, grasping). An API cheat-sheet and a skeleton with
  TODOs. You write it, the AI reviews.
- 🔴 **Full teaching**: new topics (chess engines, OpenCV, C++). A concept lesson first, a tiny
  example, a detailed skeleton, quick understanding checks, then you write it.

**Rules**
- After each lesson, tick its box, add a short entry to [LEARNING_LOG.md](LEARNING_LOG.md)
  (the concept, bugs as symptom → cause → how to detect, open questions), then **commit and push**.
- Stuck? Ask for a `hint`, then a `bigger hint`, then `show me`. The reference solution (tag
  `reference/ai-build`) comes last.
- Time estimates assume about 10 hours a week. They're a guide, not a deadline.

| Phase | Topic | Help | Lessons | Estimate | Status |
|---|---|---|---|---|---|
| 1 | HELENE in your workspace | 🟢 | 11 | 1 week | ☐ |
| 2 | MoveIt 2 | 🟡 | 13 | 2 weeks | ☐ |
| 3 | Chess engine + adjustable rating | 🔴 | 10 | 1 week | ☐ |
| 4 | Chess world + camera in Gazebo | 🟢 / 🔴 camera | 8 | 1 week | ☐ |
| 5 | Vision with OpenCV | 🔴 | 16 | 3 weeks | ☐ |
| 6 | Pick and place | 🟡 | 9 | 2 weeks | ☐ |
| 7 | Full game loop | 🟡 | 7 | 1–2 weeks | ☐ |
| 8 | Real world: camera, board, arm | 🟢 hardware / 🔴 C++ | 11 | 4–6 weeks | ☐ |

---

# Phase 1: HELENE in your workspace 🟢

**Why:** everything else builds on a robot that loads, simulates and responds correctly.
**At the end you can:** show HELENE in RViz and Gazebo, with controllers that move the arm and gripper.

## Step 1.1: Bring in the model

- [ ] **Lesson 1.1.1: Read the spec and draw the robot**
  - 🎯 **Learn:** reading a robot description spec before touching code.
  - 📖 **Explain:** `helene_description/AGENTS.md` lists the kinematic chain, joint names, axes,
    limits, the zero pose ("L" shape) and the `tcp` frame. Engineers read this first so they don't
    guess names or frames later.
  - 🛠️ **Do:** clone the repo (`gh repo clone ShubhamManglaw/helene_description`) and read
    `AGENTS.md`. On paper, draw the tree `world → … → tcp`, with each joint's axis and limits.
  - ✅ **Test:** without looking, you can say the parent and child of every joint, which joints are
    prismatic, and where `tcp` sits relative to the fingers.
  - 🤝 **AI helps:** answers questions and checks your drawing.

- [ ] **Lesson 1.1.2: Choose how to bring in the package**
  - 🎯 **Learn:** managing a dependency that lives in another repo (submodule vs copy vs overlay workspace).
  - 📖 **Explain:** some files in that repo are **generated** from Fusion and must never be edited by
    hand. The repo also contains things your project already has (launch files, controllers, a world).
    Whatever you choose decides how others clone your repo and how model updates arrive.
  - 🛠️ **Do:** compare A) a git submodule, B) copying in only the model files, C) a separate overlay
    workspace. Write your choice and 2–3 reasons in `LEARNING_LOG.md`.
  - ✅ **Test:** your reasoning covers: the private repo, the size of `fusion/`, duplicate launch and
    config files, how updates arrive, and the `package://` mesh paths.
  - 🤝 **AI helps:** reviews your reasoning and points out anything you missed.

- [ ] **Lesson 1.1.3: Create the package in your workspace**
  - 🎯 **Learn:** what an `ament_cmake` package needs to install data files (`share/<pkg>/…`).
  - 📖 **Explain:** `package://helene_description/meshes/…` only resolves if a package with exactly
    that name installs a `meshes/` folder.
  - 🛠️ **Do:** set up the package using the method you chose. Install `urdf/` and `meshes/`.
  - ✅ **Test:**
    - `colcon build` is clean;
    - `ros2 pkg prefix helene_description` prints a path;
    - the meshes exist under `install/helene_description/share/helene_description/meshes/`.
  - 🤝 **AI helps:** may write `package.xml` / `CMakeLists.txt` with you (that's routine setup work), and explains each line.

- [ ] **Lesson 1.1.4: A top-level xacro that builds the robot**
  - 🎯 **Learn:** xacro macros vs instances, `xacro:include`, `$(find pkg)`.
  - 📖 **Explain:** `helene_description.xacro` only *defines* `<xacro:helene_arm parent="…"/>`. Something
    has to create a `world` link and *call* the macro.
  - 🛠️ **Do:** rewrite `robot_description/urdf/robot.urdf.xacro` so it includes `materials.xacro` and
    the HELENE macro and instantiates it on `world`.
  - ✅ **Test:** `xacro robot.urdf.xacro > /tmp/helene.urdf` runs, and `check_urdf /tmp/helene.urdf`
    shows `world → base_link → link1 … link6 → gripper_base → finger_r, finger_l, tcp`.
  - 🤝 **AI helps:** reviews your xacro.

- [ ] **Lesson 1.1.5: Show it in RViz (and fix a bug)**
  - 🎯 **Learn:** robot_state_publisher, joint_state_publisher_gui, and reading Python tracebacks from launch files.
  - 📖 **Explain:** your current `display.launch.py` has a bug. Run it first and read the error.
  - 🛠️ **Do:** fix the launch file, display HELENE, and move every slider.
  - ✅ **Test:** all meshes are placed correctly, each slider moves the right part, and the finger
    sliders open the jaws symmetrically.
  - 🤝 **AI helps:** debugging hints on the hint ladder, only if you ask.

## Step 1.2: Run it in Gazebo with ros2_control

- [ ] **Lesson 1.2.1: The ros2_control tag**
  - 🎯 **Learn:** command vs state interfaces, and one hardware "system" for many joints.
  - 📖 **Explain:** the gripper has **two commanded fingers and no `<mimic>`**. You always send both
    the same value, and the jaw gap is 2 × that value. This works the same in Gazebo and on real hardware.
  - 🛠️ **Do:** write `arm.ros2_control.xacro` for joint1–6 plus both fingers (position command;
    position and velocity state), using `gz_ros2_control/GazeboSimSystem`.
  - ✅ **Test:** the expanded URDF contains one `<ros2_control>` block with 8 joints.
  - 🤝 **AI helps:** reviews it.

- [ ] **Lesson 1.2.2: The Gazebo plugin and finger friction**
  - 🎯 **Learn:** how URDF `<gazebo>` tags become SDF (inspect with `gz sdf -p file.urdf`).
  - 📖 **Explain:** grasping relies on friction alone, so the finger pads need high friction and stiff contact.
  - 🛠️ **Do:** add the `gz_ros2_control-system` plugin (pointing at your controllers YAML) and
    `<gazebo reference="finger_r/l">` contact properties.
  - ✅ **Test:** in the output of `gz sdf -p`, the finger collisions show your friction values.
  - 🤝 **AI helps:** explains the contact parameters (mu, kp, kd).

- [ ] **Lesson 1.2.3: The controllers YAML**
  - 🎯 **Learn:** JointTrajectoryController vs JointGroupPositionController, and when to use each.
  - 🛠️ **Do:** in `robot_bringup/config/controllers.yaml`, configure `joint_state_broadcaster`,
    `arm_controller` (joint1–6) and `gripper_controller` (both fingers).
  - ✅ **Test:** the YAML parses, and the joint names match the URDF exactly.
  - 🤝 **AI helps:** a syntax refresher.

- [ ] **Lesson 1.2.4: The Gazebo launch file**
  - 🎯 **Learn:** spawning a robot, starting controllers in the right order, `GZ_SIM_RESOURCE_PATH`, running Gazebo headless.
  - 🛠️ **Do:** update `gazebo.launch.py`: start the world, spawn the robot from `robot_description`,
    then start the controllers. Add a `headless` argument.
  - ✅ **Test:** `ros2 control list_controllers` shows 3 controllers `active`, with no missing-mesh errors.
  - 🤝 **AI helps:** reviews the order in which things start.

- [ ] **Lesson 1.2.5: Command the robot from the terminal (and a debugging challenge)**
  - 🎯 **Learn:** testing controllers from the CLI, checking positions with TF, and debugging a simulator.
  - 🛠️ **Do:**
    - send the `ready` pose `[0, 11, 0.46, 0, -79.46, 0]°` with
      `ros2 action send_goal /arm_controller/follow_joint_trajectory …`;
    - open and close the gripper with `ros2 topic pub /gripper_controller/commands …`.
  - ✅ **Test:**
    - `tf2_echo world tcp` shows ≈ (0.232, 0, 0.150);
    - `/joint_states` shows both fingers at 0.02 (gap 40 mm), then at 0 (gap 0 mm).
  - ⚠️ **Challenge:** something won't behave as expected here. Find out why with the debugging toolbox.
  - 🤝 **AI helps:** the hint ladder only.

- [ ] **Lesson 1.2.6: Clean up and commit**
  - 🛠️ **Do:** remove the old robot's xacro and meshes (they stay in git history), check that nothing
    refers to the old names (`grep -rn "Joint0\|Link_1\|tool0" src`), and update the README.
  - ✅ **Test:** a clean build, and the Gazebo checks from 1.2.5 still pass.

---

# Phase 2: MoveIt 2 🟡

**Why:** turns "go to this pose" into a safe, collision-free trajectory. It's used in almost every manipulation job.
**At the end you can:** plan and execute arm motions from RViz and from your own Python code.

## Step 2.1: Understand and generate the MoveIt config

- [ ] **Lesson 2.1.1: How MoveIt is put together (concept lesson)**
  - 🎯 **Learn:** `move_group`, the planning scene, planning pipelines, IK solvers, and how MoveIt hands trajectories to controllers.
  - 📖 **Explain:** you ask for a goal pose. IK turns it into joint angles, a planner finds a
    collision-free path, time parameterisation adds speeds, and MoveIt sends the trajectory to
    your `arm_controller`.
  - 🛠️ **Do:** draw this flow, from your goal down to the joints moving in Gazebo.
  - ✅ **Test:** you can explain each box in your diagram in one sentence.
  - 🤝 **AI helps:** explains and checks your diagram.

- [ ] **Lesson 2.1.2: Run MoveIt Setup Assistant**
  - 🎯 **Learn:** SRDF, planning groups, end effectors, the self-collision matrix, the virtual joint.
  - 🛠️ **Do:** run `ros2 launch moveit_setup_assistant setup_assistant.launch.py` and load your xacro. Create:
    - the collision matrix;
    - group `arm` (chain `base_link → tcp`) and group `gripper` (both fingers);
    - poses `home`, `ready`, `open` and `closed`;
    - an end effector at `tcp`;
    - a mapping to your existing `arm_controller`.

    Generate the `helene_moveit_config` package.
  - ✅ **Test:** the package builds.
  - 🤝 **AI helps:** walks through each screen. Warns you **not** to let it create a second ros2_control setup (Gazebo already runs one).

- [ ] **Lesson 2.1.3: Read the generated files**
  - 🎯 **Learn:** what `*.srdf`, `kinematics.yaml`, `joint_limits.yaml` and `moveit_controllers.yaml` each control.
  - 🛠️ **Do:** read each file and add a comment above every block saying what it does. Check that acceleration limits are set (MoveIt needs them to compute speeds along the path).
  - ✅ **Test:** you can answer: which IK solver is used? Which links never collision-check against each other, and why?
  - 🤝 **AI helps:** answers your questions.

- [ ] **Lesson 2.1.4: Try it with fake hardware**
  - 🛠️ **Do:** run the generated `demo.launch.py`, then drag the goal marker in RViz and Plan & Execute.
  - ✅ **Test:** the arm moves in RViz, with planned paths for `ready` and for random goals.
  - 🤝 **AI helps:** debugging hints.

## Step 2.2: MoveIt and Gazebo together

- [ ] **Lesson 2.2.1: Connect move_group to the Gazebo controllers**
  - 🎯 **Learn:** `use_sim_time`, matching controller names, starting only one ros2_control setup.
  - 🛠️ **Do:** write a `sim_moveit.launch.py` that starts Gazebo (Phase 1), then `move_group` and RViz with simulation time.
  - ✅ **Test:** Plan & Execute in RViz moves the arm **in Gazebo**.
  - 🤝 **AI helps:** reviews the launch file.

- [ ] **Lesson 2.2.2: Typical MoveIt failures (debugging lesson)**
  - 🎯 **Learn:** reading MoveIt errors: start-state tolerance, controllers not found, no IK solution, timeouts.
  - 🛠️ **Do:** cause each one on purpose (wrong controller name, unreachable pose, sim time turned off) and record the error and fix in the log.
  - ✅ **Test:** you can name the cause from the error message alone.
  - 🤝 **AI helps:** suggests which failure to try next.

## Step 2.3: MoveIt from your own Python code

- [ ] **Lesson 2.3.1: Choose a Python API**
  - 🎯 **Learn:** MoveItPy (the official Python API) vs calling `move_group`'s services and actions directly.
  - 🛠️ **Do:** check whether `ros-jazzy-moveit-py` is installable. Compare the two options and write your choice in the log.
  - 🤝 **AI helps:** explains the trade-offs.

- [ ] **Lesson 2.3.2: Plan to a named pose and a joint goal**
  - 🛠️ **Do:** a Python node that moves to `ready`, then to a given set of joint angles.
  - ✅ **Test:** the arm reaches both in Gazebo, and your script prints whether planning succeeded.
  - 🤝 **AI helps:** an API cheat-sheet and a skeleton with TODOs.

- [ ] **Lesson 2.3.3: Plan to a pose (gripper pointing down)**
  - 🎯 **Learn:** quaternions in practice. For HELENE, the approach direction is the **tcp +X** axis.
  - 📖 **Explain:** "pointing down" means `tcp` +X maps to world −Z. Work out that rotation yourself (hint: one rotation about Y), then add a yaw angle.
  - 🛠️ **Do:** a helper `tcp_pose(x, y, z, yaw)` and a script that moves above 4 different points.
  - ✅ **Test:** `tf2_echo world tcp` matches each target within 2 mm, and the gripper points straight down.
  - 🤝 **AI helps:** checks your maths.

- [ ] **Lesson 2.3.4: Straight-line moves (Cartesian paths)**
  - 🎯 **Learn:** `compute_cartesian_path`, step size, the "fraction" result, and why straight lines matter when grasping.
  - 🛠️ **Do:** move 5 cm straight down and back up.
  - ✅ **Test:** fraction = 1.0, and the TCP x and y stay constant during the move.
  - 🤝 **AI helps:** a skeleton.

- [ ] **Lesson 2.3.5: The planning scene (obstacles)**
  - 🎯 **Learn:** collision objects, and attaching or detaching an object to the gripper.
  - 🛠️ **Do:** add a box (a stand-in for the board) and plan a move that has to go around it.
  - ✅ **Test:** RViz shows the box and the planned path avoids it.
  - 🤝 **AI helps:** an API cheat-sheet.

- [ ] **Lesson 2.3.6: A reusable motion module**
  - 🛠️ **Do:** clean up 2.3.2–2.3.5 into one Python module (e.g. `MotionClient`) that you'll reuse in Phase 6.
  - ✅ **Test:** a short demo script uses only your module.
  - 🤝 **AI helps:** a code review.

- [ ] **Lesson 2.3.7: Reachability check**
  - 🛠️ **Do:** for a grid of points in front of the robot, check which ones have an IK solution with the gripper pointing down.
  - ✅ **Test:** you know how big a board the arm can serve, which you'll need in Phase 4.
  - 🤝 **AI helps:** helps interpret the results.

---

# Phase 3: Chess engine with adjustable rating 🔴 (no ROS needed, do it any time)

**Why:** keeps game rules separate from the robot, and gives you something to play against early.
**At the end you can:** play against an engine at any rating you choose, from the terminal.

## Step 3.1: Chess in code

- [ ] **Lesson 3.1.1: Chess notation primer**
  - 🎯 **Learn:** square names, UCI notation (`e2e4`, `e7e8q`), SAN notation (`Nf3`, `O-O`), and FEN (one line that describes a whole position).
  - 🛠️ **Do:** write the FEN for the position after 1.e4 by hand, then check it in python-chess.
  - ✅ **Test:** you can read any FEN and set up the position on a board.
  - 🤝 **AI helps:** explains with examples and quizzes you.

- [ ] **Lesson 3.1.2: Explore python-chess in the REPL**
  - 🎯 **Learn:** `chess.Board`, `push`, `pop`, `legal_moves`, `is_check`, `is_checkmate`, `is_stalemate`.
  - 🛠️ **Do:** in `python3`, play Scholar's Mate move by move, and test illegal moves.
  - ✅ **Test:** you can explain what `board.push_san("Nf3")` changes inside the board object.
  - 🤝 **AI helps:** gives a tiny example to start from.

- [ ] **Lesson 3.1.3: A terminal game against yourself**
  - 🛠️ **Do:** `play_self.py`: show the board, read a move, reject illegal moves, and detect the end of the game.
  - ✅ **Test:** you can play a full game, and illegal moves are rejected with a clear message.
  - 🤝 **AI helps:** a skeleton with TODOs.

- [ ] **Lesson 3.1.4: Special moves as data**
  - 🎯 **Learn:** `is_capture`, `is_castling`, `is_en_passant`, `move.promotion`. The robot will later need to know "which pieces physically move".
  - 🛠️ **Do:** a function `physical_steps(board, move)` that returns a list such as
    `[("remove", "d5"), ("move", "e5", "d6")]`.
  - ✅ **Test:** correct output for a normal move, a capture, castling on both sides, en passant and promotion.
  - 🤝 **AI helps:** a review. (You'll reuse this in Phases 6 and 7.)

## Step 3.2: Talking to Stockfish

- [ ] **Lesson 3.2.1: The UCI protocol by hand**
  - 🎯 **Learn:** how chess programs and engines talk over plain text.
  - 🛠️ **Do:** run `/usr/games/stockfish` and type `uci`, `isready`, `position startpos moves e2e4`, `go movetime 500`, `quit`.
  - ✅ **Test:** you can explain every line it prints, including `info … score cp …` and `bestmove`.
  - 🤝 **AI helps:** explains the output.

- [ ] **Lesson 3.2.2: Stockfish from Python**
  - 🎯 **Learn:** `chess.engine.SimpleEngine.popen_uci`, `engine.play(board, Limit(time=…))`, closing the engine properly.
  - 🛠️ **Do:** change your terminal game so Stockfish plays black.
  - ✅ **Test:** a full game against Stockfish runs with no hanging processes afterwards (`pgrep stockfish` is empty).
  - 🤝 **AI helps:** a skeleton.

## Step 3.3: Adjustable rating

- [ ] **Lesson 3.3.1: How engine strength works**
  - 🎯 **Learn:** what an Elo rating means, `UCI_LimitStrength` + `UCI_Elo` (Stockfish 16: 1320–3190), `Skill Level` 0–20, and think-time limits.
  - 🛠️ **Do:** design how **one rating number** (say 400–3000) maps onto those settings. Below 1320 you need another method: skill level, a very short think time, or occasionally a random move. Write the design in the log.
  - ✅ **Test:** the design covers the whole range, with no gaps.
  - 🤝 **AI helps:** discusses the options and their weak points.

- [ ] **Lesson 3.3.2: Write the engine class**
  - 🛠️ **Do:** `RatedEngine(rating)` with `choose_move(board)`, `set_rating(r)` and `close()`. Keep it free of ROS so it's easy to test.
  - ✅ **Test:** it works in your terminal game.
  - 🤝 **AI helps:** reviews your class design.

- [ ] **Lesson 3.3.3: Your first pytest tests**
  - 🎯 **Learn:** pytest basics (test functions, `assert`, fixtures, `pytest.raises`).
  - 🛠️ **Do:** test that the rating mapping stays in range, that `choose_move` always returns a legal move, and that a finished game raises a clear error.
  - ✅ **Test:** `pytest` passes, and a test you break on purpose fails.
  - 🤝 **AI helps:** a pytest primer and a skeleton.

- [ ] **Lesson 3.3.4: Play at three strengths**
  - 🛠️ **Do:** play against 800, 1500 and 2200. Write in the log how each one felt.
  - ✅ **Test:** the 2200 engine clearly plays better than the 800 one.

---

# Phase 4: Chess world and camera in Gazebo 🟢 / 🔴 camera

**Why:** the stage where the robot and the camera meet.
**At the end you can:** see the board from a simulated camera as a ROS topic, and move pieces "like a person's hand".

## Step 4.1: Board and pieces

- [ ] **Lesson 4.1.1: The board coordinate convention**
  - 🎯 **Learn:** keeping one source of truth for geometry.
  - 📖 **Explain:** define a `chessboard_frame` (origin, axis directions, square size) once. Every
    node uses the same `square ↔ world` functions. Use your reachability result from 2.3.7 to place the board.
  - 🛠️ **Do:** a config file (YAML) plus a pure-Python module `board.py` with `square_to_world`, `world_to_square` and capture-tray slots.
  - ✅ **Test:** pytest: round trips for all 64 squares, and neighbouring squares exactly one square apart.
  - 🤝 **AI helps:** reviews your convention.

- [ ] **Lesson 4.1.2: The board model**
  - 🛠️ **Do:** an SDF board (an 8×8 grid of coloured tiles plus one collision box).
  - ✅ **Test:** it looks right in Gazebo, with a1 on the correct side.
  - 🤝 **AI helps:** SDF syntax hints.

- [ ] **Lesson 4.1.3: Piece models, generated from the config**
  - 🎯 **Learn:** simple collision shapes, mass and inertia, friction, and why to generate 32 models instead of hand-writing them.
  - 🛠️ **Do:** a generator script that writes the world SDF with all 32 pieces, each with a unique name like `white_pawn_e2`.
  - ✅ **Test:** the world validates (`gz sdf -k`), and every piece sits stably on its square.
  - 🤝 **AI helps:** a review.

- [ ] **Lesson 4.1.4: Launch the world with the robot**
  - 🛠️ **Do:** `chess_sim.launch.py` that generates the world, then starts Gazebo, the robot and MoveIt.
  - ✅ **Test:** the robot can reach above the four corner squares (using your motion module).

## Step 4.2: Camera

- [ ] **Lesson 4.2.1: How a camera works (concept lesson)**
  - 🎯 **Learn:** the pinhole camera model, field of view, resolution, camera intrinsics, and `CameraInfo`.
  - 🛠️ **Do:** given the FOV and resolution, calculate the focal length in pixels by hand.
  - ✅ **Test:** your number matches `CameraInfo` (after 4.2.2).
  - 🤝 **AI helps:** a full explanation with a diagram.

- [ ] **Lesson 4.2.2: A camera in Gazebo, bridged to ROS**
  - 🛠️ **Do:** add a camera sensor above the board (and the Sensors system), then bridge it to `/camera/image_raw` and `/camera/camera_info`.
  - ✅ **Test:** `rqt_image_view` shows the whole board, even with the arm at `ready`.
  - 🤝 **AI helps:** a sensor and bridge cheat-sheet.

## Step 4.3: Ground truth and the "person's hand"

- [ ] **Lesson 4.3.1: Read piece positions from Gazebo (testing only)**
  - 🎯 **Learn:** reading simulator state. This is *ground truth*, used only to grade your vision, never to cheat.
  - 🛠️ **Do:** a node that reports which square each piece is on. (Investigate whether the ROS bridge keeps entity names.)
  - ✅ **Test:** all 32 pieces are reported on their correct squares.
  - 🤝 **AI helps:** debugging hints.

- [ ] **Lesson 4.3.2: Move a piece "by hand", and reset the board**
  - 🛠️ **Do:** services that move a piece to a square (Gazebo `set_pose`) and put all pieces back to the start.
  - ✅ **Test:** moving e2 → e4 and then resetting both work. Your vision (Phase 5) will never call or read these.

---

# Phase 5: Vision with OpenCV 🔴

**Why:** the biggest new skill area, and core to robotics + AI careers (perception).
**At the end you can:** detect the person's move from camera images alone.

## Step 5.1: OpenCV foundations

- [ ] **Lesson 5.1.1: Images are arrays**
  - 🎯 **Learn:** NumPy arrays, `shape`, `dtype`, BGR channel order, slicing, `imread`, `imwrite`, `imshow`.
  - 🛠️ **Do:** save one camera frame to disk, then work offline: crop a square, measure its average colour, draw a rectangle.
  - ✅ **Test:** you can explain why `img[100, 200]` gives three numbers, and in what order.
  - 🤝 **AI helps:** a concept lesson and a tiny example.

- [ ] **Lesson 5.1.2: ROS ↔ OpenCV with cv_bridge**
  - 🛠️ **Do:** a node that subscribes to `/camera/image_raw`, converts frames with `cv_bridge`, and shows them or saves them on a key press.
  - ✅ **Test:** a live window shows the board.
  - 🤝 **AI helps:** a skeleton.

- [ ] **Lesson 5.1.3: Colour spaces and thresholding**
  - 🎯 **Learn:** HSV vs BGR, `inRange`, Otsu thresholding, tuning with trackbars.
  - 🛠️ **Do:** make a mask that isolates the board (or the light and dark squares).
  - ✅ **Test:** the mask is clean, and you can say why HSV makes this easier.
  - 🤝 **AI helps:** an explanation and a trackbar skeleton.

- [ ] **Lesson 5.1.4: Contours**
  - 🎯 **Learn:** `findContours`, `contourArea`, and `approxPolyDP` to reduce an outline to 4 corners.
  - 🛠️ **Do:** find the board's outer contour and its 4 corner points.
  - ✅ **Test:** the corners are drawn exactly on the board's edges.
  - 🤝 **AI helps:** debugging hints.

## Step 5.2: A top-down view of the board

- [ ] **Lesson 5.2.1: Homography (concept lesson)**
  - 🎯 **Learn:** why 4 point pairs define a perspective mapping, and what the 3×3 matrix means.
  - 🛠️ **Do:** on paper, explain why a square seen from an angle looks like a general four-sided shape, and how the warp "undoes" that.
  - 🤝 **AI helps:** a full explanation.

- [ ] **Lesson 5.2.2: Warp to a straight-down view**
  - 🛠️ **Do:** order the corners consistently, use `getPerspectiveTransform` and `warpPerspective` to make a 400×400 image.
  - ✅ **Test:** the warped board is square, and the grid lines are straight.
  - 🤝 **AI helps:** a skeleton.

- [ ] **Lesson 5.2.3: The 8×8 grid and square names**
  - 🎯 **Learn:** linking image orientation to the board convention (which corner is a1?).
  - 🛠️ **Do:** split the image into 64 cells and label each with its square name, using your Phase 4 convention.
  - ✅ **Test:** the overlay labels match the real squares (check against ground truth from 4.3.1).

- [ ] **Lesson 5.2.4: When the arm blocks the view**
  - 🛠️ **Do:** detect when the board isn't fully visible (the arm is in the way, or the corners aren't found), and refuse to judge until the view is clear again.
  - ✅ **Test:** with the arm over the board, the node reports "board occluded" instead of making something up.

## Step 5.3: What's on each square?

- [ ] **Lesson 5.3.1: Features for each square**
  - 🎯 **Learn:** turning pixels into numbers: mean, standard deviation, colour statistics of the square's centre.
  - 🛠️ **Do:** compute features for all 64 squares and plot them (empty vs white vs black).
  - ✅ **Test:** the plot shows clear clusters.
  - 🤝 **AI helps:** helps interpret the plot.

- [ ] **Lesson 5.3.2: A classifier with measured accuracy**
  - 🎯 **Learn:** thresholds vs simple ML, and measuring accuracy against ground truth.
  - 🛠️ **Do:** classify every square as empty, white or black.
  - ✅ **Test:** 64/64 correct in the start position and in 5 other positions (set up with the 4.3.2 service).
  - 🤝 **AI helps:** an explanation of evaluation (a confusion matrix).

- [ ] **Lesson 5.3.3: Robustness**
  - 🛠️ **Do:** test with changed lighting and a slightly moved camera.
  - ✅ **Test:** accuracy stays at 100%, or you can explain each failure and fix it.

## Step 5.4: Detecting the move

- [ ] **Lesson 5.4.1: Before/after differences**
  - 🛠️ **Do:** compare the occupancy before and after the person's move, and list the squares that changed.
  - ✅ **Test:** for e2 → e4, exactly those 2 squares changed.

- [ ] **Lesson 5.4.2: Use chess legality to identify the move**
  - 🎯 **Learn:** combining noisy perception with rules. A capture changes a square's colour; castling changes 4 squares; en passant changes 3.
  - 🛠️ **Do:** find the single legal move whose result matches what you observed.
  - ✅ **Test:** correct for a normal move, a capture, castling and en passant. An unclear situation returns "not sure", never a guess.
  - 🤝 **AI helps:** discusses edge cases. Reuses your Lesson 3.1.4 function.

- [ ] **Lesson 5.4.3: A move-detector node**
  - 🎯 **Learn:** waiting for the scene to stop moving before trusting a frame.
  - 🛠️ **Do:** a node that waits for a stable view, detects the move, and publishes it (e.g. as UCI text).
  - ✅ **Test:** after `/chess_world/move_piece e2 e4`, the node publishes `e2e4` without reading that command.

- [ ] **Lesson 5.4.4: Evaluation**
  - 🛠️ **Do:** a script that plays 10 scripted moves (including a capture and a castle) and scores the detector.
  - ✅ **Test:** 10/10.

- [ ] **Lesson 5.4.5 (optional AI stretch): A small CNN square classifier**
  - 🎯 **Learn:** collecting a dataset from simulation, training a small CNN in PyTorch, comparing it to your thresholds.
  - ✅ **Test:** it matches or beats the threshold classifier on new positions.

---

# Phase 6: Pick and place 🟡

**Why:** reliable manipulation is the heart of the project.
**At the end you can:** move any piece between squares, and handle captures, castling and promotion.

## Step 6.1: The grasp sequence

- [ ] **Lesson 6.1.1: Grasp geometry**
  - 🎯 **Learn:** where the TCP must be. The finger pads span ±16 mm around the TCP along the approach axis, so they must stay clear of the board and the piece's base. Also: why the jaws should close along a board diagonal (neighbours are 42 mm away instead of 30 mm).
  - 🛠️ **Do:** calculate the grasp height, the approach height and the carrying height for your pieces.
  - ✅ **Test:** your numbers keep the fingertips off the board and the gripper body above the tallest piece.
  - 🤝 **AI helps:** checks your maths.

- [ ] **Lesson 6.1.2: The sequence as code**
  - 🛠️ **Do:** above the piece → open → down in a straight line → close → lift → carry → lower → open → back up, using your Phase 2 motion module and the gripper topic (both fingers equal).
  - ✅ **Test:** a pawn moves e2 → e4 once.
  - 🤝 **AI helps:** a skeleton with TODOs.

- [ ] **Lesson 6.1.3: The planning scene during the grasp**
  - 🎯 **Learn:** adding the board and pieces as collision objects, removing the target piece before grasping, and attaching the held piece to `tcp`.
  - 🛠️ **Do:** add all of this.
  - ✅ **Test:** RViz shows the held piece moving with the gripper, and other pieces are avoided.

- [ ] **Lesson 6.1.4: Repeatability**
  - ✅ **Test:** e2 → e4 → e2, five times in a row with no failures.

## Step 6.2: Grasp quality

- [ ] **Lesson 6.2.1: Friction contacts in the simulator**
  - 🎯 **Learn:** why friction-only grasping is hard in simulation (mu, kp, kd, contact depth) and how to tune it.
  - 🛠️ **Do:** experiment with the pad and piece contact values, and record the results.
  - 🤝 **AI helps:** an explanation.

- [ ] **Lesson 6.2.2: Check every grasp and placement**
  - 🎯 **Learn:** if the fingers stop wider than you commanded, they're holding something. A lifted piece's height should rise.
  - 🛠️ **Do:** add checks after the close, the lift and the placement.
  - ✅ **Test:** move the piece away on purpose before closing. The failure is detected and reported, not ignored.

## Step 6.3: An action server and special moves

- [ ] **Lesson 6.3.1: Custom action interface**
  - 🎯 **Learn:** actions vs services (feedback, cancelling, results), and defining your own `.action` file.
  - 🛠️ **Do:** define an `ExecuteMoves.action` file and wrap Step 6.1 in an action server that reports each stage.
  - ✅ **Test:** `ros2 action send_goal` with feedback works.

- [ ] **Lesson 6.3.2: Captures and the tray**
  - 🛠️ **Do:** move a captured piece to the next free slot in its capture tray.
  - ✅ **Test:** three captures in a row land in three different slots.

- [ ] **Lesson 6.3.3: Castling and promotion**
  - 🛠️ **Do:** castling = two moves in one request. Promotion = swap the pawn's model for the new piece.
  - ✅ **Test:** both castles and a promotion work, using your Lesson 3.1.4 function.

---

# Phase 7: The full game loop 🟡

**Why:** integration is where real robotics work happens.
**At the end you can:** play a full game against the robot at a chosen rating.

- [ ] **Lesson 7.1.1: Architecture**
  - 🛠️ **Do:** draw the nodes (game, vision, engine, manipulation, world) and the interfaces between them (topics, services, actions).
  - ✅ **Test:** every arrow in the diagram has a message type.
  - 🤝 **AI helps:** reviews the diagram.

- [ ] **Lesson 7.1.2: Design the state machine**
  - 🛠️ **Do:** on paper, design the states (waiting for the person → detecting → validating → engine thinking → robot moving → checking → committing) and the error transitions.
  - ✅ **Test:** every failure has a defined next state.

- [ ] **Lesson 7.1.3: The game node**
  - 🛠️ **Do:** implement it, using your engine class (Phase 3), the move detector (Phase 5) and the action server (Phase 6).
  - ✅ **Test:** one full exchange works: the person's command → vision → the engine's reply → the arm → the check.

- [ ] **Lesson 7.2.1: Never corrupt the game state**
  - 🎯 **Learn:** commit-after-success, i.e. only update the game record once the physical move is confirmed.
  - 🛠️ **Do:** handle an illegal move by the person, an unclear detection, a failed grasp and a check mismatch.
  - ✅ **Test:** inject each failure; the logical board stays correct and the problem is reported.

- [ ] **Lesson 7.2.2: Change the rating while running**
  - 🛠️ **Do:** expose the rating as a ROS parameter (`ros2 param set /chess_game rating 1800`).
  - ✅ **Test:** the change takes effect on the next move.

- [ ] **Lesson 7.3.1: One-command launch**
  - ✅ **Test:** a single launch command starts a game, and a full game runs with no manual help.

- [ ] **Lesson 7.3.2: Demo and README**
  - 🛠️ **Do:** record a demo video, update the README with a GIF, the architecture diagram and instructions.

---

# Phase 8: The real world 🟢 hardware / 🔴 C++

**Why:** sim-to-real is what employers value most.
**At the end you can:** play chess against the real HELENE on a real board.
*(This phase gets refined once Phases 1–7 are done.)*

## Step 8.1: Real camera and real board

- [ ] **Lesson 8.1.1: Webcam in ROS**
  - 🛠️ **Do:** publish the webcam as `/camera/image_raw` (e.g. with `v4l2_camera` or `usb_cam`), the same topic as the simulator.
  - ✅ **Test:** `rqt_image_view` shows the real board.

- [ ] **Lesson 8.1.2: Camera calibration**
  - 🎯 **Learn:** lens distortion, the checkerboard method, what the calibration file contains.
  - 🛠️ **Do:** calibrate with a printed checkerboard (the ROS `camera_calibration` package, or `cv2.calibrateCamera`).
  - ✅ **Test:** straight lines look straight in the undistorted image, and the reprojection error is small.
  - 🤝 **AI helps:** a full explanation.

- [ ] **Lesson 8.1.3: Your vision on real images**
  - ✅ **Test:** occupancy is 64/64 on the real start position, and 10/10 moves are detected. Write down what you had to change compared with simulation.

## Step 8.2: Real HELENE hardware

- [ ] **Lesson 8.2.1: Electronics and power plan:** servos, microcontroller, power supply, wiring diagram.
- [ ] **Lesson 8.2.2: Firmware:** the microcontroller receives joint targets over serial and reports positions.
- [ ] **Lesson 8.2.3: Joint calibration:** match each servo's zero and direction to the URDF.

## Step 8.3: Connect it to ros2_control

- [ ] **Lesson 8.3.1: C++ for ROS 2 primer** 🔴: build a minimal C++ node, then classes, smart pointers, CMake basics.
- [ ] **Lesson 8.3.2: How a hardware interface works:** the lifecycle, `read()` / `write()`, interfaces.
- [ ] **Lesson 8.3.3: Implement a `SystemInterface` for HELENE** (C++), or a Python serial bridge (decide in 8.3.2).
  - ✅ **Test:** MoveIt moves the real arm to `ready` and back.

## Step 8.4: Sim-to-real

- [ ] **Lesson 8.4.1: Measure accuracy and grasp success** compared with simulation, and write down what changed and why.
- [ ] **Lesson 8.4.2: Play a real game.** 🎉

---

## Career skills you'll be able to show
ROS 2 system integration · ros2_control · MoveIt 2 · Gazebo simulation · OpenCV perception (homography,
calibration) · engine integration · pytest · custom actions · state machines · sim-to-real on real
hardware · C++ ros2_control (Phase 8) · optional CNN for perception.

**Portfolio checklist (end of project):** a README with a demo GIF or video · an architecture diagram ·
a one-command setup (Docker optional) · tests in CI · a short write-up of the 3 hardest bugs you solved.
