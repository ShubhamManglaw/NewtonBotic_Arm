"""Generate the Gazebo Sim chess world (SDF 1.9) from config/board.yaml.

The world is generated rather than hand-written so square coordinates come from
the same BoardGeometry used by the manipulation layer.

  ros2 run chess_simulation generate_world -o /tmp/chess.sdf
"""
import argparse
from typing import Optional, Tuple

from chess_simulation.board import BoardGeometry, PieceSpec

WORLD_NAME = 'chess_world'
LIGHT_SQ = (0.93, 0.85, 0.70, 1.0)
DARK_SQ = (0.45, 0.30, 0.20, 1.0)
FRAME = (0.30, 0.18, 0.10, 1.0)


def _rgba(c):
    return ' '.join(f'{v:.3f}' for v in c)


def _material(c):
    return (f'<material><ambient>{_rgba(c)}</ambient><diffuse>{_rgba(c)}</diffuse>'
            f'<specular>0.1 0.1 0.1 1</specular></material>')


def _cyl_inertia(m, r, h):
    ixx = m * (3 * r * r + h * h) / 12.0
    return ixx, ixx, m * r * r / 2.0


def _surface(mu, kp=1e5, kd=1.0):
    # High-friction, moderately stiff contacts so pure-friction grasps can hold.
    return (f'<surface><friction><ode><mu>{mu}</mu><mu2>{mu}</mu2></ode>'
            f'<torsional><coefficient>0.05</coefficient></torsional></friction>'
            f'<contact><ode><kp>{kp}</kp><kd>{kd}</kd><max_vel>0.05</max_vel>'
            f'<min_depth>0.0005</min_depth></ode></contact></surface>')


def piece_model_sdf(geo: BoardGeometry, spec: PieceSpec,
                    xyz: Optional[Tuple[float, float, float]] = None,
                    yaw: float = 0.0, include_pose: bool = True) -> str:
    """SDF <model> for one piece. Origin = centre of the piece's base, on the board."""
    p = geo.pieces
    rb, hb = p['base_radius'], p['base_height']
    rbody = p['body_radius']
    h = geo.piece_height(spec.kind)
    hbody = h - hb
    mass = p['mass']
    mu = p['friction']
    color = p['color'][spec.color]
    if xyz is None:
        xyz = geo.square_world(spec.square)
    # Inertia of the body cylinder, located at its own centre (good enough, stable).
    ixx, iyy, izz = _cyl_inertia(mass, rb, h)
    head = _head_visual(spec.kind, rbody, h, color)
    pose = (f'<pose>{xyz[0]:.5f} {xyz[1]:.5f} {xyz[2]:.5f} 0 0 {yaw:.5f}</pose>'
            if include_pose else '')
    return f"""
    <model name="{spec.piece_id}">
      {pose}
      <link name="link">
        <inertial>
          <pose>0 0 {h * 0.4:.4f} 0 0 0</pose>
          <mass>{mass}</mass>
          <inertia><ixx>{ixx:.3e}</ixx><iyy>{iyy:.3e}</iyy><izz>{izz:.3e}</izz>
            <ixy>0</ixy><ixz>0</ixz><iyz>0</iyz></inertia>
        </inertial>
        <collision name="base_col">
          <pose>0 0 {hb / 2:.4f} 0 0 0</pose>
          <geometry><cylinder><radius>{rb}</radius><length>{hb}</length></cylinder></geometry>
          {_surface(mu)}
        </collision>
        <collision name="body_col">
          <pose>0 0 {hb + hbody / 2:.4f} 0 0 0</pose>
          <geometry><cylinder><radius>{rbody}</radius><length>{hbody:.4f}</length></cylinder></geometry>
          {_surface(mu)}
        </collision>
        <visual name="base">
          <pose>0 0 {hb / 2:.4f} 0 0 0</pose>
          <geometry><cylinder><radius>{rb}</radius><length>{hb}</length></cylinder></geometry>
          {_material(color)}
        </visual>
        <visual name="body">
          <pose>0 0 {hb + hbody / 2:.4f} 0 0 0</pose>
          <geometry><cylinder><radius>{rbody}</radius><length>{hbody:.4f}</length></cylinder></geometry>
          {_material(color)}
        </visual>
        {head}
      </link>
    </model>"""


