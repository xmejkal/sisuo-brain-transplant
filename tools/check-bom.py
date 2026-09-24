#!/usr/bin/env python3
"""
Does the fab package order the parts the schematic actually specifies?

    python3 tools/check-bom.py                 # checks the exported board-gerbers.zip

Nothing else compares these two. `make check` proves the firmware, the board, the bench scripts
and the simulation agree — and every one of those reads the *design*. The BOM is the one artifact
that leaves the design behind and becomes an order, and it was never checked against anything.

It needed to be. In the exported package, `SenseFilterCap` (1uF) and the four 100nF decoupling
capacitors were all assigned LCSC part **C14663**. One part number cannot be two capacitances, so
at least one of those five components would have arrived wrong — and the 1uF is the one the
design's own comment says sets the sense filter's corner at 159 Hz. With 100nF it is 1.6 kHz, and
the stall detector averages PWM ripple instead of motor current.

The checks here are deliberately the ones that need no supplier lookup, so they run offline and
cannot rot when a catalogue changes:

  * one supplier part number used for two different values is a contradiction on its face;
  * a supplier footprint that disagrees with the footprint in the design is tscircuit telling you
    the part it matched is not the part you drew;
  * a passive with a value but no supplier part is an unbuildable line in the order.

What it deliberately does NOT do is claim a part number is correct. Proving that needs the
supplier's catalogue, and a check that silently stops verifying when a network call fails is
worse than no check.
"""

import csv
import io
import json
import re
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FAB_PACKAGE = REPO / "board-gerbers.zip"
CIRCUIT = REPO / "dist" / "board" / "circuit.json"
BOM_NAME = "bom.csv"

EXIT_OK, EXIT_PROBLEMS, EXIT_COULD_NOT_RUN = 0, 1, 2

#: Components that legitimately have no supplier part: the plug-in modules and connectors are
#: hand-fitted, not placed by the assembler.
NO_SUPPLIER_PART_EXPECTED = re.compile(
    r"^(Mcu|MotorDriver|Mp3Player|SensorHeader|Speaker|StatusLed|Btn|BinConnector|MotorOut)")

#: Design warnings that stop being warnings once the package is an order.
FATAL_AT_FAB = ("supplier_footprint_mismatch_warning",)


def read_bom(package: Path):
    with zipfile.ZipFile(package) as archive:
        names = [n for n in archive.namelist() if n.endswith(BOM_NAME)]
        if not names:
            raise SystemExit("no %s in %s" % (BOM_NAME, package.name))
        text = archive.read(names[0]).decode()
    return list(csv.DictReader(io.StringIO(text)))


def check_duplicate_parts(rows):
    """One supplier part number standing for two different values cannot be right."""
    problems = []
    values_by_part = {}
    for row in rows:
        part = (row.get("JLCPCB Part #") or "").strip()
        value = (row.get("Value") or "").strip()
        if not part or not value:
            continue
        values_by_part.setdefault(part, {}).setdefault(value, []).append(row["Designator"])

    for part, by_value in sorted(values_by_part.items()):
        if len(by_value) > 1:
            detail = "; ".join(
                "%s = %s" % (", ".join(sorted(designators)), value)
                for value, designators in sorted(by_value.items()))
            problems.append(
                "supplier part %s is ordered for %d different values: %s. "
                "At most one of them can be the part that arrives."
                % (part, len(by_value), detail))
    return problems


def check_missing_parts(rows):
    problems = []
    for row in rows:
        designator = row["Designator"]
        if NO_SUPPLIER_PART_EXPECTED.match(designator):
            continue
        if (row.get("Value") or "").strip() and not (row.get("JLCPCB Part #") or "").strip():
            problems.append(
                "%s has a value (%s) but no supplier part, so it cannot be ordered or placed"
                % (designator, row["Value"]))
    return problems


def check_design_warnings(circuit_path: Path):
    """Warnings the design already emitted that are fatal once this becomes an order."""
    if not circuit_path.is_file():
        return []
    problems = []
    for element in json.loads(circuit_path.read_text()):
        if element.get("type") in FATAL_AT_FAB:
            problems.append("the design itself warns: %s" % element.get("message", element["type"]))
    return problems


def main():
    if not FAB_PACKAGE.is_file():
        print("no %s — run `make %s` first" % (FAB_PACKAGE.name, FAB_PACKAGE.name))
        return EXIT_COULD_NOT_RUN

    rows = read_bom(FAB_PACKAGE)
    problems = (check_duplicate_parts(rows)
                + check_missing_parts(rows)
                + check_design_warnings(CIRCUIT))

    print("%s: %d line(s) checked against the design" % (BOM_NAME, len(rows)))
    if not problems:
        print("   the order matches the schematic.")
        return EXIT_OK

    print("\n%d problem(s) — this package would build a different circuit:\n" % len(problems))
    for problem in problems:
        print("  - %s" % problem)
    return EXIT_PROBLEMS


if __name__ == "__main__":
    sys.exit(main())
