"""Robot move selection: Stockfish if available, else a documented fallback policy.

Fallback policy (no engine installed): checkmate if available, else the capture
with the highest captured-piece value, else a move giving check, else a random
legal move (seeded for reproducibility). It is weak and exists only so the
robot can play without Stockfish.
"""
import random
import shutil
from typing import Optional

import chess
import chess.engine

VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5,
          chess.QUEEN: 9, chess.KING: 0}


class MoveSelector:
    def __init__(self, engine_path: str = '', think_time: float = 0.5,
                 skill_level: int = 5, seed: int = 0):
        self.think_time = think_time
        self.rng = random.Random(seed)
        self.engine: Optional[chess.engine.SimpleEngine] = None
        path = engine_path or shutil.which('stockfish') or (
            '/usr/games/stockfish' if shutil.which('/usr/games/stockfish') else None)
        if path:
            try:
                self.engine = chess.engine.SimpleEngine.popen_uci(path)
                if 'Skill Level' in self.engine.options:
                    self.engine.configure({'Skill Level': int(skill_level)})
            except Exception:  # noqa: BLE001 - fall back to the simple policy
                self.engine = None
        self.name = 'stockfish' if self.engine else 'fallback-policy'

    def choose(self, board: chess.Board) -> chess.Move:
        if board.is_game_over():
            raise ValueError('game is over')
        if self.engine is not None:
            return self.engine.play(board, chess.engine.Limit(time=self.think_time)).move
        return self._fallback(board)

    def _fallback(self, board: chess.Board) -> chess.Move:
        moves = list(board.legal_moves)
        for m in moves:
            board.push(m)
            mate = board.is_checkmate()
            board.pop()
            if mate:
                return m
        caps = [m for m in moves if board.is_capture(m)]
        if caps:
            def victim(m):
                if board.is_en_passant(m):
                    return VALUES[chess.PAWN]
                return VALUES[board.piece_at(m.to_square).piece_type]
            best = max(victim(m) for m in caps)
            return self.rng.choice([m for m in caps if victim(m) == best])
        checks = [m for m in moves if board.gives_check(m)]
        return self.rng.choice(checks or moves)

    def close(self):
        if self.engine is not None:
            self.engine.quit()
            self.engine = None
