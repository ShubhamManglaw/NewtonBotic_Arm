"""Board geometry: square names <-> chessboard_frame <-> world.

Pure Python (no ROS imports) so it is unit-testable and reusable by every node.
"""
import math
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import yaml

FILES = 'abcdefgh'
PIECE_NAMES = {'P': 'pawn', 'R': 'rook', 'N': 'knight', 'B': 'bishop',
               'Q': 'queen', 'K': 'king'}
START_BACK_RANK = 'RNBQKBNR'


def default_config_path() -> str:
    try:
        from ament_index_python.packages import get_package_share_directory
        return os.path.join(get_package_share_directory('chess_simulation'),
                            'config', 'board.yaml')
    except Exception:  # running from source tree (tests)
        return os.path.join(os.path.dirname(__file__), '..', 'config', 'board.yaml')


def parse_square(square: str) -> Tuple[int, int]:
    """'e4' -> (file_index 4, rank_index 3). Raises ValueError if invalid."""
    if len(square) != 2 or square[0] not in FILES or square[1] not in '12345678':
        raise ValueError(f'invalid square {square!r}')
    return FILES.index(square[0]), int(square[1]) - 1


def square_name(file_idx: int, rank_idx: int) -> str:
    if not (0 <= file_idx < 8 and 0 <= rank_idx < 8):
        raise ValueError(f'invalid indices {file_idx},{rank_idx}')
    return FILES[file_idx] + str(rank_idx + 1)


@dataclass(frozen=True)
class PieceSpec:
    piece_id: str      # unique, stable: e.g. 'white_pawn_e2', 'black_queen_promo1'
    color: str         # 'white' | 'black'
    kind: str          # 'P','R','N','B','Q','K'
    square: str        # current square

    @property
    def symbol(self) -> str:   # python-chess style symbol
        return self.kind if self.color == 'white' else self.kind.lower()


class BoardGeometry:
    def __init__(self, cfg: Optional[Dict] = None, path: Optional[str] = None):
        if cfg is None:
            with open(path or default_config_path()) as f:
                cfg = yaml.safe_load(f)
        self.cfg = cfg
        b = cfg['board']
        self.s = float(b['square_size'])
        self.thickness = float(b['thickness'])
        self.border = float(b['border'])
        self.x0 = float(b['pose']['x'])
        self.y0 = float(b['pose']['y'])
        self.yaw = float(b['pose']['yaw'])
        self.pieces = cfg['pieces']
        self.graveyard = cfg['graveyard']

    # ----------------------------------------------------------- transforms
    @property
    def top_z(self) -> float:
        return self.thickness

    @property
    def size(self) -> float:
        return 8 * self.s + 2 * self.border

    def square_to_board(self, square: str) -> Tuple[float, float]:
        f, r = parse_square(square)
        return (f - 3.5) * self.s, (r - 3.5) * self.s

    def board_to_world(self, x: float, y: float, z: float = 0.0) -> Tuple[float, float, float]:
        c, s = math.cos(self.yaw), math.sin(self.yaw)
        return (self.x0 + c * x - s * y, self.y0 + s * x + c * y, self.top_z + z)

    def world_to_board(self, x: float, y: float) -> Tuple[float, float]:
        dx, dy = x - self.x0, y - self.y0
        c, s = math.cos(self.yaw), math.sin(self.yaw)
        return c * dx + s * dy, -s * dx + c * dy

    def square_world(self, square: str, z: float = 0.0) -> Tuple[float, float, float]:
        """World XYZ of a square centre, z measured above the board top."""
        return self.board_to_world(*self.square_to_board(square), z)

    def world_to_square(self, x: float, y: float, tol: Optional[float] = None) -> Optional[str]:
        """Nearest square to a world XY, or None if off-board / farther than tol."""
        bx, by = self.world_to_board(x, y)
        f = round(bx / self.s + 3.5)
        r = round(by / self.s + 3.5)
        if not (0 <= f < 8 and 0 <= r < 8):
            return None
        cx, cy = (f - 3.5) * self.s, (r - 3.5) * self.s
        if tol is not None and math.hypot(bx - cx, by - cy) > tol:
            return None
        return square_name(f, r)

    def graveyard_world(self, color: str, index: int) -> Tuple[float, float, float]:
        """Slot for the index-th captured piece of `color` (0..15), beside the board.

        White's captured pieces go off the a-file side, black's off the h-file side.
        """
        if not 0 <= index < 16:
            raise ValueError('graveyard index out of range')
        col, row = divmod(index, 8)
        side = -1.0 if color == 'white' else 1.0
        bx = side * (4 * self.s + self.border + self.graveyard['gap']
                     + col * self.graveyard['spacing'])
        by = float(self.graveyard['first_row_y']) - row * self.graveyard['spacing']
        return self.board_to_world(bx, by, 0.0)

    # ------------------------------------------------------------- pieces
    def piece_height(self, kind: str) -> float:
        return float(self.pieces['height'][kind.upper()])

    @property
    def grasp_height(self) -> float:
        return float(self.pieces['grasp_height'])

    @staticmethod
    def starting_pieces() -> List[PieceSpec]:
        out = []
        for color, back, pawn in (('white', 0, 1), ('black', 7, 6)):
            for f, kind in enumerate(START_BACK_RANK):
                sq = square_name(f, back)
                out.append(PieceSpec(f'{color}_{PIECE_NAMES[kind]}_{sq}', color, kind, sq))
            for f in range(8):
                sq = square_name(f, pawn)
                out.append(PieceSpec(f'{color}_pawn_{sq}', color, 'P', sq))
        return out
