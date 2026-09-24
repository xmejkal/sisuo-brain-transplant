# Where we are, and what happens next

Updated 2026-09-23. This is the handover note: read it first after a break, then `CLAUDE.md`
for the project map and `firmware/micropython/smartbin/__init__.py` for how the firmware works.

## In one paragraph

The firmware is written, twice audited, and passes 80 tests, a 13-check simulation on a real
MicroPython runtime, and four scenarios on a simulated ESP32-C6 in Wokwi. The v2 board is drawn
and routed (48 traces, no errors) and matches the firmware pin for pin, checked mechanically.
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
5. **Confirm the XIAO battery-pad polarity with a meter** before a cell goes near the board —
   continuity from footprint pin24 to any GND pin. The board now wires the LiPo to the XIAO
   (it previously did not, which meant the MCU had no battery power at all). Polarity was taken
   from Seeed's back-view drawing and mirrored onto the land pattern; Seeed's own text describes
   the pads in a way that cannot be read off this footprint. Reversed LiPo destroys the module.
6. **The MP3 module's idle current** — five minutes with a meter and a cell, module in your
   drawer, no bin required. It decides three things at once: whether the board needs a high-side
   switch on the MP3's VBAT feed **before it is fabricated**, whether the deep-sleep work buys
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
5. **Fabricate the board** once the motor current is known — `board.tsx` is the v2 design and
   `make` produces the fab package, but nothing has been ordered.
6. **Enclosure** — pull the DFRobot module STEP files for Fusion.

## Decisions locked in, and why

| Decision | Why |
| --- | --- |
| No OLED | The bin never had a screen; a bicolour LED replaces it and frees I2C for the sensor |
| **L9110S** motor driver (owned), not TB6612 | Right current class, 3.3 V logic, and it is the same simple two-input design the original used. The L298N wastes 2 V; the A4988 is for steppers |
| **VL6180X** ToF as the primary sensor (owned) | All-digital, no analog maths, and the trigger distance becomes a number in software. Fallback is an IR LED + 38 kHz receiver, which is the only option that fits the lid's existing holes |
| MP3 module's TXD **not wired** | Powered from the LiPo its idle level exceeds what the C6 tolerates, and we never read it. Frees a pin |
| Pin map v2 | **Only GPIO0-7 can wake an ESP32-C6**, which on the XIAO is D0/D1/D2 — so those carry the ToF interrupt, the OPEN button and the one ADC |
| Original board **not desoldered** | Petr wants it intact; all small parts bought new |
| Deep sleep via `esp32.wake_on_ext1`, active-high | `wake_on_ext0` does not exist on the C6 and `Pin.irq(wake=DEEPSLEEP)` silently does nothing. Low-level wake has an open MicroPython bug |
| Flat module layout, names by job | Recorded with the rejected alternatives in `FIRMWARE_PLAN.md` |

## What is NOT verified

* **Nothing has run on hardware.** All green results come from tests and simulation.
* The DFR0534 command bytes are from the v1 Arduino sketch and still need checking against
  **there is no datasheet in the repo**: `parts/datasheets/` held a 6 KB product photo with
  a `.pdf` extension, now renamed `DFR0534_product_photo.png`. Get the real one from DFRobot's
  wiki before trusting any command byte, any idle-current figure, or the standby command that
  might remove the need for a hardware power switch.

* Deep sleep and wake-on-pin: the firmware reaches sleep and arms the right pins, but **Wokwi
  does not wake an ESP32-C6 from a GPIO** (established by experiment — timer wake works), so
  waking on a hand is a bench test.
* Lid run times, the distance window and any ToF calibration are all placeholders.

## Changing the microcontroller

One file: `boards/xiao-esp32-c6.json`. It holds the silkscreen-to-GPIO map, which pins can wake
the chip, which have an ADC, which have a second job, and what the board is physically. The
firmware's copy (`smartbin/board_spec.py`) is generated from it, the converter reads it, the
simulator's layout uses its dimensions, and `make check` fails if any of them drift.

`boards/README.md` has the steps. The honest part: steps 1, 2, 4 and 5 are mechanical; step 3 —
deciding which function sits on which pin — is real work, because a different board has
different constraints. That is exactly the decision that should be revisited rather than copied.

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
