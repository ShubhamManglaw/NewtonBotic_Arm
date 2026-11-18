import argparse
import struct
from pathlib import Path


def check_stl(filename: Path) -> None:
    minx = miny = minz = float("inf")
    maxx = maxy = maxz = float("-inf")

    with filename.open("rb") as f:
        f.read(80)

        count_data = f.read(4)
        if len(count_data) != 4:
            raise ValueError("Invalid STL file: missing triangle count.")

        triangle_count = struct.unpack("<I", count_data)[0]

        for i in range(triangle_count):
            normal = f.read(12)
            if len(normal) != 12:
                raise ValueError(
                    f"Unexpected EOF at triangle {i}: missing normal."
                )

            for j in range(3):
                data = f.read(12)

                if len(data) != 12:
                    raise ValueError(
                        f"Unexpected EOF at triangle {i}, vertex {j}."
                    )

                x, y, z = struct.unpack("<fff", data)

                minx = min(minx, x)
                maxx = max(maxx, x)

                miny = min(miny, y)
                maxy = max(maxy, y)

                minz = min(minz, z)
                maxz = max(maxz, z)

            attribute_data = f.read(2)
            if len(attribute_data) != 2:
                raise ValueError(
                    f"Unexpected EOF at triangle {i}: missing attribute data."
                )

    print(f"STL: {filename}")
    print(f"Triangles: {triangle_count}")
    print(f"X: {minx} {maxx}")
    print(f"Y: {miny} {maxy}")
    print(f"Z: {minz} {maxz}")
    print(f"Size: {maxx - minx} {maxy - miny} {maxz - minz}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect a binary STL file and report its geometry bounds."
    )

    parser.add_argument(
        "stl_file",
        type=Path,
        help="Path to the binary STL file.",
    )

    args = parser.parse_args()

    if not args.stl_file.is_file():
        parser.error(f"STL file does not exist: {args.stl_file}")

    check_stl(args.stl_file)


if __name__ == "__main__":
    main()