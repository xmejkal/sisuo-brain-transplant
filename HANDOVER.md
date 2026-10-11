# Smart bin + spark — everything needed to pick this up cold and finish it

Written 2026-09-25; trimmed 2026-10-11, when the order of work moved to the board. Read this first, then
`CLAUDE.md` for the project's own conventions.

**What each document is for**, because three overlapping lists is how work stops draining:

| file | job |
| --- | --- |
| **this file** | the whole picture: both repos, what was decided and why, what is left |
| `CLAUDE.md` | working conventions and where things live. Stable |
| `STATUS.md` | what is true now, what waits on a person, what has never been checked: one page |
| [the bin's board](https://github.com/users/xmejkal/projects/1) | the bin's work in the PO's order; each card is an issue in this repo |
| `../spark/scrum/` | the process; the plugin's work is on [spark's board](https://github.com/users/xmejkal/projects/2) |

---

## 1. What this is

Two repositories, one effort.

- **`~/Development/smartbin-local`** — the thing being built. A Sisuo SS-01 sensor bin whose
  control board died, rebuilt around a **DFRobot FireBeetle 2 ESP32-S3** with plug-in modules:
  an L9110S motor driver, a VL6180X time-of-flight rangefinder, a DFR0954 MAX98357A I2S
  amplifier, two buttons and a bicolour LED. PCB in tscircuit, firmware in MicroPython.
- **`~/Development/spark`** — a Claude Code plugin for AI-assisted electronics design. The bin is
  its test case and its only real evidence that it works.

The bin is the priority. Petr's words: *"lets prioritize having a working bin project with a
schema, parts, simulations and software"*, and *"we want the circuit to be good and working"* —
**not** fabrication-ready. **We are not ordering the board.** That distinction decides what is
worth fixing: a circuit fault matters, a fabrication-process limit does not yet.

---

## 2. Where it stands, measured

Every number here came from running the command beside it, not from memory.

| what | state | how to reproduce |
| --- | --- | --- |
| The board builds | 60 traces, 0 errors | `tsci build board.tsx` |
| Everything agrees | green | `make check` → *"everything is in step"* |
| Firmware logic | **113 tests**, OK | `cd firmware/micropython && python3 -m unittest discover -s tests -t tests` |
| Firmware on a real MicroPython runtime | 14 checks pass | `micropython sim/run_on_micropython.py` |
| Board↔simulation↔firmware↔bench scripts | **50 tests**, 0 fail | `cd tools/circuit-to-wokwi && bun test` |
| Wokwi, simulated ESP32-S3 silicon | **last green 2026-09-25; none runs now** — on 2026-10-11 the serial log came back empty, Wokwi changed (B31, #26) | `make simulate-all` (costs minutes — see §7) |
| spark's own suite | **367 tests**, OK | `cd ../spark && python3 -m unittest discover -s tests` |
| spark end to end | *"the chain runs end to end"* | `python3 ../spark/scripts/check_spine.py` |

### The five Wokwi scenarios and what each proves

Run from `firmware/micropython/sim/`. Before today only `lid-cycle` had ever been confirmed.

- `lid-cycle` — buttons, full open → hold → close.
- `wave-to-open` — a hand on the rangefinder, over a simulated I2C bus. **Had never worked.**
- `obstruction` — hand in the way three times, reopens each time, faults on the fourth, cleared
  by a button. This is the behaviour the original bin got wrong. **Had never worked.**
- `sensor-trouble` — "cannot measure" (an empty room) is not confused with a real fault.
- `deep-sleep/sleep-and-wake` — reaches sleep and arms GPIO 13 and 12.

Why two could never pass: `CONFIG_OVERRIDES` in `tools/build-flash-image.py` was `{}`, so the
simulation image inherited config.py's *deployed* defaults — `deep_sleep` and `tof_interrupt`.
The bin under test slept while the scenarios waved a hand at it. The main image is now the
**bench** configuration; the battery configuration has its own image and its own project
directory, because a `wokwi.toml` names exactly one firmware.

---

## 3. Which audio module — answered 2026-10-06 (B1)

The DFR0954 I2S amplifier, owned ×2, from the DFRobot order history; no DFR0534 appears in any DFRobot order
(B1, #1). The board and the firmware assume it. B29 (#23) retires the DFR0534 fallback
(`board-v3-dfr0534.tsx`, `AUDIO_STRATEGY="dfr0534"`); until it does, both players translate the same cue
vocabulary (§5).

---

## 4. What to do next

[The bin's board](https://github.com/users/xmejkal/projects/1), in the PO's order; each card is an issue in this
repo and carries its detail. **Nothing has ever touched hardware**, and the bench is where every remaining
unknown gets answered (§8).

---

## 5. Decisions that are settled, and why

Do not re-litigate these without new evidence. The *why* is the part that would otherwise be lost.

**The audio is I2S, and that removed four defects at once.** A DFR0534 has no enable pin and an
idle current nobody had measured — possibly 15-25 mA, which would have been forty times
everything else on the board combined. The board worked around it with a P-channel high-side
switch, a gate hold resistor and a 470 uF reservoir. The MAX98357A has a shutdown pin instead:
**0.6 µA held low, against 340 µA if the clock merely stops.** So the switch, its resistor, the
reservoir, the switched rail, the SOT-23 pad-mapping defect and the pad-identical 6-way header
all went together. Never stop LRCLK while BCLK runs; real shutdown needs SD below 0.16 V.

**A cue is a word, not a number.** This is the part worth keeping even if the bin changes. A cue
used to be a bare integer, and the integer meant *"track 1 in the module's flash"* to the DFR0534
and *"entry 1 in the tone table"* to the amplifier. The same profile, the same numbers, two
unrelated sounds, and nothing anywhere could detect it. Now `audio.ALL_CUES` names what the bin
is **expressing** — `open-start`, `settled`, `blocked`, `fault` — and each player translates:
`I2sTonePlayer.TONES` to frequencies, `Dfr0534Player.TRACKS` to track numbers. Neither table
knows the other exists, and a test asserts both cover the vocabulary.

**The two audio strategies are different BOARDS, not two settings.** `AUDIO_STRATEGY` selects,
but `_build_dfr0534_player` refuses when `PIN_MP3_TX` is absent rather than sending serial frames
into the amplifier's shutdown line. The pin map *is* the statement of which board is fitted, so
asking it beats a second flag that could disagree.

**Both deep-sleep wake sources assert HIGH.** `esp32.wake_on_ext1` takes one level for every
armed pin, so both sources must agree; `WAKEUP_ANY_HIGH` is an OR. *Corrected 2026-10-01 (spark P60/P63):* this used to say `WAKEUP_ALL_LOW` is an AND across every armed pin. That is true only on the original ESP32 — ESP-IDF v5.5.2's `esp_sleep.h` aliases it to `ANY_LOW`, an OR, on the S3 and C6, and MicroPython passes it through. So the "woke only if you held OPEN while waving" failure was reasoned, never observed (nothing has run on hardware), and active-low wiring would have woken too. Active-high stays, for the reason that holds: low-level wake has an open MicroPython bug (#17334, reported on a C6). So `BtnOpen`
goes to 3V3 behind a pull-down, `TofIntPulldown` replaced `TofIntPullup`, and the VL6180X's GPIO1
is configured active-high. **MODE stays wired to ground on purpose** — GPIO47 cannot wake this
chip, so it needs no external part.

**Only ground is poured.** `automaticPoursEnabled` poured every qualifying net, which meant a V33
plane as well as a GND one — and at two mounting holes both reached 0.19 mm from the edge while
an M3 screw head overhangs 1.15 mm. Tightening a screw shorted 3.3 V to ground. Keepouts do not
help (copper pours are excluded from keepout enforcement) and there is no board-level clearance
setting. Explicit `<copperpour connectsTo="net.GND">` per layer removes the hazard structurally:
one net, nothing to bridge to. It also turned 447 pour fragments into 3.

**Board versions**: `board.tsx` (v4) is the board; `board-v3-dfr0534.tsx` waits at the root for B29 (#23) to
retire it, and `docs/archive/board-v1-tb6612.tsx` is the v1 design. Each superseded file's header says what is
wrong with it, so nobody fabricates one by finding it.

**Smaller decisions, one line each** (moved here from STATUS.md, 2026-10-11):

- **FireBeetle 2 ESP32-S3, not the XIAO ESP32-C6 on hand:** the C6 wakes from GPIO0-7 only (three usable pins); the
  S3 has 22 RTC pins, so pins are spent on purpose — wake pins on non-ADC1 RTC pins, both strapping pins left empty.
- **No OLED:** the bin never had a screen; a bicolour LED replaces it and frees I2C for the sensor.
- **L9110S (owned), not TB6612:** right current class, 3.3 V logic, the same two-input design the original used.
- **VL6180X ToF (owned) as the primary sensor:** all-digital, the trigger distance is a number in software.
  Fallback: an IR LED + 38 kHz receiver, the only option that fits the lid's holes.
- **The board is chosen in `boards/active.json`:** one field, three consumers; `make check` reports what cannot be
  derived (`config.py`'s pins, `mcu-pins.ts`, the footprint and placement in `board.tsx`).
- **Everything runs on the module's `3V3`:** it is a buck (TPS62A02, 2 A, V1.2+; AXP313A, 1.5 A, V1.1), so there is
  no VBAT rail.
- **I2C pull-ups 2.2k, not 4.7k:** at 400 kHz on a ribbon, 4.7k x 100 pF = 566 ns against a 300 ns limit; 2.2k gives 265 ns.
- **The FireBeetle footprint is generated, not downloaded:** rows **22.86 mm** apart, not the 25.40 of a public
  KiCad footprint, which a real header would not mate.
- **The original board is not desoldered:** Petr wants it intact; all small parts are bought new.
- **Flat module layout, names by job:** the rejected alternatives are in `docs/archive/FIRMWARE_PLAN.md`.

### The pin map, as it stands

Three statements must agree — `config.py` (signal→GPIO), the board definition (GPIO→silkscreen),
`mcu-pins.ts` (signal→silkscreen) — and `make check` proves it.

```
ToF INT      D12 [12]   wake source, asserts HIGH
Open button  D11 [13]   wake source, asserts HIGH (to 3V3, pull-down)
Stall ADC    A0  [4]    the one ADC1 pin spent
Motor IA     D10 [14]      Motor IB   D6 [18]
I2C          SDA [1] / SCL [2]
Mode button  D14 [47]   cannot wake, to GND, internal pull-up
I2S BCLK     SCK [17]   LRC  MO [15]   DIN  MI [16]
Audio SD     D3  [38]   driven LOW = 0.6 µA shutdown; never leave floating
LED red      D7  [9]       LED green  D5 [7]
```

Untouched on purpose: `D9`/GPIO0 is the BOOT strap, `D2`/GPIO3 the JTAG strap. ADC2 (GPIO11-20)
cannot be read with WiFi on.

Current strategy settings: `SENSOR_STRATEGY="tof_interrupt"`, `POWER_POLICY="deep_sleep"`,
`CLOSE_DETECTOR="timed"`, `AUDIO_STRATEGY="i2s"`, `WAKE_ON_HIGH=True`.

---

## 6. The traps — things that actually bit us

Each of these was found by running something, and each would bite again.

**A pad's label is not always its pin's name.** The FireBeetle prints `MI` and `MO` where the
board file keys `MISO` and `MOSI`. Both correct, not the same string. Two lookups were missing
the bridge in opposite directions, and `pad_aliases` had been in the board definition all along
with nothing reading it. This only surfaced because I2S is the first design to use those pads.

**A test that passes for the wrong reason.** The bring-up script's WAVE phase had never tested
anything: the firmware builds the interrupt pin with *no* pull (correct — the board carries an
external one), so in the fakes it read 0, the strategy was active-LOW, and 0 meant "asserted".
The phase passed on a pin nothing had ever driven. `FakeVL6180X` now drives its interrupt from
the threshold and polarity the driver actually **wrote**.

**A mutation no firmware test can catch.** Reverting `WAKE_ON_HIGH` to `False` leaves all 113
tests green, because every one derives from that constant — the pull, the pressed level, the
interrupt polarity. Flip it and the firmware flips *consistently*. It is only wrong relative to
the copper. `tools/circuit-to-wokwi/lib/checks/wake-polarity.ts` compares the rail the button is
tied to against the level the firmware arms for. It deliberately does **not** predict whether the
symptom is "never wakes" or "wakes constantly" — that depends on whether the internal pull or the
board resistor wins, and the first version guessed and was wrong in both directions.

**A vendor's drill is not your drill.** A module drawing gives the vendor's finished hole for the
vendor's own pad. A hole that must *accept* a 2.54 mm header pin needs ≥1.0 mm: the pin is
0.64 mm square, so 0.905 mm across the diagonal, and plating grows inward.

**Two fields describing one physical thing must agree.** spark's VL6180X record said
`footprint: pinrow5` while its pinout named seven pads — five carry a signal, two are unwired,
and somebody counted pins instead of pads. The generator labelled a pad that did not exist, that
port got no position, and tscircuit's autorouter died reading its `x` — **silently**, leaving a
board with zero traces.

**Routing is skipped entirely when one net is unsatisfiable.** It does not raise. You get every
component placed, every port present, and **zero `pcb_trace`**. Always count traces and errors in
`circuit.json`; the CLI summary is not enough.

**Pads with no pad-1 marker.** The DFR0954 has none, and DFRobot number its two rows in opposite
directions. `Dfr0954I2sAmp.tsx` places every pad **by name** for that reason. SPK+ and SPK− are
the rightmost pad of *each* row — directly across, 15.24 mm apart, **not** adjacent. A footprint
drawn as though they neighboured wires the speaker across SPK+ and DIN.

**A task cannot cancel itself in MicroPython** (`RuntimeError: can't cancel self`), and every lid stroke does
exactly that when it fires the trigger that transitions away. `lid.py` handles it; the test fakes model it
deliberately. A "simplified" fake would hide it again, and the lid would freeze after one open.

**A hand that never leaves used to hold the lid open forever**, because every detection re-armed the hold
timer. `config.MAX_OPEN_MS` caps it. Found by simulation, not by unit tests, because nobody writes a test for the
case they did not think of.

---

## 7. How to work on this

```bash
export PATH="$PWD/node_modules/.bin:$PATH"

make check            # the gate. Must say "everything is in step"
make simulate         # one Wokwi scenario (lid-cycle)
make simulate-all     # all five — costs minutes, see below

tsci build board.tsx                                  # -> dist/board/circuit.json
python3 ../spark/scripts/check_all.py --project .     # spark's deterministic checks
```

**Wokwi minutes are a budget, not a resource.** The quota is 50 free CI minutes and the only
source of truth is wokwi.com/dashboard/ci — **check there, do not trust a number written here.**
What is known: confirming all five scenarios on 2026-09-25 cost roughly six to eight minutes of
wall-clock simulation, including two runs that timed out before the cause was found. Needs `WOKWI_CLI_TOKEN`, which Petr has; it is deliberately
**not** in the repo and should go in `~/.zshrc`. Run one scenario per question, never the full set to "check nothing
broke". The free checks — 113 firmware tests, the MicroPython run, `make check` — catch
everything a scenario would except real silicon behaviour.

**Rules that are not negotiable**, each learned from a real defect:

- A check that could not look must never read as a check that passed. Four outcomes: `ok`,
  `problems`, `could-not-run`, `skipped`.
- A test must **run** the thing, not read it. No assertions on source text.
- **Never change a test so it passes.** Change the decision first; the test follows. If the test
  is wrong, say why its *premise* is wrong.
- Mutation-test before committing: re-introduce the defect, the suite must go red. Capture
  stderr — `unittest` writes its verdict there, and a harness that drops it reports silence and
  looks like success.
- Commit continuously, with a message saying what was wrong and why the fix is right. The log is
  the memory.

---

## 8. What cannot be known without hardware

Say these are unknown rather than estimating them. `STATUS.md` keeps the list, in "Waiting on Petr" and "What is
NOT verified": the motor's real current (the one number that could still change the driver choice), whether the
bin wakes, the lid stroke times, the bin connector's pitch, which VL6180X breakout it is (the board assumes a
5-wire ribbon — VIN, GND, SDA, SCL, INT — to an off-board module), and which FireBeetle revision you own.

---

## 9. The spark side, briefly

spark has its own board, [spark's board](https://github.com/users/xmejkal/projects/2); the process lives in
`../spark/scrum/` (`README.md` the flow, `WORKING_AGREEMENTS.md` the rules, `RETROSPECTIVES.md` what each retro
changed). Petr is Product Owner; a card waiting on his decision carries *Waiting on: the PO*. The Wokwi converter
(`tools/circuit-to-wokwi/`) moved into spark (P32a); the bin's copy goes with P32b (#6). The 2026-10-11 replan
(`../spark/docs/2026-10-11-replan.md`, a proposal until the PO decides) makes the bin's bench the second proof of
spark's journey, after spark's own walk. `python3 scripts/check_spine.py` in spark reports *"the chain runs end to
end"*.
