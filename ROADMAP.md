# Roadmap: chess-playing robot arm (learning edition)

**Goal:** a HELENE arm with its gripper plays chess one-on-one against a person. The person
moves a piece, OpenCV detects the move from camera images, an engine with an **adjustable rating**
replies, and the arm moves the piece. Built in Gazebo first, then on a real arm and board.

**How to use this file**
- Work through the phases in order (Phase 3 needs no ROS, so it can be done any time as a break).
- Tick boxes as you finish steps. After each step, add an entry to [LEARNING_LOG.md](LEARNING_LOG.md):
  the concept, what you built, the bugs you hit (symptom → cause → how to detect it), and open questions.
- **Done when** = the check that proves a step works. Don't move on until it passes.
- **Help level** comes from your comfort ratings (0 new · 1 seen · 2 concept ok, syntax rusty ·
  3 confident). It sets how much the AI gives you; see `~/LEARNING_MODE.md`.
- Reference solution: tag `reference/ai-build`. Look at it only after the "show me" hint.
- Commit after every finished step, with a clear message (e.g. `Phase 2.1: MoveIt config for HELENE`).

**Time estimate:** about 16–20 weeks at roughly 10 hours a week. That's a guide, not a deadline.

| Phase | Topic | Help level | Estimate | Status |
|---|---|---|---|---|
| 1 | HELENE in your workspace | 3: you lead, AI reviews | 1 week | ☐ |
| 2 | MoveIt 2 | 2: syntax refreshers | 2 weeks | ☐ |
| 3 | Chess engine + adjustable rating | 0: full explanations | 1 week | ☐ |
| 4 | Chess world + camera in Gazebo | 3 (camera sensors are new) | 1 week | ☐ |
| 5 | Vision with OpenCV | 1: explanations + skeletons | 3 weeks | ☐ |
| 6 | Pick and place | 2: syntax refreshers | 2 weeks | ☐ |
| 7 | Full game loop | mixed | 1–2 weeks | ☐ |
| 8 | Real world: camera, board, arm | 3 hardware · 0 C++ | 4–6 weeks | ☐ |

---

## Phase 1: HELENE in your workspace
**Why:** everything else builds on a robot that loads, simulates and responds to commands correctly.

- [ ] **1.1 Bring in the model.** Add `helene_description` (the generated xacro and meshes only) to `src/`.
  - *Concept:* workspace packages, `package://` mesh paths, why generated files are never edited by hand.
  - *Done when:* `colcon build` is clean, `check_urdf` passes on the expanded URDF, and RViz shows the arm and gripper, with the sliders moving the right parts.
- [ ] **1.2 Run it in Gazebo.** Write your own wrapper xacro (ros2_control for joint1–6 and both fingers, the Gazebo plugin, finger friction) and a controllers YAML (arm trajectory controller, gripper controller).
  - *Concept:* the ros2_control data flow: controller → command interface → hardware (Gazebo).
  - *Done when:*
    - the robot spawns and 3 controllers are `active`;
    - the `ready` pose `[0, 11, 0.46, 0, -79.46, 0]°` puts the TCP at (0.232, 0, 0.150);
    - the gripper opens and closes to 40 mm and 0 mm.
  - ⚠️ A real Gazebo quirk is waiting in this step. Debug it with the hint ladder.

**Resources:** control.ros.org (Jazzy) → gz_ros2_control · gazebosim.org/docs/harmonic

---

## Phase 2: MoveIt 2
**Why:** turns "go to this pose" into a safe, collision-free joint trajectory. Every manipulation job uses this.

- [ ] **2.1 Generate the config with MoveIt Setup Assistant (GUI).**
  - *Concept:* the SRDF, planning groups (`arm`, `gripper`), the end effector at `tcp`, the allowed-collision matrix, IK plugins.
  - *Done when:* the config package builds and the demo launch plans in RViz.
- [ ] **2.2 Plan and execute in RViz with Gazebo running.**
  - *Concept:* the `move_group` node, how MoveIt's controller settings map to your controllers, trajectory execution, `use_sim_time`.
  - *Done when:* dragging the goal in RViz, then Plan & Execute, moves the arm in Gazebo.
