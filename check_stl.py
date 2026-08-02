import struct

filename = "/home/shubham/robot_arm_ws/src/robot_description/meshes/Base_Link.stl"

with open(filename, "rb") as f:
    f.read(80)
    tri_count = struct.unpack("<I", f.read(4))[0]

    print("Triangles:", tri_count)

    minx = miny = minz = float("inf")
    maxx = maxy = maxz = float("-inf")

    for i in range(tri_count):
        f.read(12)

        for j in range(3):
            data = f.read(12)
            if len(data) != 12:
                print("EOF at triangle", i, "vertex", j)
                raise SystemExit

            x, y, z = struct.unpack("<fff", data)

            minx = min(minx, x)
            maxx = max(maxx, x)

            miny = min(miny, y)
            maxy = max(maxy, y)

            minz = min(minz, z)
            maxz = max(maxz, z)

        f.read(2)

print("X:", minx, maxx)
print("Y:", miny, maxy)
print("Z:", minz, maxz)
print("Size:", maxx-minx, maxy-miny, maxz-minz)
