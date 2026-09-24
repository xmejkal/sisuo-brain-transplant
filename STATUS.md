# Where we are, and what happens next

Updated 2026-09-24. This is the handover note: read it first after a break, then `CLAUDE.md`
for the project map and `firmware/micropython/smartbin/__init__.py` for how the firmware works.

## In one paragraph

The firmware is written, twice audited, and passes 80 tests, a 13-check simulation on a real
MicroPython runtime, and four scenarios on a simulated ESP32 in Wokwi. **The microcontroller
changed on 2026-09-24 from a Seeed XIAO ESP32-C6 to a DFRobot FireBeetle 2 ESP32-S3**, and the
v3 board is drawn and routed (100 x 50 mm, 53 traces, no errors) and matches the firmware pin
for pin, checked mechanically.
Every module now carries its real 3D body, which is how the layout's collisions were found and
why the rangefinder and speaker moved onto ribbons instead of onto the board.
**No part of it has ever run on hardware.** The immediate blocker is a small parts order,
which is waiting on two measurements only Petr can take.

## Waiting on Petr (everything else is blocked behind these)

1. **Button height** — board surface to the top of the black cap, on the original board. Hadex
   stocks 4.3/5/8 mm; if yours are taller (they look ~12 mm), LaskaKit has 6x6x12 mm.
2. **Bin connector pin pitch** — 2.0 mm means JST PH (buy at LaskaKit), 2.5 mm means JST XH
   (Hadex). Measure across the white 4-pin connector on the original board.
3. **A photo of the VL6180X breakout** — to confirm it has a regulator and level shifter. The
   bare chip is a 2.8 V part; Adafruit 3316 and Pololu 2489 are safe on 3.3 V, cheap boards may
   not be.
4. **Motor current, running and stalled** (multimeter in series, stall the lid by hand). The
   70 mA / 230 mA figures are from patent literature, not this motor. **Above ~500 mA the L9110S
   has no margin and the driver choice changes.** This single number can invalidate the design.
   There is now a second, independent ceiling from the same number: the 0.33 R shunt lifts the
   driver's ground, and the driver's inputs go below their 2.5 V threshold at about **2.4 A**.
   See the L9110S entry in `parts/PARTS.md` for the table. One measurement settles both.
5. ~~Confirm the XIAO battery-pad polarity with a meter~~ — **no longer applies.** The FireBeetle
   carries its own JST battery socket and an ETA6003 charger, so the cell plugs into the module
   and the board has no battery connector at all. This blocker was removed by the board change,
   not solved.
6. **The MP3 module's idle current** — five minutes with a meter and a cell, module in your
   drawer, no bin required. It decides three things at once: whether the board needs a high-side
   switch on the MP3's 3V3 feed **before it is fabricated** (it used to be a VBAT feed; the
   VBAT rail is gone), whether the deep-sleep work buys
   months or days, and whether any battery-life claim in this repo is true. Without it the bin
   has no trustworthy battery figure at all. If it is ~15-25 mA as its class suggests, it is
   roughly forty times everything else on the board combined.
7. **Motor winding resistance** — meter across the disconnected, stationary motor. Thirty seconds,
   no bin, no risk to the meter's fuse. Stall current then falls out as
   `(V_oc - V_sat) / (R_winding + R_pack + R_shunt)`, which is a better route to the number than
   stalling the lid by hand. At 17 ohm the design is comfortable; at 3 ohm stall is ~1.2 A, over
   the L9110S's rating and over the 0805 shunt's power rating.
8. **GitHub**: run `gh auth login`, then the repo gets created and pushed (see below).
   `~/Development/spark` is a git repo now, at v0.5.0, with no remote.
7. ~~A Wokwi token~~ — done; `make simulate` runs, and four scenarios pass.

## Next steps, in order

1. **Order parts** — `SHOPPING.md` has the cart: Hadex, about 145 Kc including spares, plus the
   IR fallback set. Finalise once 1 and 2 above are known.
2. **Breadboard bring-up** — `firmware/micropython/README.md` has the order: board alive,
   buttons and LED, rangefinder, MP3, motor. One script per step, each prints PASS. Then
   **step 6, `bringup/06_all_together.py`**: the whole firmware, a roll call of every device,
   and a prompted wave / OPEN / MODE, judged per phase. That is the acceptance test — when it
   prints PASS the bin works, and everything before it is only a way of getting there.
