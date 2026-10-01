#!/usr/bin/env python3
"""
Make board-viewer.html from the board's current exports (backlog B4).

The viewer used to be a file made once by hand. On 2026-10-01 it still showed the XIAO board of
2026-09-22, two boards ago, while CLAUDE.md called it the viewer. A picture nobody regenerates is
a picture of the past, so it is a make target now: it is rebuilt whenever the schematic, the PCB,
the 3D model or the netlist is. It states no fact of its own — every figure on the page is read
from dist/board/circuit.json, and the board's name from the resolved board file.

It opens from a download folder with no network: both drawings inline, the GLB embedded, and the
three.js that tscircuit already installs inlined through an import map. That makes it a few
megabytes, so it is NOT committed: like the flash images (8e83dbb) it is derived, `make all` makes
it, and .gitignore keeps it out.

    python3 tools/build-viewer.py      # writes board-viewer.html
"""

import base64
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "tools" / "viewer-template.html"
VIEWER_3D = ROOT / "tools" / "viewer-3d.js"
THREE = ROOT / "node_modules" / "three"
SCHEMATIC = ROOT / "board-sch.svg"
PCB = ROOT / "board-pcb-routed.svg"
MODEL = ROOT / "board.glb"
CIRCUIT = ROOT / "dist" / "board" / "circuit.json"
RESOLVED_BOARD = ROOT / ".spark" / "board.json"
OUTPUT = ROOT / "board-viewer.html"

#: Each module the 3D tab imports: the name the import map gives it, the file it is under
#: node_modules/three, and the import specifiers rewritten in it. A relative import cannot resolve
#: inside a data: URL, so the two relative imports three.js has are pointed at these names — the
#: only edits made to three.js's own files, and each must match or the build stops.
MODULES = {
    "three": ("build/three.module.min.js",
              {'from"./three.core.min.js"': 'from"three/core"'}),
    "three/core": ("build/three.core.min.js", {}),
    "three/addons/BufferGeometryUtils": ("examples/jsm/utils/BufferGeometryUtils.js", {}),
    "three/addons/GLTFLoader": ("examples/jsm/loaders/GLTFLoader.js",
                                {"from '../utils/BufferGeometryUtils.js'":
                                 "from 'three/addons/BufferGeometryUtils'"}),
    "three/addons/OrbitControls": ("examples/jsm/controls/OrbitControls.js", {}),
}


class ViewerError(Exception):
    """Something the viewer is made from is missing or not what this script expects."""


def as_data_url(source):
    return "data:text/javascript;base64," + base64.b64encode(source.encode()).decode()


def module_source(relative, rewrites):
    path = THREE / relative
    if not path.is_file():
        raise ViewerError("%s is missing — run npm install; tscircuit brings three.js" % path)
    source = path.read_text()
    for old, new in rewrites.items():
        if old not in source:
            raise ViewerError("%s no longer contains %s, so its import cannot be pointed at the "
                              "import map — three.js changed; update MODULES" % (relative, old))
        source = source.replace(old, new)
    return source


def import_map():
    imports = {name: as_data_url(module_source(*spec)) for name, spec in MODULES.items()}
    imports["board-3d"] = as_data_url(VIEWER_3D.read_text())
    return json.dumps({"imports": imports})


def drawing(path):
    """
    An exported SVG, inline, and scalable. tscircuit writes a fixed width and height and no
    viewBox, so CSS could resize the box but not the drawing — the PCB sat at 800 x 600 px in a
    corner. A viewBox from its own width and height makes it fit the panel; the prolog is dropped
    so it cannot sit mid-page.
    """
    if not path.is_file():
        raise ViewerError("%s is missing — `make all` exports it before this runs" % path.name)
    svg = path.read_text()
    svg = svg[svg.index("<svg"):]
    opening = svg[:svg.index(">")]
    if "viewBox" not in opening:
        size = dict(re.findall(r'\b(width|height)="([\d.]+)"', opening))
        if len(size) != 2:
            raise ViewerError("%s states no viewBox and no numeric width and height" % path.name)
        svg = svg.replace("<svg", '<svg viewBox="0 0 %s %s"' % (size["width"], size["height"]), 1)
    return svg


def board_facts():
    """The figures the page shows, every one read from the netlist and the board file."""
    circuit = json.loads(CIRCUIT.read_text())
    board = next(e for e in circuit if e["type"] == "pcb_board")
    errors = [e for e in circuit if e["type"].startswith("pcb_") and "error" in e["type"]]
    return {
        "size": "%g &times; %g mm" % (board["width"], board["height"]),
        "board": json.loads(RESOLVED_BOARD.read_text())["name"],
        "components": sorted(e["name"] for e in circuit if e["type"] == "source_component"),
        "nets": sorted(e["name"] for e in circuit if e["type"] == "source_net"),
        "traces": sum(1 for e in circuit if e["type"] == "pcb_trace"),
        "errors": len(errors),
    }


def footer(facts):
    errors = ('<span class="pill ok">0 routing errors</span>' if not facts["errors"] else
              '<span class="pill pending">%d routing errors</span>' % facts["errors"])
    return "\n    ".join([
        '<div class="spec"><span class="k">Parts</span><span title="%s">%d</span></div>'
        % (html.escape(", ".join(facts["components"])), len(facts["components"])),
        '<div class="spec"><span class="k">Nets</span><span class="nets">%s</span></div>'
        % " · ".join("<b>%s</b>" % html.escape(net) for net in facts["nets"]),
        '<span class="pill ok">routed · %d traces</span>' % facts["traces"],
        errors,
    ])


def build():
    facts = board_facts()
    page = TEMPLATE.read_text()
    filled = {
        "@@IMPORTMAP@@": import_map(),
        "@@DIMS@@": "%s · %s" % (facts["size"], html.escape(facts["board"])),
        "@@SCHEMATIC@@": drawing(SCHEMATIC),
        "@@PCB@@": drawing(PCB),
        "@@FOOTER@@": footer(facts),
        "@@MODEL@@": base64.b64encode(MODEL.read_bytes()).decode(),
    }
    for marker, value in filled.items():
        if page.count(marker) != 1:
            raise ViewerError("the template holds %s %d times, not once" % (marker, page.count(marker)))
        page = page.replace(marker, value)
    OUTPUT.write_text(page)
    return facts


def main():
    try:
        facts = build()
    except ViewerError as broken:
        print("viewer not built: %s" % broken, file=sys.stderr)
        return 1
    print("   %s: %d parts, %d traces, %d routing errors, %.1f MB"
          % (OUTPUT.name, len(facts["components"]), facts["traces"], facts["errors"],
             OUTPUT.stat().st_size / 1e6))
    return 0


if __name__ == "__main__":
    sys.exit(main())
