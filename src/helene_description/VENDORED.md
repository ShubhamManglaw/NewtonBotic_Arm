# Vendored: helene_description

Source: `github.com/ShubhamManglaw/helene_description` (private), commit `bf83584bc2dc624cab1a6d581757056f0691b5a9`.

Copied unmodified:
- `urdf/helene_description.xacro`: **generated** (by the source repo's `tools/build_description.py`). Do not edit.
- `urdf/materials.xacro`
- `meshes/visual/*.stl`, `meshes/collision/*.stl`: **generated**, in millimetres, scaled 0.001 in the xacro.

Deliberately **not** copied: `fusion/`, `tools/` (CAD export and generator), `launch/`, `scripts/`,
`rviz/`, `config/`, `worlds/` and the source `package.xml`/`CMakeLists.txt`. This project has its
own launch files, ros2_control (`robot_description/urdf/arm.ros2_control.xacro`), controllers
(`robot_bringup/config/controllers.yaml`) and chess world (`chess_simulation`).
`package.xml` and `CMakeLists.txt` here are minimal and project-owned.

To update after the model is regenerated in the source repo:

    tools/sync_helene_description.sh /path/to/helene_description

The package keeps the name `helene_description` so the generated
`package://helene_description/meshes/...` URIs resolve without edits.
