"""Startup demo: a real pick-and-place shortly after the system comes up.

Waits until the manipulation server (/execute_moves) and the chess world are
ready, waits `delay` more seconds, then picks the piece on the first square of
`move` with the gripper and places it on the second (MoveIt plans every arm
motion; the piece is held by friction). If `return_piece` is true it then
carries the piece back, so the board (and the game node) are again in the
standard start position.

  ros2 run chess_manipulation startup_demo --ros-args -p move:=e2e4 -p delay:=5.0
"""
import threading
import time

import rclpy
from rclpy.action import ActionClient
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from chess_interfaces.action import ExecuteMoves
from chess_interfaces.msg import PieceMove
from chess_interfaces.srv import GetPieceStates


class StartupDemo(Node):
    def __init__(self):
        super().__init__('startup_demo')
        self.delay = float(self.declare_parameter('delay', 5.0).value)
        self.move = self.declare_parameter('move', 'e2e4').value.strip().lower()
        self.return_piece = bool(self.declare_parameter('return_piece', True).value)
        self.ready_timeout = float(self.declare_parameter('ready_timeout', 180.0).value)
        self._ac = ActionClient(self, ExecuteMoves, '/execute_moves')
        self._states = self.create_client(GetPieceStates, '/chess_world/get_piece_states')

    @staticmethod
    def _wait(fut, timeout):
        ev = threading.Event()
        fut.add_done_callback(lambda _: ev.set())
        return fut.result() if ev.wait(timeout) else None

    def _piece_on(self, square):
        res = self._wait(self._states.call_async(GetPieceStates.Request()), 15.0)
        if res is None or not res.success:
            return None
        for s in res.pieces:
            if s.square == square and s.upright:
                return s.piece_id
        return None

    def _execute(self, piece_id, frm, to):
        goal = ExecuteMoves.Goal(request_id=f'startup-demo-{frm}{to}', moves=[
            PieceMove(piece_id=piece_id, from_square=frm, to_square=to,
                      operation=PieceMove.MOVE)])
        gh = self._wait(self._ac.send_goal_async(goal), 15.0)
        if gh is None or not gh.accepted:
            self.get_logger().error('demo goal rejected (manipulation server busy?)')
            return False
        res = self._wait(gh.get_result_async(), 300.0)
        if res is None:
            self.get_logger().error('demo move timed out')
            return False
        r = res.result
        if r.success:
            self.get_logger().info(f'demo: {piece_id} {frm} -> {to} done and verified')
        else:
            self.get_logger().error(f'demo: {frm}->{to} failed at {r.failure_stage} '
                                    f'({r.failure_category}): {r.message}')
        return r.success

    def run(self):
        log = self.get_logger()
        if len(self.move) != 4:
            log.error(f'invalid move {self.move!r}; expected UCI like e2e4')
            return
        frm, to = self.move[:2], self.move[2:]
        log.info('startup demo: waiting for the manipulation server and chess world...')
        if not (self._ac.wait_for_server(timeout_sec=self.ready_timeout)
                and self._states.wait_for_service(timeout_sec=self.ready_timeout)):
            log.error('manipulation server / chess world not available; demo skipped')
            return
        log.info(f'system ready: demo {frm}->{to} starts in {self.delay:.0f}s')
        time.sleep(self.delay)
        pid = self._piece_on(frm)
        if pid is None:
            log.error(f'no upright piece on {frm}; demo skipped')
            return
        if self._piece_on(to) is not None:
            log.error(f'{to} is occupied; demo skipped')
            return
        log.info(f'demo: picking {pid} on {frm} and placing it on {to}')
        if self._execute(pid, frm, to) and self.return_piece:
            log.info(f'demo: returning {pid} to {frm} (board back to the start position)')
            self._execute(pid, to, frm)


def main():
    rclpy.init()
    node = StartupDemo()
    ex = MultiThreadedExecutor(num_threads=2)
    ex.add_node(node)
    threading.Thread(target=ex.spin, daemon=True).start()
    try:
        node.run()
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