def _head_visual(kind, r, h, color):
    """Visual-only head so piece types are distinguishable. Collision stays simple."""
    mat = _material(color)
    if kind == 'P':
        geom, z = f'<sphere><radius>{r * 1.25:.4f}</radius></sphere>', h
    elif kind == 'R':
        geom, z = (f'<cylinder><radius>{r * 1.35:.4f}</radius><length>0.008</length>'
                   '</cylinder>'), h - 0.002
    elif kind == 'N':
        return (f'<visual name="head"><pose>{r * 0.5:.4f} 0 {h - 0.004:.4f} 0 0.6 0</pose>'
                f'<geometry><box><size>{r * 2.6:.4f} {r * 1.4:.4f} 0.010</size></box>'
                f'</geometry>{mat}</visual>')
    elif kind == 'B':
        return (f'<visual name="head"><pose>0 0 {h - 0.003:.4f} 0 0 0</pose>'
                f'<geometry><ellipsoid><radii>{r * 1.1:.4f} {r * 1.1:.4f} {r * 1.7:.4f}'
                f'</radii></ellipsoid></geometry>{mat}</visual>')
    elif kind == 'Q':
        geom, z = f'<sphere><radius>{r * 1.45:.4f}</radius></sphere>', h - 0.002
    else:  # King: box cross on top
        return (f'<visual name="head_v"><pose>0 0 {h + 0.002:.4f} 0 0 0</pose>'
                f'<geometry><box><size>0.004 0.004 0.014</size></box></geometry>{mat}</visual>'
                f'<visual name="head_h"><pose>0 0 {h + 0.004:.4f} 0 0 0</pose>'
                f'<geometry><box><size>0.012 0.004 0.004</size></box></geometry>{mat}</visual>'
                f'<visual name="collar"><pose>0 0 {h - 0.004:.4f} 0 0 0</pose>'
                f'<geometry><cylinder><radius>{r * 1.3:.4f}</radius><length>0.006</length>'
                f'</cylinder></geometry>{mat}</visual>')
    return (f'<visual name="head"><pose>0 0 {z:.4f} 0 0 0</pose><geometry>{geom}</geometry>'
            f'{mat}</visual>')


def board_model_sdf(geo: BoardGeometry) -> str:
    s, t, size = geo.s, geo.thickness, geo.size
    squares = []
    for sq_f in range(8):
        for sq_r in range(8):
            bx, by = (sq_f - 3.5) * s, (sq_r - 3.5) * s
            dark = (sq_f + sq_r) % 2 == 0       # a1 is dark
            # 1 mm tiles spanning t-0.9 mm .. t+0.1 mm, i.e. just above the frame
            # visual (top at t-1 mm) so they are not hidden inside it.
            squares.append(
                f'<visual name="sq_{"abcdefgh"[sq_f]}{sq_r + 1}">'
                f'<pose>{bx:.4f} {by:.4f} {t - 0.0004:.4f} 0 0 0</pose>'
                f'<geometry><box><size>{s:.4f} {s:.4f} 0.001</size></box></geometry>'
                f'{_material(DARK_SQ if dark else LIGHT_SQ)}</visual>')
    return f"""
    <model name="chessboard">
      <static>true</static>
      <pose>{geo.x0:.5f} {geo.y0:.5f} 0 0 0 {geo.yaw:.6f}</pose>
      <link name="link">
        <collision name="board">
          <pose>0 0 {t / 2:.4f} 0 0 0</pose>
          <geometry><box><size>{size:.4f} {size:.4f} {t}</size></box></geometry>
          {_surface(0.6, kp=1e6)}
        </collision>
        <visual name="frame">
          <pose>0 0 {t / 2 - 0.0005:.4f} 0 0 0</pose>
          <geometry><box><size>{size:.4f} {size:.4f} {t - 0.001:.4f}</size></box></geometry>
          {_material(FRAME)}
        </visual>
        {''.join(squares)}
      </link>
    </model>"""


