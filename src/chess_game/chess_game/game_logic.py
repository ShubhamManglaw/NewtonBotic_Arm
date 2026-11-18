"""Authoritative chess state + translation of chess moves into physical piece moves.

Pure Python (python-chess, no ROS) so it is unit-testable. The ROS game node
wraps this; the manipulation layer never sees chess rules.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import chess

PIECE_NAMES = {chess.PAWN: 'pawn', chess.KNIGHT: 'knight', chess.BISHOP: 'bishop',
               chess.ROOK: 'rook', chess.QUEEN: 'queen', chess.KING: 'king'}

# Operation codes mirror chess_interfaces/msg/PieceMove.
MOVE, REMOVE, REPLACE = 0, 1, 2


class MoveError(ValueError):
    """Illegal / unparsable move. Message is safe to show the user."""


@dataclass(frozen=True)
class PlannedStep:
    piece_id: str
    from_square: str
    to_square: str
    operation: int
    promotion: str = ''


def initial_piece_ids() -> Dict[str, str]:
    """square -> stable piece id, matching chess_simulation BoardGeometry.starting_pieces."""
    board = chess.Board()
    ids = {}
    for sq, piece in board.piece_map().items():
        name = chess.square_name(sq)
        color = 'white' if piece.color == chess.WHITE else 'black'
        ids[name] = f'{color}_{PIECE_NAMES[piece.piece_type]}_{name}'
    return ids


class ChessGame:
    def __init__(self, robot_color: bool = chess.BLACK, fen: Optional[str] = None):
        self.robot_color = robot_color
        self.board = chess.Board(fen) if fen else chess.Board()
        self.piece_at: Dict[str, str] = initial_piece_ids() if fen is None else {}

    # --------------------------------------------------------------- parsing
    def parse_move(self, text: str) -> chess.Move:
        text = text.strip()
        if not text:
            raise MoveError('empty move')
        move = None
        try:
            move = chess.Move.from_uci(text.lower())
        except ValueError:
            pass
        if move is not None:
            if move not in self.board.legal_moves:
                raise MoveError(f'illegal move {text} in position {self.board.fen()}')
            return move
        try:
            return self.board.parse_san(text)
        except chess.IllegalMoveError:
            raise MoveError(f'illegal move {text}')
        except chess.AmbiguousMoveError:
            raise MoveError(f'ambiguous move {text}; use UCI like e2e4')
        except (chess.InvalidMoveError, ValueError):
            raise MoveError(f'cannot parse {text!r}; use UCI (e2e4) or SAN (Nf3)')

    @property
    def human_to_move(self) -> bool:
        return self.board.turn != self.robot_color

    # -------------------------------------------------------------- planning
    def plan(self, move: chess.Move) -> List[PlannedStep]:
        """Physical relocations needed to realise `move` on the real board, in order."""
        b = self.board
        if move not in b.legal_moves:
            raise MoveError(f'illegal move {move.uci()}')
        frm, to = chess.square_name(move.from_square), chess.square_name(move.to_square)
        mover = self._id(frm)
        steps: List[PlannedStep] = []

        if b.is_en_passant(move):
            cap_sq = chess.square_name(chess.square(chess.square_file(move.to_square),
                                                    chess.square_rank(move.from_square)))
            steps.append(PlannedStep(self._id(cap_sq), cap_sq, '', REMOVE))
        elif b.is_capture(move):
            steps.append(PlannedStep(self._id(to), to, '', REMOVE))

        if b.is_castling(move):
            # python-chess encodes standard castling as king e1g1 / e1c1 etc.
            rank = chess.square_rank(move.from_square)
            kingside = chess.square_file(move.to_square) > chess.square_file(move.from_square)
            r_from = chess.square_name(chess.square(7 if kingside else 0, rank))
            r_to = chess.square_name(chess.square(5 if kingside else 3, rank))
            steps.append(PlannedStep(mover, frm, to, MOVE))
            steps.append(PlannedStep(self._id(r_from), r_from, r_to, MOVE))
            return steps

        steps.append(PlannedStep(mover, frm, to, MOVE))
        if move.promotion:
            steps.append(PlannedStep(mover, to, to, REPLACE,
                                     chess.piece_symbol(move.promotion).upper()))
        return steps

    def _id(self, square: str) -> str:
        if square not in self.piece_at:
            raise MoveError(f'no tracked piece on {square} (state out of sync)')
        return self.piece_at[square]

    # ---------------------------------------------------------- verification
    def expected_after(self, move: chess.Move) -> Dict[str, str]:
        """square -> python-chess symbol ('P', 'n', ...) after `move` is played."""
        b = self.board.copy(stack=False)
        b.push(move)
        return occupancy(b)

    @staticmethod
    def compare(expected: Dict[str, str], physical: Dict[str, str]) -> List[str]:
        """Discrepancies between expected occupancy and observed occupancy."""
        problems = []
        for sq in sorted(set(expected) | set(physical)):
            e, p = expected.get(sq), physical.get(sq)
            if e != p:
                problems.append(f'{sq}: expected {e or "empty"}, found {p or "empty"}')
        return problems

    # ---------------------------------------------------------------- commit
    def commit(self, move: chess.Move, physical_ids: Optional[Dict[str, str]] = None):
        """Apply `move` to the authoritative state.

        physical_ids (square -> piece_id observed in simulation) re-syncs piece
        tracking after execution (needed after promotion, which creates a new id).
        Without it, tracking is updated logically.
        """
        steps = self.plan(move)
        self.board.push(move)
        if physical_ids is not None:
            self.piece_at = dict(physical_ids)
            return
        for st in steps:
            if st.operation == REMOVE:
                self.piece_at.pop(st.from_square, None)
        for st in steps:
            if st.operation == MOVE:
                self.piece_at[st.to_square] = self.piece_at.pop(st.from_square)

    # ---------------------------------------------------------------- status
    def status(self) -> str:
        b = self.board
        if b.is_checkmate():
            return 'CHECKMATE'
        if b.is_stalemate():
            return 'STALEMATE'
        if b.is_insufficient_material() or b.can_claim_draw() or b.is_seventyfive_moves() \
                or b.is_fivefold_repetition():
            return 'DRAW'
        return 'ONGOING'

    def result_text(self) -> str:
        s = self.status()
        if s == 'CHECKMATE':
            winner = 'white' if self.board.turn == chess.BLACK else 'black'
            return f'checkmate, {winner} wins'
        return s.lower()


def occupancy(board: chess.Board) -> Dict[str, str]:
    return {chess.square_name(sq): p.symbol() for sq, p in board.piece_map().items()}


def symbol_for(color: str, kind: str) -> str:
    return kind.upper() if color == 'white' else kind.lower()


def physical_maps(states) -> Tuple[Dict[str, str], Dict[str, str], List[str]]:
    """From PieceState-like objects build (square->symbol, square->piece_id, problems).

    Pieces on the board must be upright and alone on their square. Pieces in the
    graveyard are ignored. Anything else is reported as a problem.
    """
    occ, ids, problems = {}, {}, []
    for s in states:
        if s.in_graveyard:
            continue
        if not s.square:
            problems.append(f'{s.piece_id} is off-board / between squares')
            continue
        if not s.upright:
            problems.append(f'{s.piece_id} on {s.square} is knocked over')
        if s.square in occ:
            problems.append(f'two pieces on {s.square}: {ids[s.square]}, {s.piece_id}')
        occ[s.square] = symbol_for(s.color, s.kind)
        ids[s.square] = s.piece_id
    return occ, ids, problems
