# Where we are, and what happens next

Updated 2026-10-01. The short state of the bin: read it first after a break, then `HANDOVER.md`
for the whole picture and `CLAUDE.md` for the project map. Rewritten on 2026-10-01 because the
previous version described a board two changes old — a XIAO ESP32-C6 and a DFR0534 MP3 module, a
deleted findings tool, "84 tests" and "CI green" — while the board, the firmware and the checks had
moved on. That version is in git at `22677e6`, if its reasoning about the UART audio path is ever
needed again (see B1 below).

## In one paragraph

The board is a **DFRobot FireBeetle 2 ESP32-S3** with an **I2S amplifier** (DFRobot DFR0954,
MAX98357A), an L9110S motor driver, a VL6180X rangefinder, two buttons and a bicolour LED: v4,
**100 x 62 mm, 60 traces, 0 routing errors**. The firmware passes **113 tests**, **14 checks on a
real MicroPython runtime**, and **five Wokwi scenarios** on a simulated S3 (all five passed on
2026-09-25; paid, so not rerun since). **`make check` is green** and the pre-commit gate is used
again (2026-10-01). **The repository's CI is green** since 2026-10-01 (backlog B7, `f4e6bf5`): with
no spark plugin to reach, it reads the resolved board and skips spark's four checks by name, which
this Mac's pre-commit gate runs. **No part of it has ever run on hardware.**

## Where the circuit stands

Five of the seven blockers are closed, each verified by running something rather than by reading
the change; the sixth is now an advisory.

| # | was | now |
| --- | --- | --- |
| 1 | `Mp3Switch` SOT-23 pads mapped drain/source/gate where every real P-FET is gate/source/drain | **gone** — the part is not on the board. The I2S amplifier has a shutdown pin, so there is no rail to switch |
| 2 | Nobody knows which audio module this is | **STILL OPEN, and yours to settle.** It is a look in a drawer — B1 below |
| 3 | `MotorDriver` and the audio module pad-identical, 24 mm apart | **gone** — 12 pads in two rows against 6 in one. spark's cross-pluggable rule no longer reports it |
| 4 | Pours ran to the mounting-hole walls; a screw head bridged V33 to GND | **gone** — measured at 0.19 mm on two corners, an M3 head overhangs 1.15 mm. Ground is now the only poured net, so there is nothing to bridge TO |
| 5 | Deep sleep never woke: `WAKEUP_ALL_LOW` is an AND across every armed pin | **misdiagnosed, and closed anyway** — on the S3 ESP-IDF aliases `ALL_LOW` to `ANY_LOW`, an OR (found 2026-10-01, spark P60), so this was reasoned, never observed. Both sources now assert HIGH and the firmware arms `WAKEUP_ANY_HIGH`, which also stays clear of MicroPython #17334 |
| 6 | 470 uF hard-switched with no soft-start | **gone** — the switched rail it sat on does not exist |
| 7 | `Speaker` and `BinConnector` annular rings are 0.225 mm, under the 0.25 mm a cheap process guarantees | **an advisory, not a blocker** (2026-10-01, spark P57): JLCPCB's 2-layer 1 oz PTH minimum is 0.18 mm and 0.25 is its *recommendation*, so the board is made as drawn. `check_footprints` exits 0 and says so. Grow both pads to 1.25 mm if the pitch allows, the day the board is ordered |

## Waiting on Petr

1. **B1 — which audio module is in the drawer.** The board and the firmware assume the I2S
   amplifier; `SHOPPING.md` has listed a DFR0534 as owned since the first commit, and nothing
   records who checked. Five-second test: a microSD slot means **DFPlayer Mini**; micro-USB with no
   card slot and "Voice Module V1.0" means **DFR0534**; pads marked **BCLK / LRC / DIN** mean the
   I2S amplifier. Only the last fits this board. The firmware keeps a `Dfr0534Player` strategy, and
   the old reasoning about that path (its command bytes, its missing standby opcode, the high-side
   switch it would need) is in this file at `22677e6`.
2. **Button height** — board surface to the top of the black cap, on the original board. Hadex
   stocks 4.3/5/8 mm; if yours are taller (they look ~12 mm), LaskaKit has 6x6x12 mm.
3. **Bin connector pin pitch** — 2.0 mm means JST PH (LaskaKit), 2.5 mm means JST XH (Hadex).
   Measure across the white 4-pin connector on the original board.
