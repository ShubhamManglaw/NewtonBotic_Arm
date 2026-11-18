#!/usr/bin/env python3
"""Generate simplified collision meshes from the CAD visual meshes.

The CAD STLs (~917k triangles total) are far too dense for Gazebo contact
and MoveIt collision checking. This writes one convex hull per link into
``meshes/collision/`` in the SAME link frame as the visual mesh, so the
URDF can reuse the visual <origin> unchanged. CAD meshes are not modified.

Usage:
    python3 tools/make_collision_meshes.py [path/to/robot_description]
"""
import sys
from pathlib import Path

import trimesh


def main() -> None:
    pkg = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        Path(__file__).resolve().parent.parent / 'src' / 'robot_description')
    src = pkg / 'meshes'
    dst = src / 'collision'
    dst.mkdir(exist_ok=True)
    for stl in sorted(src.glob('*.STL')):
        mesh = trimesh.load(stl)
        hull = mesh.convex_hull
        out = dst / (stl.stem + '.stl')
        hull.export(out)
        print(f'{stl.name}: {len(mesh.faces)} -> {len(hull.faces)} faces -> {out}')


if __name__ == '__main__':
    main()
