# Board definitions

One file per board, holding everything the rest of the project needs to know about which
microcontroller this is: the silkscreen-to-GPIO map, which pins can wake it, which have an ADC,
which have a second job, which MicroPython build it runs, and what it is physically — its
footprint in the PCB design and its size on screen.

It exists because that knowledge was in six places — the firmware, the PCB design, the
simulator's part type, the pin-map checker, the placement code and a pile of comments — and six
copies of a fact are five chances to be wrong.

```text
boards/
  active.json              <- which board. THE one place it is chosen.
  firebeetle2-esp32s3.json    the board files themselves. Drop one in; it is available.
  xiao-esp32-c6.json
```

## Switching board

```sh
python3 tools/boards.py --list          # what is available
$EDITOR boards/active.json              # change the one line
make                                    # everything derived regenerates
make check                              # what still disagrees
```

Nothing else names a board. `tools/boards.py` resolves the active one, and the Makefile, the
firmware's spec generator and the simulator's diagram generator all go through it.

## Adding a board

1. **Write `boards/<id>.json`.** Copy the closest existing one. `id` must match the filename.
2. **Get the pin map from the vendor's Arduino variant header**, not from a pinout picture:
   `espressif/arduino-esp32` → `variants/<board>/pins_arduino.h`. Pinout diagrams are drawn by
   marketing; the header is what the toolchain compiles against. Cross-check it against the
   vendor wiki and record both under `sources`.
3. **Get the chip's capabilities from `soc_caps.h`** in `espressif/esp-idf`:
   `SOC_RTCIO_PIN_COUNT` gives the wake-capable range, `SOC_PM_SUPPORT_EXT0_WAKEUP` says whether
   `esp32.wake_on_ext0` exists, `SOC_PM_SUPPORT_EXT1_WAKEUP_MODE_PER_PIN` whether wake pins may
   have different polarities. Guessing any of these costs a bench session.
4. **Check it**: `python3 tools/boards.py --validate`. The contract is enforced, not documented.
5. **Rework `config.py`'s pin assignments.** Which function sits on which pin is a design
   decision, not a board fact — see below.
6. **Swap the footprint in `board.tsx`** to the one named in `physical.footprint_export`.
   Until `footprint_module` and `footprint_export` are filled in, `--validate --for-fab` fails
   and `make` refuses to export gerbers, which is deliberate: an unverified footprint is the one
   mistake here that costs money.

## What is a board fact, and what is not

The line that keeps this file honest:

- **A board fact** is true of the hardware whatever you build with it — D9 is GPIO0, GPIO11 is
  on ADC2, GPIO38 cannot wake the chip. These go in `boards/<id>.json`.
- **A design decision** is a choice you made — which pin the OPEN button is on, whether buttons
  are wired to GND or 3V3 (and therefore `config.WAKE_ON_HIGH`). These go in `config.py`.

`wake_on_high` was briefly in a board file during the S3 switch and had to come out: it follows
from how the buttons are wired, not from the board. A board file that accumulates decisions
stops being swappable, which is the whole point of the directory.

Steps 1–4 are mechanical. Step 5 is real work, and no amount of structure avoids it: moving to a
board with more wake-capable pins is precisely the kind of change that should make you revisit
the pin map rather than transplant it. Going from the XIAO ESP32-C6 to the FireBeetle 2 ESP32-S3
took the wake-capable pin count from 3 usable to 22, which changed every assignment.

## Simulation

`wokwi_part_type` names the part the generated Wokwi diagram uses. If Wokwi has no model of the
exact board, a same-silicon devkit stands in and `wokwi_is_stand_in` says so — the diagram
addresses pins by GPIO number, so a stand-in costs only the silkscreen labels in the picture.

Wokwi custom boards exist but are a browser-only feature (F1 → "Load custom board file"):
`wokwi.toml` has no board key, and the simulator loads boards from a bundle Wokwi hosts. Getting
a board supported headlessly means a PR to `wokwi/wokwi-boards`.
