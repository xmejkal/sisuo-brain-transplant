# Where we are, and what happens next

Updated 2026-09-24. This is the handover note: read it first after a break, then `CLAUDE.md`
for the project map and `firmware/micropython/smartbin/__init__.py` for how the firmware works.

## In one paragraph

The firmware is written, audited three times, and passes **84 tests**, a 13-check run on a real
MicroPython runtime, and — new on 2026-09-24 — **the real 4 MB flash image booting on a simulated
ESP32-S3 in Wokwi**, where the `lid-cycle` scenario passes end to end. The microcontroller changed
on 2026-09-24 from a Seeed XIAO ESP32-C6 to a DFRobot FireBeetle 2 ESP32-S3, and the v3 board is
drawn and routed (**100 x 62 mm, 61 traces**, no routing errors). **No part of it has ever run on
hardware.**

**`make check` is RED, and correctly so.** The board is not fit to order. An adversarial review on
2026-09-24 found six defects, one of which destroys a GPIO the first time the firmware runs. They
are listed immediately below and every one was reproduced before being written down.

## STOP — do not order this board

| # | defect | why it matters |
| --- | --- | --- |
| 1 | **`Mp3Switch` SOT-23 pads are mapped wrong** | tscircuit binds pad 1 = drain, 2 = source, 3 = gate. Every real SOT-23 P-FET (AO3401A, SI2301, DMG2305UX, BSS84) is **gate, source, drain**. A real part on these pads puts the load on its gate and GPIO5 on its drain with 3.3 V on the source: on from power-up, and the first `set_mp3_power(True)` shorts the 2 A buck to ground through a GPIO. `make check` now fails on this. **Fab-blocking.** |
| 2 | **Nobody knows which MP3 module this is** | see "the audio decision" below. The board's footprint fits neither candidate. **Fab-blocking.** |
| 3 | **`MotorDriver` and `Mp3Player` are pad-identical** | both `headermodule6`, same orientation, 24 mm apart on one axis. Swap the modules and 6 V lands on the audio module's serial input. |
| 4 | **The pours reach the mounting-hole walls** | `automaticPoursEnabled` runs copper to the drill. A metal M3 screw head at (-46, 27) bridges **V33 to GND**; at (46, -27) it bridges **MP3_V33 to V33**, shorting out the high-side switch. No annular ring at all. |
| 5 | **Deep sleep never wakes** | `WAKE_ON_HIGH = False` selects `esp32.WAKEUP_ALL_LOW`, which is an **AND** across both armed pins, so the bin wakes only if you hold OPEN *while* waving. A board-swap regression: the C6 had per-pin ext1 polarity, the S3 does not, and `boards/firebeetle2-esp32s3.json` records that in a field nothing reads. Fix by waking HIGH with pulldowns, using `wake_on_ext0` (one pin only), or arming one pin at a time. |
| 6 | **470 uF behind a hard-switched FET** | `Mp3ReservoirCap` is on the switched rail with no gate resistor and no soft-start, so turn-on inrush is limited only by Rds(on). The fix for the MP3's idle current created this. A gate RC cannot be added after fabrication. |

Items 1, 3, 4 and 6 disappear entirely if the audio goes I2S.

## The audio decision, which is the fork everything else waits on

`SHOPPING.md` has listed **DFR0534** under *Already owned* since the first commit and nothing
records who checked. Petr is not sure — it may be the **DFPlayer Mini (DFR0299)**, and he may also
own a **DFRobot I2S amplifier**. These are different products, not variants:

| | pads | protocol | storage | idle |
| --- | --- | --- | --- | --- |
| **the board's footprint** | **6, one row** | — | — | — |
| **this firmware** | — | **`0xAA` frames** | — | — |
| DFR0534 | 10, two rows of 5 | `0xAA` | onboard flash + micro-USB | unknown, est. 18 mA, **no standby command exists** |
| DFR0299 DFPlayer Mini | 16, two rows of 8 | `0x7E FF .. EF` | **microSD card** | similar problem |
| DFR0954 MAX98357A (I2S) | 12, two rows of 6 | I2S, 4 wires | none — the ESP32 plays | **0.6 uA** shut down |

**The board fits neither UART module**, and the firmware was written for the DFR0534.

**Five-second test: does it have a memory-card slot?** microSD means DFPlayer Mini. Micro-USB with
no card slot and "Voice Module V1.0" on the silkscreen means DFR0534. Pads marked BCLK / LRC / DIN
means the I2S amp.

**Petr has said to take the I2S route.** It is the better answer on the merits: it removes defects
1, 3, 4 and 6, it ends the idle-current unknown that has blocked this project for weeks, and the
firmware's `Player` strategy already exists for exactly this swap. Costs two extra pins and real
WAV-playback code. The part is fully researched in `spark/parts/max98357a-dfr0954.json` — read its
`host_requirements` before drawing anything, especially: **never stop LRCLK while BCLK runs** (a
large DC output cooks the speaker), and **removing the clock reaches standby at 340 uA, not
shutdown at 0.6 uA** — real shutdown needs SD driven below 0.16 V.

