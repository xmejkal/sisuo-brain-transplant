# Where we are

Updated 2026-10-11. The short state of the bin: read it first after a break, then `HANDOVER.md` for
the whole picture and `CLAUDE.md` for the project map. **The order of work is
[the bin's board](https://github.com/users/xmejkal/projects/1), not this file**; this page keeps only what
is true now, what waits on a person, and what has never been checked.

## In one paragraph

The board is a **DFRobot FireBeetle 2 ESP32-S3** with an **I2S amplifier** (DFRobot DFR0954,
MAX98357A), an L9110S motor driver, a VL6180X rangefinder, two buttons and a bicolour LED: v4,
**100 x 62 mm, 60 traces, 0 routing errors**. The firmware passes **113 tests**, **14 checks on a
real MicroPython runtime**, and **five Wokwi scenarios** on a simulated S3 (all five passed
on 2026-09-25; on 2026-10-11 the serial log came back empty, so none runs now — B31,
https://github.com/xmejkal/sisuo-brain-transplant/issues/26). **`make check` is green** and the pre-commit gate is used
again (2026-10-01). **The repository's CI is green** since 2026-10-01 (backlog B7, `f4e6bf5`): with
no spark plugin to reach, it reads the resolved board and skips spark's four checks by name, which
this Mac's pre-commit gate runs. **No part of it has ever run on hardware.**

## Waiting on Petr

1. **Button height** — board surface to the top of the black cap, on the original board. Hadex
   stocks 4.3/5/8 mm; if yours are taller (they look ~12 mm), LaskaKit has 6x6x12 mm.
2. **Bin connector pin pitch** — 2.0 mm means JST PH (LaskaKit), 2.5 mm means JST XH (Hadex).
   Measure across the white 4-pin connector on the original board.
3. **A photo of the VL6180X breakout** — to confirm it has a regulator and level shifter. The bare
   chip is a 2.8 V part; Adafruit 3316 and Pololu 2489 are safe on 3.3 V, cheap boards may not be.
4. **Motor current, running and stalled** (multimeter in series, stall the lid by hand). The rules
   file states **1.5 A — the L9110S's own limit, as an upper bound, not a measurement** — so that
   the gate can run (2026-10-01, spark retro R8.1). The 70 mA / 230 mA figures are from patent
   literature, not this motor. **Above ~500 mA the L9110S has no margin and the driver choice
   changes.** This single number can still invalidate the design.
5. **The L9110S's input pull-ups** — a meter, thirty seconds: resistance from each input pin to
   VCC. Its vendor schematic shows four 10k to VCC and the board adds 10k pull-downs, together a
   divider near VCC/2, which on 6 V is above the part's 2.5 V input-high threshold. **This decides
   whether the motor twitches at power-up.**
6. **The DFR0954's SD bias resistor** — a download, not a bench: DFRobot's schematic says 100k,
   their wiki says 680k.
7. **Which FireBeetle you own** (owned since 2026-10-03). The SKU — DFR0975 (N16R8) or DFR1145
   (N4) — from the box or the label. The revision — the chip between BOOT and the USB-C: a QFN
   marked AXP313A is V1.1, a tiny SOT-563 beside two SOT-23-5 regulators is V1.2 or later. On V1.1
   the PMIC sits on the I2C bus with its own 5.1k pull-ups, and the MODE button — this bin's mode
   input — also drives the PMIC's power-off; `spark/boards/firebeetle2-esp32s3.json` → `hardware_revisions`.

## What is NOT verified

* **Nothing has run on hardware.** Every green result is a test or a simulation. The strongest of
  them — the real 4 MB flash image booting on a simulated S3 with our own `vl6180x` and `l9110s`
  chip models, all five scenarios passing until B31 — is still not a bench: no real motor, current or sensor.
* **Deep-sleep wake** is checked structurally (`wake-polarity.ts` compares the level the board
  asserts with the level the firmware arms for) and not by running it: Wokwi does not wake an
  ESP32 from a GPIO, established by experiment on the C6 and *assumed* for the S3 stand-in.
* **Three open circuit faults**, each a card: B25 (#19) the ToF wake line asserts at 1.89 V, below the S3's 2.48 V
  input-high; B26 (#20) the L9110S module drains the AA pack flat in weeks with the lid at rest; B28 (#22) the motor
  current reaches its shunt over 0.15 mm track, lifting the driver's ground 300 mV at 2 A.
* **Lid run times, the distance window and the ToF calibration** are placeholders.
* **Which SKU to buy** is undecided on current: the PSRAM deep-sleep cost that argued for the N4
  is not in the datasheet it cited (the 140 uA is Light-sleep). A bench number.

## Where the rest went

The long version of this file (04e3817 and earlier, in git) held the following; each now lives in one place.

* **The seven original fab blockers** (six closed, one an advisory) and the **open circuit faults** B25, B26 and B28
  with the claim B27: the cards on the board carry them. The closed ones are history in git.
* **Next steps and the bench cards** (B14-B24 and the rest): the board, in the PO's order.
* **Decisions and why**, with the smaller ones: `HANDOVER.md` section 5. **The traps**, including the two bugs
  worth not reintroducing (a task cannot cancel itself; a hand that never leaves): section 6.
* **Changing the microcontroller**: the spark plugin's `boards/README.md`, "Switching board".
* **Commands**: README "Testing" and `HANDOVER.md` section 7; deploy and REPL in `firmware/micropython/README.md`.
* **Published**: <https://github.com/xmejkal/sisuo-brain-transplant> — public, MIT. CI green since 2026-10-01 (B7;
  spark's four checks are skipped there until spark is public).
