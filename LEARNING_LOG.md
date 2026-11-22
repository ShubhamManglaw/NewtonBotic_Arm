# Learning Log: chess-playing arm (branch `learn/chess-arm`)

Goal: a HELENE arm with its gripper plays chess one-on-one against a person.
The person moves a piece, OpenCV detects the move, an engine with an adjustable rating
replies, and the arm moves the piece. Built first in Gazebo, then on a real arm and board.

Reference solution: tag `reference/ai-build` (also `main`). Look at it only at the
"show me" rung of the hint ladder.

## Kickoff: 2026-11-21

### Decisions
- Branch `learn/chess-arm` from `4c829b9` (my own work, before the AI rebuild).
- Arm: HELENE with its parallel-jaw gripper. I built my own arm already, so redoing a gripper teaches me little.
- Person: simulated first. A camera in Gazebo watches the board and the "person" moves pieces by
  command. Vision must detect the move **from pixels only**, never by reading the command.
  Final phase: real webcam, real board, real arm.

### Comfort ratings (0 new · 1 seen · 2 concept ok, syntax rusty · 3 confident)
| Topic | Rating |
|---|---|
| ROS 2 core | 3 |
| URDF/xacro, TF | 3 |
| ros2_control + Gazebo Sim | 3 |
| MoveIt 2 | 2 |
| Gripper modelling / grasp physics | 2 |
| OpenCV basics | 1 |
| Camera calibration, perspective transforms | 1 |
| Move detection | 1 |
| Chess engines (python-chess, UCI, Stockfish) | 0 |
| Python | 3 (tests: introduce pytest when needed) |
| C++ for ROS 2 | 0 |
| Hardware (servos, MCU, serial) | 3 |

### Environment
Ubuntu 24.04 · ROS 2 Jazzy · Gazebo Harmonic 8.15 · MoveIt 2 · OpenCV 4.6 · python-chess 1.11 ·
Stockfish 16 (`UCI_Elo` 1320–3190, `Skill Level` 0–20) · webcams at /dev/video0, /dev/video1 · RTX 5060.

### Baseline
`colcon build` on the branch: 5 packages, clean.

---
<!-- One entry per step: concept, what was built, bugs (symptom → cause → how to detect), open questions -->
