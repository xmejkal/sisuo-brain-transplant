#!/usr/bin/env python3
"""
Do the modules physically fit on the board, and clear of each other?

A plug-in module is drawn as the header it sits on — six pins, 15 x 2.5 mm — while the thing
that actually plugs in is a 29 x 23 mm circuit board standing 12 mm tall. Nothing in the PCB
tools objects to two headers being 8 mm apart; the modules on top would be occupying the same
space. That mistake is only visible once the real bodies are in the model, which is what this
reads: the 3D bodies from the build, checked against each other and against the board outline.

    python3 tools/check-module-clearance.py

It reports overlaps and overhangs. It does not fail the build — placement is a judgement call,
and a module overhanging the edge can be exactly what you meant.
"""

import json
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MODEL = REPO / "board.glb"

CIRCUIT = REPO / "dist" / "board" / "circuit.json"
IGNORE_BELOW_MM = 3.0     # passives; their bodies are smaller than their pads
CLEARANCE_MM = 0.5        # touching is not fitting


def read_gltf(path):
    data = path.read_bytes()
    if data[:4] != b"glTF":
        raise SystemExit(f"{path} is not a binary glTF")
    offset, chunks = 12, {}
    while offset < len(data):
        length, kind = struct.unpack_from("<II", data, offset)
        chunks["json" if kind == 0x4E4F534A else "bin"] = data[offset + 8: offset + 8 + length]
        offset += 8 + length + (-length % 4)
    return json.loads(chunks["json"])


def footprints(gltf):
    """Each body as a name and its footprint on the board: (x0, y0, x1, y1) in millimetres."""
    for node in gltf.get("nodes", []):
        if "mesh" not in node:
            continue
        low = [float("inf")] * 3
        high = [float("-inf")] * 3
        for primitive in gltf["meshes"][node["mesh"]].get("primitives", []):
            accessor = gltf["accessors"][primitive["attributes"]["POSITION"]]
            for axis in range(3):
                low[axis] = min(low[axis], accessor["min"][axis])
                high[axis] = max(high[axis], accessor["max"][axis])

        scale = node.get("scale", [1, 1, 1])
        translation = node.get("translation", [0, 0, 0])
        # glTF is Y-up; the board lies in X/Z, so those are the two that matter here.
        box = []
        for axis in (0, 2):
            box.append(low[axis] * scale[axis] + translation[axis])
            box.append(high[axis] * scale[axis] + translation[axis])
        size = (box[1] - box[0], box[3] - box[2])
        name = node.get("name", "?")
        if max(size) < IGNORE_BELOW_MM or name.startswith("Box"):
            continue
        yield name, (box[0], box[2], box[1], box[3]), size


def overlap(a, b):
    """How far two footprints intrude on each other, in each axis. Both positive means a clash."""
    return (
        min(a[2], b[2]) - max(a[0], b[0]) - CLEARANCE_MM,
        min(a[3], b[3]) - max(a[1], b[1]) - CLEARANCE_MM,
    )


def board_size():
    """The outline, taken from the build rather than repeated here — it changes with the layout."""
    if not CIRCUIT.exists():
        raise SystemExit("no dist/board/circuit.json — run `make` first")
    for element in json.loads(CIRCUIT.read_text()):
        if element["type"] == "pcb_board":
            return float(element["width"]), float(element["height"])
    raise SystemExit("circuit.json has no pcb_board")


def main():
    if not MODEL.exists():
        raise SystemExit("no board.glb — run `make` first")

    board_width, board_height = board_size()
    parts = list(footprints(read_gltf(MODEL)))
    print(f"{len(parts)} module bodies, board {board_width:.0f} x {board_height:.0f} mm\n")

    half_width, half_height = board_width / 2, board_height / 2
    problems = 0

    for name, box, size in sorted(parts):
        over_x = max(0.0, -half_width - box[0], box[2] - half_width)
        over_y = max(0.0, -half_height - box[1], box[3] - half_height)
        flag = ""
        if over_x or over_y:
            flag = f"   overhangs the edge by {max(over_x, over_y):.1f} mm"
            problems += 1
        print(f"  {name:<16} {size[0]:5.1f} x {size[1]:5.1f} mm{flag}")

    print()
    for index, (name, box, _) in enumerate(sorted(parts)):
        for other_name, other_box, _ in sorted(parts)[index + 1:]:
            intrusion = overlap(box, other_box)
            if intrusion[0] > 0 and intrusion[1] > 0:
                print(f"  {name} and {other_name} occupy the same space "
                      f"({min(intrusion):.1f} mm of overlap)")
                problems += 1

    print(f"\n{problems} thing(s) to look at" if problems else "\nnothing overlaps, nothing hangs off")
    return 0


if __name__ == "__main__":
    sys.exit(main())
