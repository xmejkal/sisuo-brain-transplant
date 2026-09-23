# Where we are, and what happens next

Updated 2026-09-23. This is the handover note: read it first after a break, then `CLAUDE.md`
for the project map and `firmware/micropython/smartbin/__init__.py` for how the firmware works.

## In one paragraph

The firmware is written, restructured after a four-way code audit, and passes 60 tests plus a
twelve-check simulation on a real MicroPython runtime. **No part of it has ever run on
hardware.** The v1 PCB is routed and has a fab package, but the parts decisions have moved on,
so it must be redone before anything is ordered. The immediate blocker is a small parts order,
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
5. **A name for the `spark` plugin** (in `~/Development/spark`, not a git repo, never installed).
   Asked several times; still unanswered, so the rename and install never happened.
6. **GitHub**: run `gh auth login`, then the repo gets created and pushed (see below).
7. **Optional: a Wokwi token** (wokwi.com/dashboard/ci, 50 free CI minutes) to run the `sim/`
   Wokwi project, which has never been run.

## Next steps, in order

1. **Order parts** — `SHOPPING.md` has the cart: Hadex, about 145 Kc including spares, plus the
   IR fallback set. Finalise once 1 and 2 above are known.
2. **Breadboard bring-up** — `firmware/micropython/README.md` has the order: board alive,
   buttons and LED, rangefinder, MP3, motor. One script per step, each prints PASS.
3. **Measure the motor current** while the motor is on the bench (item 4 above).
4. **Calibrate** — `tools/calibrate.py` runs each procedure and saves to `/config.json`:
   stroke times, the distance window, then the ToF offset and crosstalk *through the real lid
   window*.
5. **Redo the PCB for v2** — `board.tsx` is still the v1 design: TB6612, an OLED and the old pin
   map, none of which survive. See "decisions" below for what it must become.
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
  `parts/datasheets/DFR0534_mp3.pdf`.
* Deep sleep and wake-on-pin have never been executed — not on hardware, and unverified in Wokwi
  under MicroPython.
* The `sim/` Wokwi project (diagram, scenario) is written from documentation, not from a run.
  Expect to fix part IDs and the pushbutton control name on first use.
* Lid run times, the distance window and any ToF calibration are all placeholders.

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
micropython sim/run_on_micropython.py            # 12 checks on a real MicroPython runtime
for f in smartbin/*.py; do mpy-cross -o /tmp/o.mpy "$f" || echo "FAIL $f"; done
./deploy.sh                                      # copy to the board (--mpy to cross-compile)
mpremote repl                                    # then: import smartbin; b = smartbin.build()
```

## Publishing

Repository decided: **public**, named **sisuo-brain-transplant**. Branch renamed to `main`, MIT
licence added, README written, `.gitignore` covers firmware binaries and token files. A scan
found no secrets and no personal email in the committed files. Remaining:

```sh
gh auth login    # Petr: GitHub.com -> HTTPS -> browser
gh repo create sisuo-brain-transplant --public --source=. --remote=origin --push
```

## The two bugs worth not reintroducing

1. **A task cannot cancel itself in MicroPython** (`RuntimeError: can't cancel self`), and every
   lid stroke does exactly that when it fires the trigger that transitions away. `lid.py` handles
   it; the test fakes model it deliberately. A "simplified" fake would hide it again, and the lid
   would freeze after one open.
2. **A hand that never leaves used to hold the lid open forever**, because every detection
   re-armed the hold timer. `config.MAX_OPEN_MS` caps it. Found by simulation, not by unit tests,
   because nobody writes a test for the case they did not think of.