3. **Measure the motor current** while the motor is on the bench (item 4 above).
4. **Calibrate** — `tools/calibrate.py` runs each procedure and saves to `/config.json`:
   stroke times, the distance window, then the ToF offset and crosstalk *through the real lid
   window*.
5. **Fabricate the board** once the motor current is known — `board.tsx` is the v3 design and
   `make` produces the fab package, but nothing has been ordered.
6. **Enclosure** — pull the DFRobot module STEP files for Fusion.

## Decisions locked in, and why

| Decision | Why |
| --- | --- |
| No OLED | The bin never had a screen; a bicolour LED replaces it and frees I2C for the sensor |
| **L9110S** motor driver (owned), not TB6612 | Right current class, 3.3 V logic, and it is the same simple two-input design the original used. The L298N wastes 2 V; the A4988 is for steppers |
| **VL6180X** ToF as the primary sensor (owned) | All-digital, no analog maths, and the trigger distance becomes a number in software. Fallback is an IR LED + 38 kHz receiver, which is the only option that fits the lid's existing holes |
| MP3 module's TXD **not wired** | Nothing reads it and the module is not 3.3 V tolerant in that direction. Frees a pin |
| Pin map v3 | The S3 has **22 RTC pins**, so the C6's three-wake-pin straitjacket is gone. Pins are now spent on purpose: the two that must wake take non-ADC1 RTC pins; the two that never wake take the non-RTC pins D3/D14; both strapping pins are left empty |
| Board chosen in `boards/active.json` | One field, three consumers. What is *derived* round-trips exactly — switching to the C6 and back regenerated a byte-identical `board_spec.py`. What is **not** automatic: `config.py`'s pin assignments, `mcu-pins.ts`, and the footprint and placement in `board.tsx`. `make check` reports the disagreement; it cannot fix it |
| MP3 on the module's `3V3` | The FireBeetle's 3V3 is a **TPS62A02 buck good for 2 A** (DFRobot schematic V1.3), not an LDO. The whole reason the MP3 sat on VBAT was the XIAO's weak LDO, so the VBAT rail was deleted |
| I2C pull-ups 2.2k, not 4.7k | The bus runs at 400 kHz with the sensor on a ribbon. 4.7k x 100 pF = 566 ns against a 300 ns limit; 2.2k gives 265 ns and sinks 1.5 mA of the 3 mA allowed |
| FireBeetle footprint **generated**, not downloaded | Its pads are obround: a through-hole 1.27 mm inboard plus a castellated half-hole on the edge. Rows are **22.86 mm** apart, not 25.40. At least one public KiCad footprint uses 25.40, and a header fitted to that will not mate |
| Original board **not desoldered** | Petr wants it intact; all small parts bought new |
| Deep sleep via `esp32.wake_on_ext1` | `Pin.irq(wake=DEEPSLEEP)` silently does nothing on either chip. `wake_on_ext0` does not exist on the C6; it does on the S3 but takes one pin only, and we have two wake sources. The S3 lacks per-pin ext1 polarity, so all wake sources still share one level |
| Flat module layout, names by job | Recorded with the rejected alternatives in `FIRMWARE_PLAN.md` |

## What is NOT verified

* **Nothing has run on hardware.** All green results come from tests and simulation — but the
  simulation now includes the real thing: 2026-09-24, the 4 MB flash image booted on a simulated
  ESP32-S3 in Wokwi and the `lid-cycle` scenario passed end to end (idle → opening → open →
  closing → idle, with the motor pins asserted low at rest). Our own `vl6180x` and `l9110s` chip
  models drove it. That is the strongest evidence short of a bench, and it is still not a bench:
  no real motor, no real current, no real sensor.
  **`wave-to-open`, `obstruction`, `sensor-trouble` and `deep-sleep` are written and unrun** —
  Wokwi CI minutes are a limited free quota, so run them deliberately rather than on every change.