- [ ] **2.3 Plan from your own Python code.** Move to a pose above a square, then go straight down and up.
  - *Concept:* IK, planners (OMPL vs Pilz), Cartesian paths, time parameterisation. Choose an API (MoveItPy, or calling `move_group`'s services and actions).
  - *Done when:* a script reaches poses above 4 corner squares within 2 mm (checked with `tf2_echo`).

**Resources:** moveit.picknik.ai → "MoveIt Setup Assistant", "Your First C++/Python MoveIt Project", "MoveIt Python API" ·
*Modern Robotics* (Lynch & Park), chapters 4–6 (forward kinematics, velocity kinematics, inverse kinematics)

---

## Phase 3: Chess engine with adjustable rating (no ROS needed)
**Why:** keeps the game rules and decisions separate from the robot. It's also a quick win you can play against.

- [ ] **3.1 python-chess basics.**
  - *Concept:* `chess.Board`, legal moves, UCI notation (`e2e4`) vs SAN (`Nf3`), FEN position strings, check, mate, stalemate, draws.
  - *Done when:* you can play against yourself in the terminal, and illegal moves are rejected.
- [ ] **3.2 Talk to Stockfish by hand.** Run `/usr/games/stockfish` and type `uci`, `position startpos moves e2e4`, then `go movetime 500`.
  - *Concept:* the UCI protocol, which is how chess programs talk to engines.
  - *Done when:* you can explain each line Stockfish prints.
- [ ] **3.3 An adjustable-rating engine module.**
  - *Concept:* `UCI_LimitStrength` + `UCI_Elo` (1320–3190), and `Skill Level` (0–20) for weaker play. You design how one "rating" number maps onto them.
  - *Concept:* your first **pytest** tests.
  - *Done when:* the tests pass, and you've played against the engine at 3 different strengths.

**Resources:** python-chess.readthedocs.io (Core, Engine communication) · Stockfish wiki → "UCI & Commands"

---

## Phase 4: Chess world and camera in Gazebo
**Why:** the stage where the robot and the camera meet.

- [ ] **4.1 Board and 32 pieces generated from one config file**, with a single square ↔ world coordinate mapping.
  - *Done when:* every piece spawns on its correct square and rests stably.
- [ ] **4.2 Camera sensor above the board, bridged to ROS** as `sensor_msgs/Image` + `CameraInfo`.
  - *Concept:* camera sensors in Gazebo, `ros_gz_bridge` / `ros_gz_image`. Vision reads a ROS image topic, so later the real webcam simply publishes the same topic.
  - *Done when:* `rqt_image_view` shows the board.
- [ ] **4.3 The "person's hand":** a command that moves a piece in Gazebo (set_pose).
  - Rule: vision must **never** read this command. It has to work the move out from pixels.

**Resources:** gazebosim.org/docs/harmonic → "Sensors" · ros_gz (GitHub README)

---

## Phase 5: Vision with OpenCV
**Why:** the largest new skill area, and core to robotics + AI careers (perception).

- [ ] **5.1 OpenCV basics on the simulated camera image**, received via `cv_bridge`.
  - *Concept:* images as arrays, BGR vs HSV colour, thresholding, contours.
  - *Done when:* a node shows a thresholded mask of the board.
- [ ] **5.2 Find the board and warp it to a straight-down view.**
  - *Concept:* camera intrinsics, homography, `findHomography` / `getPerspectiveTransform`, `warpPerspective`.
  - *Done when:* the warped image is a clean square that splits evenly into an 8×8 grid.
- [ ] **5.3 Decide what's on each square:** empty, white piece or black piece.
  - *Done when:* 64/64 squares are correct in the start position and in 5 other positions.
- [ ] **5.4 Detect the move** by comparing before and after, then using chess legality to resolve captures, castling, en passant and promotion.
  - *Done when:* 10 scripted moves are all detected correctly, including at least one capture and one castle.
- [ ] *(Optional AI stretch)* replace the hand-tuned classifier from 5.3 with a small CNN trained on rendered square images.

**Resources:** docs.opencv.org/4.x → Tutorials: "Changing Colorspaces", "Image Thresholding", "Contours",
"Geometric Transformations", "Camera Calibration" · vision_opencv (`cv_bridge`)

---

## Phase 6: Pick and place
**Why:** reliable manipulation is the heart of the project.

- [ ] **6.1 The grasp sequence:** above the piece → approach → close → lift → carry → lower → release → retreat, with the board and pieces in MoveIt's planning scene.
  - *Done when:* a pawn moves e2 → e4 five times in a row.
- [ ] **6.2 Tune the friction grasp and check each move.**
  - *Concept:* contact friction and stiffness in Gazebo, grasp checking from finger positions, placement checking from the piece's pose.
  - *Done when:* a missed grasp is detected and reported, not ignored.
- [ ] **6.3 Special moves:** captures (to a tray), castling (two pieces), promotion.

**Resources:** moveit.picknik.ai → "Planning Scene", "Pick and Place" (MoveIt Task Constructor, optional)

---

## Phase 7: The full game loop
**Why:** integration is where real robotics work happens.

- [ ] **7.1 A game node and state machine:**
  1. wait for the person's move;
  2. vision detects it;
  3. check that it's legal;
  4. the engine replies at the chosen rating;
  5. the arm executes;
  6. vision confirms;
  7. commit the move.
- [ ] **7.2 Failure handling:** an illegal or unclear move, a failed grasp, or a vision mismatch must never corrupt the game state.
- [ ] **7.3 A one-command launch and a demo video.**
  - *Done when:* a full game against the robot runs at a set rating with no manual help.

---

## Phase 8: The real world
**Why:** sim-to-real is what employers value most.

- [ ] **8.1 Real webcam and real board.** Calibrate with a printed checkerboard (`cv2.calibrateCamera`), then rerun the Phase 5 vision on the webcam's topic.
- [ ] **8.2 Build the real HELENE:** servos, a microcontroller and power.
- [ ] **8.3 A ros2_control hardware interface for the real arm.**
  - Options: C++ (the standard approach, and a good first C++ project) or a Python serial bridge. Discuss first.
  - *Done when:* MoveIt moves the real arm to `ready` and back.
- [ ] **8.4 Sim-to-real:** compare grasping and accuracy against simulation, write down what changed and why, and play a real game.

**Resources:** ros2_control_demos (GitHub) → hardware interface examples · micro-ROS (micro.ros.org)

---

## Career skills you'll be able to show
ROS 2 system integration · ros2_control · MoveIt 2 motion planning · Gazebo simulation ·
OpenCV perception (homography, calibration) · game-engine integration · testing with pytest ·
sim-to-real on real hardware · (optional) a CNN for perception.

To make the repo portfolio-ready at the end: a README with a demo GIF or video, a one-command
setup (Docker optional), tests in CI, and a short write-up of the problems you solved.