def graveyard_model_sdf(geo: BoardGeometry) -> str:
    """Thin static trays under the graveyard slots (visual guide + flat surface)."""
    out = []
    for color in ('white', 'black'):
        xs = [geo.graveyard_world(color, i) for i in range(16)]
        cx = sum(p[0] for p in xs) / 16
        cy = sum(p[1] for p in xs) / 16
        w = max(p[0] for p in xs) - min(p[0] for p in xs) + 0.03
        lgt = max(p[1] for p in xs) - min(p[1] for p in xs) + 0.03
        out.append(f"""
    <model name="graveyard_{color}">
      <static>true</static>
      <pose>{cx:.4f} {cy:.4f} 0 0 0 0</pose>
      <link name="link">
        <collision name="col"><pose>0 0 {geo.thickness / 2:.4f} 0 0 0</pose>
          <geometry><box><size>{w:.4f} {lgt:.4f} {geo.thickness}</size></box></geometry>
          {_surface(0.6, kp=1e6)}</collision>
        <visual name="v"><pose>0 0 {geo.thickness / 2:.4f} 0 0 0</pose>
          <geometry><box><size>{w:.4f} {lgt:.4f} {geo.thickness}</size></box></geometry>
          {_material((0.25, 0.35, 0.25, 1))}</visual>
      </link>
    </model>""")
    return ''.join(out)


def world_sdf(geo: BoardGeometry, with_pieces: bool = True) -> str:
    pieces = ''.join(piece_model_sdf(geo, p) for p in geo.starting_pieces()) \
        if with_pieces else ''
    return f"""<?xml version="1.0"?>
<!-- GENERATED by chess_simulation/world_gen.py from config/board.yaml. Do not edit. -->
<sdf version="1.9">
  <world name="{WORLD_NAME}">
    <physics name="1ms" type="ignored">
      <max_step_size>0.001</max_step_size>
      <real_time_factor>1.0</real_time_factor>
    </physics>
    <plugin filename="gz-sim-physics-system" name="gz::sim::systems::Physics"/>
    <plugin filename="gz-sim-user-commands-system" name="gz::sim::systems::UserCommands"/>
    <plugin filename="gz-sim-scene-broadcaster-system" name="gz::sim::systems::SceneBroadcaster"/>
    <plugin filename="gz-sim-contact-system" name="gz::sim::systems::Contact"/>

    <gravity>0 0 -9.81</gravity>
    <scene>
      <ambient>0.5 0.5 0.5 1</ambient>
      <background>0.75 0.8 0.85 1</background>
      <grid>false</grid>
    </scene>

    <light type="directional" name="sun">
      <cast_shadows>true</cast_shadows>
      <pose>0 0 3 0 0 0</pose>
      <diffuse>0.9 0.9 0.9 1</diffuse>
      <specular>0.2 0.2 0.2 1</specular>
      <direction>-0.3 0.2 -0.9</direction>
    </light>

    <model name="ground_plane">
      <static>true</static>
      <link name="link">
        <collision name="collision">
          <geometry><plane><normal>0 0 1</normal><size>4 4</size></plane></geometry>
          {_surface(0.8, kp=1e6)}
        </collision>
        <visual name="visual">
          <geometry><plane><normal>0 0 1</normal><size>4 4</size></plane></geometry>
          {_material((0.7, 0.7, 0.7, 1))}
        </visual>
      </link>
    </model>
{board_model_sdf(geo)}
{graveyard_model_sdf(geo)}
{pieces}
  </world>
</sdf>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-o', '--output', required=True)
    ap.add_argument('--config', default=None)
    ap.add_argument('--no-pieces', action='store_true')
    a = ap.parse_args()
    geo = BoardGeometry(path=a.config)
    with open(a.output, 'w') as f:
        f.write(world_sdf(geo, with_pieces=not a.no_pieces))
    print(a.output)


if __name__ == '__main__':
    main()