* The DFR0534 command bytes are from the v1 Arduino sketch and still need checking against
  DFRobot's own 11-page datasheet, which carries the full `AA ..` command table:
  <https://media.digikey.com/pdf/Data%20Sheets/DFRobot%20PDFs/DFR0534_Web.pdf>. (`parts/datasheets/`
  held a 6 KB product photo with a `.pdf` extension, now renamed `DFR0534_product_photo.png`.)

  **The standby question is settled, and the answer is no.** Neither DFRobot's datasheet nor the
  JQ8400 decoder's own manual documents a sleep or standby opcode — both list 0x01-0x26 and
  neither includes one. The JQ8400 manual says sleep is entered over a one-wire protocol it then
  describes as untested. A third-party measurement of the same decoder gives 18 mA idle, 4.5 mA
  after that one-wire command, and 140 µA only after removing the BUSY LED and cutting the
  amplifier's shutdown pin to a GPIO. DFRobot publish no schematic for this board, so its floor
  cannot be established from documentation at all. **The high-side power switch on the PCB is
  therefore necessary, not a precaution** — even the optimistic figure is ten times the rest of
  the sleeping system.

* Deep sleep and wake-on-pin: the firmware reaches sleep and arms the right pins, but **Wokwi
  does not wake an ESP32-C6 from a GPIO** (established by experiment — timer wake works). That
  was measured on the C6 and is *assumed* to hold for the S3 stand-in, not retested. So
  waking on a hand is a bench test.
* Lid run times, the distance window and any ToF calibration are all placeholders.

## Changing the microcontroller

Start at `boards/active.json` — one field naming a file in `boards/`. Each board file holds the
silkscreen-to-GPIO map, which pins can wake the chip, which have an ADC, which have a second job,
which MicroPython build it runs, how the Wokwi part names its pins, and what the board is
physically. The firmware's copy (`smartbin/board_spec.py`) is generated from it, the converter
and the simulator read it, and `make check` fails if any of them drift.

`boards/README.md` has the steps, and this was done for real on 2026-09-24 (XIAO ESP32-C6 ->
FireBeetle 2 ESP32-S3), so the honest accounting is:

* **Mechanical, and they worked:** the board file, the selection, the firmware's board facts, the
  Wokwi part type and pin-naming rule, the MicroPython build name, the wake/ADC capability checks.
* **Real work, and no structure avoids it:** deciding which function sits on which pin
  (`config.py` + `mcu-pins.ts`), and the footprint and placement in `board.tsx`. A board with
  different constraints deserves a fresh pin map rather than a transplanted one — the C6 allowed
  three wake pins and the S3 allows twenty-two, which changed every assignment.
* **What rotted anyway, and is now checked:** the Wokwi scenario files addressed a part that no
  longer existed (every `expect-pin` was dead while `make check` passed), and the flash-image
  script named the old chip's MicroPython build. Both now fail the build instead.

## The one command that matters

```sh
make          # regenerate whatever is out of date (board -> diagram, gerbers, SVGs, 3D)
make check    # change nothing; fail if firmware, board and simulation disagree
```

`board.tsx` and the firmware are written by hand. Everything else is derived, and editing a
derived file by hand is undone by the next `make`. Four layers keep it honest: `make`, a Claude
Code hook from the spark plugin, a git pre-commit hook (`make install-hooks`), and CI.

## Commands worth remembering

```sh
cd firmware/micropython
python3 -m unittest discover -s tests -t tests   # 60 tests, ~1 s
micropython sim/run_on_micropython.py            # 13 checks on a real MicroPython runtime
for f in smartbin/*.py; do mpy-cross -o /tmp/o.mpy "$f" || echo "FAIL $f"; done
./deploy.sh                                      # copy to the board (--mpy to cross-compile)
mpremote repl                                    # then: import smartbin; b = smartbin.build()
```

## Published

<https://github.com/xmejkal/sisuo-brain-transplant> — public, MIT, CI green on every push.

## The two bugs worth not reintroducing

1. **A task cannot cancel itself in MicroPython** (`RuntimeError: can't cancel self`), and every
   lid stroke does exactly that when it fires the trigger that transitions away. `lid.py` handles
   it; the test fakes model it deliberately. A "simplified" fake would hide it again, and the lid
   would freeze after one open.
2. **A hand that never leaves used to hold the lid open forever**, because every detection
   re-armed the hold timer. `config.MAX_OPEN_MS` caps it. Found by simulation, not by unit tests,
   because nobody writes a test for the case they did not think of.