Planned I2S pin map, spending the cheapest pins: BCLK -> `SCK` GPIO17, LRC -> `MOSI` GPIO15,
DIN -> `MISO` GPIO16, SD -> `D3` GPIO38. All four are ADC2 or non-wake pins, and it frees
`A1`/GPIO5, an ADC1 pin.

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
   There used to be a second, independent ceiling from the same number — the shunt lifts the
   driver's local ground, and its inputs are referenced to that — but **it no longer binds**.
   The driver's input-high threshold is 2.5 V absolute, so 3.3 V logic has 0.8 V of headroom and
   the ground lift is I x R_shunt. At the old **0.33 R** that reached the threshold at 2.4 A; at
   the **0.1 R** now fitted it is 8 A, far above the L9110S's own 800 mA per channel. The driver
   rating is the only ceiling left, and the derived 2.4 A figure went stale the moment the shunt
   changed. See the L9110S entry in `parts/PARTS.md`.
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
7. ~~A Wokwi token~~ — done. `make simulate` runs and **`lid-cycle` passes**. The other four
   scenarios — wave-to-open, obstruction, sensor-trouble, deep-sleep — are written and have
   NEVER BEEN RUN. Wokwi CI minutes are a small free quota, so run them deliberately rather
   than wiring them into a gate.

## Next steps, in order

1. **Identify the audio module.** Everything below waits on it, and it is a look in a drawer.
   The three-way test is above.
2. **Redraw the audio section for I2S** — the DFR0954 — using the part file's `pin_order` and
   `host_requirements`, not from memory. This removes the mis-wired MOSFET, the 470 uF inrush,
   and one of the two cross-pluggable headers in one pass. Then `make check` should go green
   again on its own, because the `sot23` with no part number will be gone.
3. **Write `I2sWavPlayer`** beside `Dfr0534Player` in `firmware/micropython/smartbin/audio.py`
   and select it by config string. `machine.I2S` is native. Sample rate **16 or 32 kHz — 22.05 is
   explicitly unsupported by this chip** and is the obvious wrong choice.
4. **Fix the deep-sleep wake** (blocker 5). It is a firmware change, it is small, and today the
   bin cannot wake at all.
5. **Add mounting-hole keepouts** (blocker 4) and check the remaining `headermodule6` pair
   (blocker 3) before any fab.
6. **Work the findings store back to truth.** 20 findings: 11 blocked, 8 open, 1 rejected,
   **0 resolved**, and `found_against` is null on all of them. Nine cite anchors the board no
   longer has, because they were raised against the XIAO. Determinations already made and
   verified against the current board — resolve `Mp3Player.VCC on unswitched VBAT`, `shipped
   config never sleeps`, `ToF interrupt has no pull-up`, `MP3 RXD level mismatch`; re-anchor and
   keep `MOTOR_SENSE name collision` and `flying wire to the bin connector`; soften `MODE on
   U0TXD` to the GPIO47/PWRON description; and **do not resolve** the cross-pluggable-connector
   or mounting-hole findings, both of which survive in worse form. Do not run
   `findings.py validate --apply` to do this — it retires by staleness, which loses the
   difference between "we fixed it" and "it names an old part".
7. **Order parts** — `SHOPPING.md` is stale: it lists the XIAO and a LiPo JST the board no longer
   has, and its MP3 line is the unverified claim above.
8. **Breadboard bring-up**, then calibrate, then fabricate. Unchanged, and still behind all of it.

## Measurements still wanted, and which need an instrument

Three of six library questions were closed this week by reading documents and one photograph, not
by buying anything. What is left:

* **needs a meter:** the audio module's idle current (DFRobot publish no figure and no schematic,
  so its floor cannot be established from documents at all) — **moot if the audio goes I2S**, and
  the rangefinder's idle current.
* **needs a meter, cheap and decisive:** the L9110S's input pull-ups. Its vendor schematic shows
  four 10k to VCC, and the board adds 10k pulldowns — together a divider near VCC/2, which on a
  6 V supply is above the part's 2.5 V input-high threshold. Thirty seconds: resistance from each
  input pin to VCC. **This decides whether the motor twitches at power-up.**
* **needs a download, not a bench:** the DFR0954's SD bias resistor (DFRobot's schematic says
  100k, their wiki says 680k) and the amplifier's output power at 3.3 V.
* **unchanged and still the big one:** the motor's running and stall current.

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

* **BLOCKING, AND IT DECIDES THE BOARD: nobody knows which MP3 module this is.**
  `SHOPPING.md` has said "DFR0534" under *Already owned* since the first commit and nothing
  records who checked. Petr now thinks it may be the **DFPlayer Mini (DFR0299)**. They are not
  variants of each other — they are different products with different pin counts, different
  protocols and different storage:

  | | pads | protocol | storage |
  | --- | --- | --- | --- |
  | **this board's footprint** | **6, one row** | — | — |
  | **this firmware** | — | **`0xAA` frames** | — |
  | DFR0534 (Gravity MP3 Player) | 10, two rows of 5 | `0xAA` | onboard flash + micro-USB |
  | DFR0299 (DFPlayer Mini) | 16, two rows of 8 | `0x7E FF .. EF` | **microSD / TF card** |

  So the board fits **neither**, and the firmware was written for the DFR0534. DFRobot make at
  least four audio modules — DFR0299, DFR0534, DFR0768 (DFPlayer Pro) and DFR1173 (MP3 Voice
  Prompt) — so "the DFRobot MP3 one" does not identify a part.

  **The five-second test: does the module have a memory-card slot?**
  A microSD/TF slot means DFPlayer Mini, and then the firmware's protocol is wrong as well as the
  footprint. A micro-USB socket and no card slot means DFR0534, the firmware is right, and only
  the footprint needs fixing. Either way **the MP3 footprint must change before the board is
  ordered**, and every DFR0534 fact in the parts library is scoped to a part that may not be the
  one in the drawer.


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
