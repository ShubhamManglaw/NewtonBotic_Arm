#!/usr/bin/env bash
# Re-vendor the generated HELENE model files from a helene_description checkout.
# Usage: tools/sync_helene_description.sh /path/to/helene_description
set -euo pipefail
SRC=${1:?path to helene_description checkout}
DST="$(cd "$(dirname "$0")/.." && pwd)/src/helene_description"
cp "$SRC/urdf/helene_description.xacro" "$SRC/urdf/materials.xacro" "$DST/urdf/"
rm -rf "$DST/meshes/visual" "$DST/meshes/collision"
cp -r "$SRC/meshes/visual" "$SRC/meshes/collision" "$DST/meshes/"
SHA=$(git -C "$SRC" rev-parse HEAD)
sed -i "s/commit \`[0-9a-f]*\`/commit \`$SHA\`/" "$DST/VENDORED.md"
echo "synced helene_description @ $SHA -> $DST (review joint/link changes before committing)"
