import math

import pytest

from chess_simulation.board import BoardGeometry, parse_square, square_name


@pytest.fixture
def geo():
    return BoardGeometry()


def test_parse_roundtrip():
    for f in range(8):
        for r in range(8):
            assert parse_square(square_name(f, r)) == (f, r)
    for bad in ['i1', 'a9', 'a0', 'e', 'e44', '']:
        with pytest.raises(ValueError):
            parse_square(bad)


def test_square_spacing_and_orientation(geo):
    s = geo.s
    a1, h1, a8 = (geo.square_world(q) for q in ('a1', 'h1', 'a8'))
    assert math.dist(a1[:2], h1[:2]) == pytest.approx(7 * s)
    assert math.dist(a1[:2], a8[:2]) == pytest.approx(7 * s)
    # adjacent squares exactly one square apart
    assert math.dist(geo.square_world('e4')[:2], geo.square_world('e5')[:2]) == pytest.approx(s)
    # board centre is between d4/e5
    mid = [(geo.square_world('d4')[i] + geo.square_world('e5')[i]) / 2 for i in range(2)]
    assert mid == pytest.approx([geo.x0, geo.y0])
    assert a1[2] == pytest.approx(geo.top_z)


def test_robot_side_is_rank8(geo):
    # Robot base is at world origin; with yaw=pi the 8th rank is closest to it.
    d8 = math.hypot(*geo.square_world('d8')[:2])
    d1 = math.hypot(*geo.square_world('d1')[:2])
    assert d8 < d1


def test_world_to_square_inverse(geo):
    for f in range(8):
        for r in range(8):
            sq = square_name(f, r)
            x, y, _ = geo.square_world(sq)
            assert geo.world_to_square(x, y) == sq
            assert geo.world_to_square(x + 0.4 * geo.s, y - 0.4 * geo.s) == sq
    assert geo.world_to_square(10.0, 10.0) is None
    x, y, _ = geo.square_world('e4')
    assert geo.world_to_square(x + 0.45 * geo.s, y, tol=0.3 * geo.s) is None


def test_graveyard_off_board_and_unique(geo):
    slots = set()
    for color in ('white', 'black'):
        for i in range(16):
            x, y, _ = geo.graveyard_world(color, i)
            assert geo.world_to_square(x, y) is None
            slots.add((round(x, 4), round(y, 4)))
    assert len(slots) == 32
    with pytest.raises(ValueError):
        geo.graveyard_world('white', 16)


def test_starting_pieces(geo):
    pieces = BoardGeometry.starting_pieces()
    assert len(pieces) == 32
    assert len({p.piece_id for p in pieces}) == 32
    assert len({p.square for p in pieces}) == 32
    by_sq = {p.square: p for p in pieces}
    assert by_sq['e1'].symbol == 'K' and by_sq['d8'].symbol == 'q'
    assert by_sq['b1'].symbol == 'N' and by_sq['h7'].symbol == 'p'
    assert by_sq['e2'].piece_id == 'white_pawn_e2'