4. **A photo of the VL6180X breakout** — to confirm it has a regulator and level shifter. The bare
   chip is a 2.8 V part; Adafruit 3316 and Pololu 2489 are safe on 3.3 V, cheap boards may not be.
5. **Motor current, running and stalled** (multimeter in series, stall the lid by hand). The rules
   file states **1.5 A — the L9110S's own limit, as an upper bound, not a measurement** — so that
   the gate can run (2026-10-01, spark retro R8.1). The 70 mA / 230 mA figures are from patent
   literature, not this motor. **Above ~500 mA the L9110S has no margin and the driver choice
   changes.** This single number can still invalidate the design.
6. **The L9110S's input pull-ups** — a meter, thirty seconds: resistance from each input pin to
   VCC. Its vendor schematic shows four 10k to VCC and the board adds 10k pull-downs, together a
   divider near VCC/2, which on 6 V is above the part's 2.5 V input-high threshold. **This decides
   whether the motor twitches at power-up.**
7. **The DFR0954's SD bias resistor** — a download, not a bench: DFRobot's schematic says 100k,
   their wiki says 680k.
8. **Which FireBeetle you own** (owned since 2026-10-03). The SKU — DFR0975 (N16R8) or DFR1145
   (N4) — from the box or the label. The revision — the chip between BOOT and the USB-C: a QFN
   marked AXP313A is V1.1, a tiny SOT-563 beside two SOT-23-5 regulators is V1.2 or later. On V1.1
   the PMIC sits on the I2C bus with its own 5.1k pull-ups, and the MODE button — this bin's mode
   input — also drives the PMIC's power-off; `boards/firebeetle2-esp32s3.json` → `hardware_revisions`.

## Next steps — the bin's board

