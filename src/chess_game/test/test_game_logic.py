from types import SimpleNamespace

import chess
import pytest

from chess_game.engine import MoveSelector
from chess_game.game_logic import (MOVE, REMOVE, REPLACE, ChessGame, MoveError,
                                   occupancy, physical_maps)


def play(g, *moves):
    for m in moves:
        g.commit(g.parse_move(m))


def test_parse_uci_and_san():
    g = ChessGame()
    assert g.parse_move('e2e4') == chess.Move.from_uci('e2e4')
    assert g.parse_move('Nf3') == chess.Move.from_uci('g1f3')
    assert g.parse_move(' E2E4 ') == chess.Move.from_uci('e2e4')


@pytest.mark.parametrize('bad', ['', 'e2e5', 'Ke2', 'xyz', 'e7e5', 'Nf6'])
def test_illegal_rejected(bad):
    g = ChessGame()
    with pytest.raises(MoveError):
        g.parse_move(bad)
    assert g.board.fen() == chess.STARTING_FEN   # state untouched


def test_ordinary_move_plan_and_commit():
    g = ChessGame()
    m = g.parse_move('e2e4')
    assert g.plan(m) == [type(g.plan(m)[0])('white_pawn_e2', 'e2', 'e4', MOVE)]
    g.commit(m)
    assert g.piece_at['e4'] == 'white_pawn_e2' and 'e2' not in g.piece_at


def test_capture_removes_victim_first():
    g = ChessGame()
    play(g, 'e4', 'd5')
    steps = g.plan(g.parse_move('exd5'))
    assert [(s.operation, s.piece_id) for s in steps] == [
        (REMOVE, 'black_pawn_d7'), (MOVE, 'white_pawn_e2')]
    g.commit(g.parse_move('exd5'))
    assert g.piece_at['d5'] == 'white_pawn_e2'
    assert 'black_pawn_d7' not in g.piece_at.values()


def test_en_passant():
    g = ChessGame()
    play(g, 'e4', 'a6', 'e5', 'd5')
    steps = g.plan(g.parse_move('exd6'))
    assert steps[0].operation == REMOVE and steps[0].from_square == 'd5'
    assert steps[1] .operation == MOVE and (steps[1].from_square, steps[1].to_square) == ('e5', 'd6')
    g.commit(g.parse_move('exd6'))
    assert 'd5' not in g.piece_at and g.piece_at['d6'] == 'white_pawn_e2'


@pytest.mark.parametrize('castle,king,rook', [
    ('O-O', ('e1', 'g1'), ('h1', 'f1')),
    ('O-O-O', ('e1', 'c1'), ('a1', 'd1'))])
def test_castling_two_moves(castle, king, rook):
    g = ChessGame()
    play(g, 'e4', 'e5', 'Nf3', 'Nc6', 'Bc4', 'Bc5', 'd4', 'd6', 'Nc3', 'Nf6',
         'Be3', 'Be6', 'Qd2', 'Qd7')
    steps = g.plan(g.parse_move(castle))
    assert [(s.from_square, s.to_square) for s in steps] == [king, rook]
    assert all(s.operation == MOVE for s in steps)
    g.commit(g.parse_move(castle))
    assert g.piece_at[king[1]] == 'white_king_e1'
    assert g.piece_at[rook[1]] == f'white_rook_{rook[0]}'


def test_promotion_with_capture():
    g = ChessGame(fen='1n5k/P7/8/8/8/8/8/K7 w - - 0 1')
    g.piece_at = {'b8': 'black_knight_b8', 'a7': 'white_pawn_a2', 'h8': 'black_king_e8',
                  'a1': 'white_king_e1'}
    steps = g.plan(g.parse_move('a7b8q'))
    assert [(s.operation, s.piece_id) for s in steps] == [
        (REMOVE, 'black_knight_b8'), (MOVE, 'white_pawn_a2'), (REPLACE, 'white_pawn_a2')]
    assert steps[-1].promotion == 'Q' and steps[-1].to_square == 'b8'
    exp = g.expected_after(g.parse_move('a7b8q'))
    assert exp['b8'] == 'Q' and 'a7' not in exp


def test_compare_and_physical_maps():
    g = ChessGame()
    m = g.parse_move('e4')
    exp = g.expected_after(m)
    st = lambda pid, c, k, sq, up=True, gy=False: SimpleNamespace(  # noqa: E731
        piece_id=pid, color=c, kind=k, square=sq, upright=up, in_graveyard=gy)
    states = []
    for sq, pid in g.piece_at.items():
        color, kind = pid.split('_')[0], g.board.piece_at(chess.parse_square(sq)).symbol().upper()
        states.append(st(pid, color, kind, 'e4' if sq == 'e2' else sq))
    occ, ids, problems = physical_maps(states)
    assert not problems and g.compare(exp, occ) == []
    states[0] = st(states[0].piece_id, states[0].color, states[0].kind, states[0].square, up=False)
    _, _, problems = physical_maps(states)
    assert problems


def test_status():
    g = ChessGame()
    play(g, 'f3', 'e5', 'g4', 'Qh4')
    assert g.status() == 'CHECKMATE' and 'black wins' in g.result_text()


def test_fallback_policy_prefers_mate_and_captures():
    sel = MoveSelector(engine_path='/nonexistent')
    sel.engine = None
    b = chess.Board()
    for m in ['f3', 'e5', 'g4']:
        b.push_san(m)
    assert b.san(sel._fallback(b)) == 'Qh4#'
    b = chess.Board('k7/8/8/3q4/4P3/8/8/K7 w - - 0 1')
    assert sel._fallback(b).uci() == 'e4d5'
    assert occupancy(chess.Board())['e1'] == 'K'
