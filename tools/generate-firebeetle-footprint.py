#!/usr/bin/env python3
"""
Generate the FireBeetle 2 ESP32-S3 footprint as a KiCad module.

    python3 tools/generate-firebeetle-footprint.py > FireBeetle2Esp32S3.kicad_mod
    tsci convert FireBeetle2Esp32S3.kicad_mod        # -> the .tsx board.tsx imports

Written rather than downloaded, because the footprints published for this board disagree with
each other and one of them is wrong in a way that is invisible until the parts arrive: DFRobot
puts an obround pad at every pin position, made of a through-hole 1.27 mm inboard of the edge
AND a castellated half-hole centred ON the edge. Measure the outer circles and you get a 25.40 mm
row spacing; measure the holes a header actually solders into and you get 22.86 mm. At least one
public KiCad footprint uses the former, and a header fitted to it will not mate.

Every number below is from DFRobot's own dimension drawing V1.3 and 2D CAD for DFR0975, parsed
geometrically rather than read off a picture, and cross-checked against the DFR1145 drawing. The
silkscreen order was confirmed against DFRobot's board render AND against their schematic V1.3 —
the render alone was not enough, and got three ground pins wrong.

Sources:
  https://wiki.dfrobot.com/SKU_DFR0975_FireBeetle_2_Board_ESP32_S3
  DFR0975 dimension V1.3.pdf   (title block: Name DFR0975[V1.3.0], Thickness 1.6mm)
  DFR0975_2D_CAD.dxf           (shared FireBeetle 2 form factor; see CAVEAT below)

CAVEAT: the file DFRobot serves as "2D CAD" from the DFR0975 folder actually depicts a FireBeetle
2 carrying an ESP-WROOM-32, not an S3. It agrees with the S3 dimension drawing on every shared
feature, so it is used here only for the drill diameter and the explicit 22.86 dimension. Its
component height and USB overhang belong to that other board and are NOT used.
"""

import sys

# --- the board outline ------------------------------------------------------------------------
BOARD_WIDTH_MM = 25.4
BOARD_LENGTH_MM = 60.0
BOARD_CORNER_RADIUS_MM = 1.5
BOARD_THICKNESS_MM = 1.6

# --- the two header rows ----------------------------------------------------------------------
#: Centre-to-centre between the two rows of THROUGH-HOLES. Not 25.4 — see the module docstring.
ROW_SPACING_MM = 22.86
PIN_PITCH_MM = 2.54
#: The hole a HEADER PIN goes through, which is not the hole DFRobot drills.
#:
#: Their drawing says 0.9 mm, and that was copied here at first. It is wrong for this board: it
#: is the finished hole of *their* obround pad. A standard 2.54 mm header pin is 0.64 mm square,
#: so 0.905 mm across the diagonal; after plating a 0.9 mm drill finishes near 0.84 mm, and the
#: pin does not go in. Every other through-hole part on this PCB — the module headers, the
#: buttons, the LED row — is 1.0 mm, and this footprint was the only outlier.
#:
#: The pad grows with it to keep the annular ring: 1.7 mm leaves 0.35 mm of ring (JLCPCB's
#: minimum is 0.25) and still 0.84 mm between adjacent pads at 2.54 mm pitch.
PAD_DIAMETER_MM = 1.7
DRILL_DIAMETER_MM = 1.0

#: Both rows start flush at the end away from the USB-C connector; the longer row simply runs
#: four pitches further toward the USB end.
FIRST_PAD_TO_FLUSH_EDGE_MM = 5.20

#: Everything is emitted relative to the CENTRE OF THE BOARD OUTLINE, not to the first pad.
#: That way `pcbX`/`pcbY` in board.tsx mean "where the module sits", which is what a person
#: laying out a board is thinking about, and the 3D body needs no compensating offset.
FIRST_PAD_TO_BOARD_CENTRE_MM = BOARD_LENGTH_MM / 2 - FIRST_PAD_TO_FLUSH_EDGE_MM

# --- mounting holes ---------------------------------------------------------------------------
#: The module's own mounting holes are NOT reproduced in our board. They would land underneath
#: the module, where no screwdriver reaches once it is seated on headers, and the inboard pair
#: sits in the corridor every trace between the MCU and the two plug-in modules has to funnel
#: through. They are a fact about the module, not a feature of this PCB.
EMIT_MODULE_MOUNTING_HOLES = False
MOUNTING_HOLE_DIAMETER_MM = 2.0
MOUNTING_HOLE_INSET_MM = 1.70          # from each board edge, in both axes
#: The holes are 0.43 mm inboard of the pin columns, so they are NOT on the pin centre line.
MOUNTING_HOLE_SPACING_X_MM = BOARD_WIDTH_MM - 2 * MOUNTING_HOLE_INSET_MM   # 22.00
MOUNTING_HOLE_SPACING_Y_MM = BOARD_LENGTH_MM - 2 * MOUNTING_HOLE_INSET_MM  # 56.60

# --- the pins, in physical order from the flush end toward the USB-C end ----------------------
# Confirmed against DFRobot's board render. The GPIO each label means is NOT here on purpose:
# that map lives in boards/firebeetle2-esp32s3.json, which is the one place it is allowed to be.
#: Pins 14, 15 and 16 are ALL GROUND. They were first read off DFRobot's board render as
#: "NC1, GND, NC2", because the silkscreen there is unreadable at that resolution — the exact
#: mistake the note above warns about. DFRobot's schematic V1.3 settles it: the GND symbol on
#: connector P4 fans out to three pins. So this module has three ground pads, not one, and
#: wiring only the middle one would put the motor return, the audio return and the logic return
#: through a single 1 mm pin.
LONG_ROW = ("RX", "TX", "D2", "D3", "D5", "D6", "D7", "D9", "SDA", "SCL",
            "MI", "MO", "SCK", "GND1", "GND2", "GND3", "3V3", "RST")