The order is [the bin's board](https://github.com/users/xmejkal/projects/1), set by the PO; each
card carries its detail. **B1** (#1) the drawer decides whether the audio on the board is the
audio you own. The bench cards: **B14** (#8) bring-up, `bringup/01..06` — take pins from
`config.py` until P58 (#5) fixes the bench steps · **B15** (#9) the motor's real current, to
replace the 1.5 A bound · **B16** (#10) deep sleep wakes, on the bench · **B17** (#11) calibrate.
Also **B18** (#12) the `SHOPPING.md` order · **B19** (#13) B7's second half, CI with spark beside
the bin · **B20**–**B24** (#14–#18) the connector's pitch, the FireBeetle's SKU and revision,
stall-sensing, STEP models, blocker 7.

## What is NOT verified

* **Nothing has run on hardware.** Every green result is a test or a simulation. The strongest of
  them — the real 4 MB flash image booting on a simulated S3 with our own `vl6180x` and `l9110s`
  chip models, all five scenarios passing — is still not a bench: no real motor, current or sensor.
* **Deep-sleep wake** is checked structurally (`wake-polarity.ts` compares the level the board
  asserts with the level the firmware arms for) and not by running it: Wokwi does not wake an
  ESP32 from a GPIO, established by experiment on the C6 and *assumed* for the S3 stand-in.
* **Lid run times, the distance window and the ToF calibration** are placeholders.
* **Which SKU to buy** is undecided on current: the PSRAM deep-sleep cost that argued for the N4
  is not in the datasheet it cited (the 140 uA is Light-sleep). A bench number.

## Decisions locked in, and why

| Decision | Why |
| --- | --- |
| **FireBeetle 2 ESP32-S3**, not the XIAO ESP32-C6 on hand | The C6 wakes from GPIO0-7 only — three usable pins on the XIAO. The S3 has **22 RTC pins**, so pins are spent on purpose: the two that must wake take non-ADC1 RTC pins, the two that never wake take non-RTC pins, both strapping pins stay empty |
| **I2S amplifier** (DFR0954), tones synthesised on the ESP32 | Removed blockers 1, 3, 4 and 6 and the idle-current unknown of the UART modules (0.6 uA shut down). Never stop LRCLK while BCLK runs; real shutdown needs SD below 0.16 V |
| No OLED | The bin never had a screen; a bicolour LED replaces it and frees I2C for the sensor |
| **L9110S** motor driver (owned), not TB6612 | Right current class, 3.3 V logic, the same simple two-input design the original used. The L298N wastes 2 V; the A4988 is for steppers |
| **VL6180X** ToF as the primary sensor (owned) | All-digital, and the trigger distance becomes a number in software. Fallback is an IR LED + 38 kHz receiver, the only option that fits the lid's existing holes |
| Board chosen in `boards/active.json` | One field, three consumers. What is derived round-trips exactly; what is not — `config.py`'s pins, `mcu-pins.ts`, the footprint and placement in `board.tsx` — `make check` reports, it cannot fix |
| Everything on the module's `3V3` | The FireBeetle's 3V3 is a buck (TPS62A02, 2 A, V1.2+; AXP313A, 1.5 A, V1.1), not an LDO, so there is no VBAT rail |
| I2C pull-ups 2.2k, not 4.7k | 400 kHz with the sensor on a ribbon: 4.7k x 100 pF = 566 ns against a 300 ns limit; 2.2k gives 265 ns and sinks 1.5 mA of the 3 mA allowed |
| FireBeetle footprint **generated**, not downloaded | Obround pads, a through-hole 1.27 mm inboard plus a castellated half-hole; rows **22.86 mm** apart, not 25.40 — a public KiCad footprint uses 25.40, and a header fitted to it will not mate |
| Original board **not desoldered** | Petr wants it intact; all small parts bought new |
| Deep sleep via `esp32.wake_on_ext1`, both sources active-HIGH | `Pin.irq(wake=DEEPSLEEP)` does nothing on the C6; on the S3 a level trigger arms ext0 — one pin, and there are two wake sources. ext1 takes one level for the whole mask, so both sources assert the same way; HIGH because low-level wake has an open MicroPython bug (#17334) |
| Flat module layout, names by job | Recorded with the rejected alternatives in `FIRMWARE_PLAN.md` |

## Changing the microcontroller

Start at `boards/active.json` — one field naming a board file. Each board file holds the
silkscreen-to-GPIO map, which pins can wake the chip, which have an ADC, which have a second job,
which MicroPython build it runs, how the Wokwi part names its pins, and what the board is
physically. The firmware's copy (`smartbin/board_spec.py`) is generated from it, the converter and
the simulator read it, and `make check` fails if any of them drift. `boards/README.md` has the
steps. Done for real on 2026-09-24, when the XIAO ESP32-C6 was replaced by the FireBeetle 2 ESP32-S3:

* **Mechanical, and they worked:** the board file, the selection, the firmware's board facts, the
  Wokwi part type and pin-naming rule, the MicroPython build name, the wake/ADC capability checks.
* **Real work, and no structure avoids it:** which function sits on which pin (`config.py` +
  `mcu-pins.ts`), and the footprint and placement in `board.tsx`.
* **What rotted anyway, and is now checked:** the Wokwi scenario files addressed a part that no
  longer existed, and the flash-image script named the old chip's MicroPython build.
* **What rotted and was NOT checked, until 2026-10-01:** the prose — this file, the README and the
  project brief kept describing the C6 board for a week (spark backlog B6).

## The one command that matters

```sh
make          # regenerate whatever is out of date (board -> diagram, gerbers, SVGs, 3D, viewer)
make check    # change nothing; fail if firmware, board, simulation or the documents disagree
```

`board.tsx` and the firmware are written by hand. Everything else is derived, and editing a
derived file by hand is undone by the next `make`. The git pre-commit hook (`make install-hooks`)
runs `make check`; since 2026-10-01 it is green and commits go through it.

## Commands worth remembering

```sh
cd firmware/micropython
python3 -m unittest discover -s tests -t tests   # 113 tests, ~2 s
micropython sim/run_on_micropython.py            # 14 checks on a real MicroPython runtime
for f in smartbin/*.py; do mpy-cross -o /tmp/o.mpy "$f" || echo "FAIL $f"; done
./deploy.sh                                      # copy to the board (--mpy to cross-compile)
mpremote repl                                    # then: import smartbin; b = smartbin.build()
```

## Published

<https://github.com/xmejkal/sisuo-brain-transplant> — public, MIT. **CI green since 2026-10-01** (B7; spark's four checks are skipped there until spark is public).

## The two bugs worth not reintroducing

1. **A task cannot cancel itself in MicroPython** (`RuntimeError: can't cancel self`), and every
   lid stroke does exactly that when it fires the trigger that transitions away. `lid.py` handles
   it; the test fakes model it deliberately. A "simplified" fake would hide it again, and the lid
   would freeze after one open.
2. **A hand that never leaves used to hold the lid open forever**, because every detection
   re-armed the hold timer. `config.MAX_OPEN_MS` caps it. Found by simulation, not by unit tests,
   because nobody writes a test for the case they did not think of.
