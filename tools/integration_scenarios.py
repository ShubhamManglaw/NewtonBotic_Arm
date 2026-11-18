#!/usr/bin/env python3
"""Integration scenarios against a running system (chess_game.launch.py).

  ros2 launch robot_bringup chess_game.launch.py headless:=true rviz:=false
  python3 tools/integration_scenarios.py

Drives /execute_moves directly (bypassing chess rules) to exercise capture,
castling-style two-piece moves, promotion and failure handling, then checks
that the game node rejects an illegal move without changing state.
"""
import sys
import threading

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from std_srvs.srv import Trigger

from chess_interfaces.action import ExecuteMoves
from chess_interfaces.msg import PieceMove
from chess_interfaces.srv import GetPieceStates, SubmitMove

M, R, P = PieceMove.MOVE, PieceMove.REMOVE, PieceMove.REPLACE


def pm(pid, frm, to='', op=M, promo=''):
    return PieceMove(piece_id=pid, from_square=frm, to_square=to, operation=op,
                     promotion=promo)


class Runner(Node):
    def __init__(self):
        super().__init__('integration_scenarios')
        self.ac = ActionClient(self, ExecuteMoves, '/execute_moves')
        self.states = self.create_client(GetPieceStates, '/chess_world/get_piece_states')
        self.new_game = self.create_client(Trigger, '/chess_game/new_game')
        self.submit = self.create_client(SubmitMove, '/chess_game/submit_move')
        self.state = self.create_client(Trigger, '/chess_game/state')

    def wait(self, fut, timeout=300.0):
        ev = threading.Event()
        fut.add_done_callback(lambda _: ev.set())
        ev.wait(timeout)
        return fut.result()

    def call(self, cli, req):
        cli.wait_for_service(timeout_sec=20.0)
        return self.wait(cli.call_async(req))

    def execute(self, name, moves):
        self.ac.wait_for_server(timeout_sec=20.0)
        gh = self.wait(self.ac.send_goal_async(ExecuteMoves.Goal(request_id=name, moves=moves)))
        return self.wait(gh.get_result_async()).result

    def squares(self):
        res = self.call(self.states, GetPieceStates.Request())
        return {s.piece_id: (s.square, s.in_graveyard, s.kind) for s in res.pieces}


def main():
    rclpy.init()
    n = Runner()
    ex = rclpy.executors.MultiThreadedExecutor()
    ex.add_node(n)
    threading.Thread(target=ex.spin, daemon=True).start()
    results = []

    def check(name, cond, detail=''):
        results.append((name, bool(cond)))
        print(f'{"PASS" if cond else "FAIL"}  {name}  {detail}')

    r = n.call(n.new_game, Trigger.Request())
    check('reset board', r.success, r.message)

    r = n.execute('capture', [pm('black_pawn_d7', 'd7', op=R), pm('white_knight_g1', 'g1', 'f3')])
    s = n.squares()
    check('capture: victim to graveyard + mover placed',
          r.success and s['black_pawn_d7'][1] and s['white_knight_g1'][0] == 'f3', r.message)

    r = n.execute('clear f1', [pm('white_bishop_f1', 'f1', 'c4')])
    r = n.execute('castle', [pm('white_king_e1', 'e1', 'g1'), pm('white_rook_h1', 'h1', 'f1')]) \
        if r.success else r
    s = n.squares()
    check('castling-style two-piece move',
          r.success and s['white_king_e1'][0] == 'g1' and s['white_rook_h1'][0] == 'f1',
          r.message)

    r = n.execute('promote', [pm('white_pawn_a2', 'a2', 'a4'),
                              pm('white_pawn_a2', 'a4', 'a4', P, 'Q')])
    s = n.squares()
    promo = [pid for pid, v in s.items() if v[0] == 'a4']
    check('promotion swap', r.success and promo and s[promo[0]][2] == 'Q', f'{r.message} {promo}')

    before = n.squares()
    r = n.execute('occupied', [pm('white_pawn_b2', 'b2', 'b1')])
    check('reject move onto occupied square',
          not r.success and r.failure_category == 'INVALID' and n.squares() == before,
          f'{r.failure_stage}/{r.failure_category}: {r.message}')

    r = n.execute('wrong source', [pm('white_pawn_c2', 'c3', 'c4')])
    check('reject wrong source square', not r.success and r.failure_category == 'INVALID',
          r.message)

    r = n.call(n.new_game, Trigger.Request())
    check('reset after scenarios', r.success, r.message)
    fen0 = n.call(n.state, Trigger.Request()).message.split('\n')[0]
    r = n.call(n.submit, SubmitMove.Request(move='e2e5'))
    fen1 = n.call(n.state, Trigger.Request()).message.split('\n')[0]
    check('game rejects illegal move, state unchanged',
          not r.accepted and fen0 == fen1, r.message)

    failed = [k for k, ok in results if not ok]
    print(f'\n{len(results) - len(failed)}/{len(results)} scenarios passed')
    rclpy.try_shutdown()
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
