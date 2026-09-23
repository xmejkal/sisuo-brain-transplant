# Board definitions

One file per board, holding everything the rest of the project needs to know about which
microcontroller this is: the silkscreen-to-GPIO map, which pins can wake it, which have an ADC,
which have a second job, and what it is physically — its footprint in the PCB design and its
size on screen.

It exists because that knowledge was in six places — the firmware, the PCB design, the
simulator's part type, the pin-map checker, the placement code and a pile of comments — and six
copies of a fact are five chances to be wrong.

## Changing board

1. **Add `boards/<id>.json`**, copying this one. The pin map is the part worth being careful
   with: read it off the vendor's own pinout diagram, not from another board's.
2. **Point the project at it** — `BOARD_DEFINITION` in `tools/circuit-to-wokwi/lib/board.ts`.
3. **Rework `config.py`'s pin assignments.** Which function sits on which pin is a design
   decision, not a board fact, and a different board has different constraints — on the C6 only
   D0/D1/D2 can wake the chip, which is why they carry the sensor interrupt, the OPEN button and
   the ADC.
4. **Swap the footprint in `board.tsx`** to the one named in `physical.footprint_export`, and
   rerun `make`. Everything derived — the firmware's `board_spec.py`, the simulator diagram and
   its layout, the fab package — regenerates from there.
5. `make check` will tell you what still disagrees.

Steps 1 and 2 are mechanical. Step 3 is real work, and no amount of structure avoids it: moving
to a board with more wake-capable pins is precisely the kind of change that should make you
revisit the pin map rather than transplant it.
