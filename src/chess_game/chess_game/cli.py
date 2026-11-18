"""Interactive terminal client: type moves, watch the robot reply.

  ros2 run chess_game play
Commands: a move (e2e4 / Nf3 / O-O), 'board', 'new', 'go' (robot moves when it is
white), 'quit'.
"""
import rclpy
from rclpy.node import Node
from std_srvs.srv import Trigger

from chess_interfaces.srv import SubmitMove


def main():
    rclpy.init()
    node = Node('chess_cli')
    submit = node.create_client(SubmitMove, '/chess_game/submit_move')
    state = node.create_client(Trigger, '/chess_game/state')
    new = node.create_client(Trigger, '/chess_game/new_game')

    def call(cli, req):
        if not cli.wait_for_service(timeout_sec=10.0):
            print(f'service {cli.srv_name} unavailable')
            return None
        fut = cli.call_async(req)
        rclpy.spin_until_future_complete(node, fut)
        return fut.result()

    print(__doc__)
    r = call(state, Trigger.Request())
    if r:
        print(r.message)
    try:
        while True:
            text = input('\nyour move> ').strip()
            if text in ('quit', 'exit', 'q'):
                break
            if text == 'board':
                r = call(state, Trigger.Request())
                print(r.message if r else '')
                continue
            if text == 'new':
                r = call(new, Trigger.Request())
                print(r.message if r else '')
                continue
            print('executing... (the robot moves your piece, then replies)')
            r = call(submit, SubmitMove.Request(move=text))
            if r is None:
                continue
            print(('OK: ' if r.accepted else 'REJECTED: ') + r.message)
            r2 = call(state, Trigger.Request())
            if r2:
                print(r2.message)
    except (EOFError, KeyboardInterrupt):
        pass
    node.destroy_node()
    rclpy.try_shutdown()


if __name__ == '__main__':
    main()