SHORT_ROW = ("D10", "D11", "D12", "D13", "A0", "A1", "A2", "A3", "A4", "A5",
             "D14", "D-", "D+", "VCC")

#: Which side of the board each row is on, looking at the component side with USB-C away from
#: you. The long row is to the left, so it takes the negative X column.
LONG_ROW_X_MM = -ROW_SPACING_MM / 2
SHORT_ROW_X_MM = +ROW_SPACING_MM / 2

#: Also the exported symbol name after `tsci convert`, so it must be a valid JS identifier —
#: a hyphen here silently produces a .tsx that cannot be imported.
FOOTPRINT_NAME = "FireBeetle2Esp32S3"
#: What is printed on the board. "REF**" is the placeholder KiCad ships with, and it
#: gets fabricated onto the silkscreen if nobody replaces it.
REFERENCE = "U1"
SILKSCREEN_LINE_WIDTH_MM = 0.12
COURTYARD_LINE_WIDTH_MM = 0.05


def pad(name, x_mm, y_mm):
    """One plated through-hole, round pad, on both copper layers."""
    return (f'  (pad "{name}" thru_hole circle (at {x_mm:.3f} {y_mm:.3f}) '
            f'(size {PAD_DIAMETER_MM} {PAD_DIAMETER_MM}) (drill {DRILL_DIAMETER_MM}) '
            f'(layers *.Cu *.Mask))')


def mounting_hole(x_mm, y_mm):
    """An unplated hole. Given no pad name so it cannot be mistaken for a connection."""
    return (f'  (pad "" np_thru_hole circle (at {x_mm:.3f} {y_mm:.3f}) '
            f'(size {MOUNTING_HOLE_DIAMETER_MM} {MOUNTING_HOLE_DIAMETER_MM}) '
            f'(drill {MOUNTING_HOLE_DIAMETER_MM}) (layers *.Cu *.Mask))')


def outline_segment(layer, width_mm, start, end):
    return (f'  (fp_line (start {start[0]:.3f} {start[1]:.3f}) '
            f'(end {end[0]:.3f} {end[1]:.3f}) (layer "{layer}") (width {width_mm}))')


def render():
    lines = [
        f'(module {FOOTPRINT_NAME} (layer F.Cu) (tedit 0)',
        f'  (descr "DFRobot FireBeetle 2 ESP32-S3 (DFR0975 / DFR1145), '
        f'{BOARD_WIDTH_MM}x{BOARD_LENGTH_MM}mm, {ROW_SPACING_MM}mm row spacing. '
        f'Generated by tools/generate-firebeetle-footprint.py from DFRobot dimension V1.3.")',
        f'  (tags "FireBeetle ESP32-S3 DFR0975 module")',
        f'  (fp_text reference "{REFERENCE}" (at 0 {-BOARD_LENGTH_MM / 2 - 2:.2f}) '
        f'(layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))',
        f'  (fp_text user "USB" (at 0 {BOARD_LENGTH_MM / 2 - 6:.2f}) (layer "F.SilkS") '
        f'(effects (font (size 1.2 1.2) (thickness 0.2))))',
        f'  (fp_text value "{FOOTPRINT_NAME}" (at 0 {BOARD_LENGTH_MM / 2 - 3:.2f}) '
        f'(layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))',
    ]

    for index, name in enumerate(LONG_ROW):
        lines.append(pad(name, LONG_ROW_X_MM, index * PIN_PITCH_MM - FIRST_PAD_TO_BOARD_CENTRE_MM))
    for index, name in enumerate(SHORT_ROW):
        lines.append(pad(name, SHORT_ROW_X_MM, index * PIN_PITCH_MM - FIRST_PAD_TO_BOARD_CENTRE_MM))

    top_y = -BOARD_LENGTH_MM / 2
    bottom_y = +BOARD_LENGTH_MM / 2
    if EMIT_MODULE_MOUNTING_HOLES:
        for y_mm in (top_y + MOUNTING_HOLE_INSET_MM, bottom_y - MOUNTING_HOLE_INSET_MM):
            for x_mm in (-MOUNTING_HOLE_SPACING_X_MM / 2, MOUNTING_HOLE_SPACING_X_MM / 2):
                lines.append(mounting_hole(x_mm, y_mm))

    left_x, right_x = -BOARD_WIDTH_MM / 2, BOARD_WIDTH_MM / 2
    corners = [(left_x, top_y), (right_x, top_y), (right_x, bottom_y), (left_x, bottom_y)]
    for layer, width in (("F.SilkS", SILKSCREEN_LINE_WIDTH_MM),
                         ("F.CrtYd", COURTYARD_LINE_WIDTH_MM)):
        for index, start in enumerate(corners):
            lines.append(outline_segment(layer, width, start, corners[(index + 1) % 4]))

    lines.append(")")
    return "\n".join(lines) + "\n"


def main():
    expected = len(LONG_ROW) + len(SHORT_ROW)
    if expected != 32:
        # The board has 32 header pins. Getting this wrong means a row was mistranscribed.
        print(f"refusing to emit: {expected} pins, expected 32", file=sys.stderr)
        return 1
    if len(set(LONG_ROW) | set(SHORT_ROW)) != expected:
        print("refusing to emit: duplicate pad names", file=sys.stderr)
        return 1
    sys.stdout.write(render())
    return 0


if __name__ == "__main__":
    sys.exit(main())
