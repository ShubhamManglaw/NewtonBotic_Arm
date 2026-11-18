"""Chess game node: authoritative game state + transaction-style move execution.

Services
  ~/submit_move  chess_interfaces/srv/SubmitMove   human move (UCI or SAN) -> robot reply
  ~/new_game     std_srvs/srv/Trigger              reset Gazebo board + game state
  ~/state        std_srvs/srv/Trigger              FEN + ASCII board in `message`
Topic
  ~/fen          std_msgs/String (transient local) committed position

Every move (human's or robot's) is: validate -> plan piece moves -> execute via
/execute_moves -> verify observed occupancy == expected -> commit. If execution
or verification fails, the last committed state is kept and the failure reported.
"""
import threading
import time
import uuid

import chess
import rclpy
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile
from std_msgs.msg import String
from std_srvs.srv import Trigger

from chess_game.engine import MoveSelector
from chess_game.game_logic import ChessGame, MoveError, physical_maps
from chess_interfaces.action import ExecuteMoves
from chess_interfaces.msg import PieceMove
from chess_interfaces.srv import GetPieceStates, SubmitMove


class GameNode(Node):
    def __init__(self):
        super().__init__('chess_game')
        p = self.declare_parameter
        self.robot_color = chess.BLACK if p('robot_color', 'black').value == 'black' \
            else chess.WHITE
        self.selector = MoveSelector(p('engine_path', '').value, p('think_time', 0.5).value,
                                     p('skill_level', 5).value, p('seed', 0).value)
        self.move_timeout = p('move_timeout', 300.0).value
        self.game = ChessGame(self.robot_color)
        self._lock = threading.Lock()

        cb = ReentrantCallbackGroup()
        self._exec = ActionClient(self, ExecuteMoves, '/execute_moves', callback_group=cb)
        self._states = self.create_client(GetPieceStates, '/chess_world/get_piece_states',
                                          callback_group=cb)
        self._reset = self.create_client(Trigger, '/chess_world/reset', callback_group=cb)
        self.create_service(SubmitMove, '~/submit_move', self._submit, callback_group=cb)
        self.create_service(Trigger, '~/new_game', self._new_game, callback_group=cb)
        self.create_service(Trigger, '~/state', self._state, callback_group=cb)
        qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self._fen_pub = self.create_publisher(String, '~/fen', qos)
        self._publish()
        self.get_logger().info(
            f'chess game ready: robot plays {"black" if self.robot_color == chess.BLACK else "white"}'
            f', engine={self.selector.name}')
        if self.robot_color == chess.WHITE:
            self.get_logger().info('robot is white: call ~/submit_move with move "go" to start')

    # ------------------------------------------------------------- helpers
    def _publish(self):
        self._fen_pub.publish(String(data=self.game.board.fen()))

    def _wait(self, fut, timeout):
        ev = threading.Event()
        fut.add_done_callback(lambda _: ev.set())
        return fut.result() if ev.wait(timeout) else None

    def _observe(self):
        if not self._states.wait_for_service(timeout_sec=5.0):
            return None, None, ['chess_world unavailable']
        res = self._wait(self._states.call_async(GetPieceStates.Request()), 10.0)
        if res is None or not res.success:
            return None, None, ['cannot read piece states']
        return physical_maps(res.pieces)

    def _play(self, move: chess.Move, who: str) -> str:
        """Execute + verify + commit one move. Returns '' on success, else an error."""
        log = self.get_logger()
        san = self.game.board.san(move)
        steps = self.game.plan(move)
        req_id = f'{who}-{len(self.game.board.move_stack) + 1}-{move.uci()}-' \
                 f'{uuid.uuid4().hex[:6]}'
        log.info(f'[{req_id}] {who} {san} ({move.uci()}): ' + ', '.join(
            f'{["MOVE", "REMOVE", "REPLACE"][s.operation]} {s.piece_id} '
            f'{s.from_square}->{s.to_square or "graveyard"}' for s in steps))
        goal = ExecuteMoves.Goal(request_id=req_id, moves=[
            PieceMove(piece_id=s.piece_id, from_square=s.from_square, to_square=s.to_square,
                      operation=s.operation, promotion=s.promotion) for s in steps])
        if not self._exec.wait_for_server(timeout_sec=10.0):
            return 'manipulation server (/execute_moves) unavailable'
        gh = self._wait(self._exec.send_goal_async(goal), 10.0)
        if gh is None or not gh.accepted:
            return 'manipulation goal rejected'
        res = self._wait(gh.get_result_async(), self.move_timeout)
        if res is None:
            self._wait(gh.cancel_goal_async(), 10.0)
            return f'manipulation timed out after {self.move_timeout:.0f}s'
        r = res.result
        if not r.success:
            return (f'execution failed at {r.failure_stage} ({r.failure_category}): '
                    f'{r.message}; {r.moves_completed}/{len(steps)} piece moves done')
        # verify the whole board, not just the moved piece
        time.sleep(0.3)
        occ, ids, problems = self._observe()
        if occ is not None:
            problems = problems + self.game.compare(self.game.expected_after(move), occ)
        if problems:
            return 'verification failed: ' + '; '.join(problems[:6])
        self.game.commit(move, physical_ids=ids)
        self._publish()
        log.info(f'[{req_id}] committed. FEN {self.game.board.fen()}')
        return ''

    # ------------------------------------------------------------ services
    def _submit(self, req, res):
        with self._lock:
            res.fen = self.game.board.fen()
            res.status = self.game.status()
            if res.status != 'ONGOING':
                res.accepted, res.message = False, f'game over: {self.game.result_text()}'
                return res
            text = req.move.strip()
            if self.game.human_to_move:
                try:
                    move = self.game.parse_move(text)
                except MoveError as e:
                    res.accepted, res.message = False, str(e)
                    return res
                err = self._play(move, 'human')
                if err:
                    res.accepted, res.status = False, 'ROBOT_FAILURE'
                    res.message = f'could not execute your move: {err}'
                    return res
                res.human_move_uci = move.uci()
            elif text.lower() != 'go':
                res.accepted, res.message = False, 'robot to move: send "go"'
                return res
            res.accepted = True
            res.status = self.game.status()
            if res.status == 'ONGOING':
                reply = self.selector.choose(self.game.board)
                san = self.game.board.san(reply)
                err = self._play(reply, 'robot')
                if err:
                    res.status = 'ROBOT_FAILURE'
                    res.message = f'robot reply {san} failed: {err}'
                else:
                    res.robot_move_uci = reply.uci()
                    res.status = self.game.status()
                    res.message = f'robot played {san}'
                    if res.status != 'ONGOING':
                        res.message += f'; {self.game.result_text()}'
            else:
                res.message = self.game.result_text()
            res.fen = self.game.board.fen()
            return res

    def _new_game(self, _req, res):
        with self._lock:
            if not self._reset.wait_for_service(timeout_sec=5.0):
                res.success, res.message = False, 'chess_world reset unavailable'
                return res
            r = self._wait(self._reset.call_async(Trigger.Request()), 60.0)
            if r is None or not r.success:
                res.success = False
                res.message = f'board reset failed: {r.message if r else "timeout"}'
                return res
            self.game = ChessGame(self.robot_color)
            self._publish()
            res.success, res.message = True, 'new game; ' + r.message
            return res

    def _state(self, _req, res):
        b = self.game.board
        res.success = True
        res.message = (f'{b.fen()}\nstatus: {self.game.status()}\n'
                       f'{"human" if self.game.human_to_move else "robot"} to move\n{b}')
        return res


def main():
    rclpy.init()
    node = GameNode()
    ex = MultiThreadedExecutor(num_threads=4)
    ex.add_node(node)
    try:
        ex.spin()
    except KeyboardInterrupt:
        pass
    node.selector.close()
    node.destroy_node()
    rclpy.try_shutdown()


if __name__ == '__main__':
    main()
