# Smart Bin — project context (for Claude Code)

ESP32 "brain transplant" of a Sisuo SS-01 sensor trash can: replace the dead control board
with a Seeed XIAO ESP32-C6 + modules, design a real PCB in tscircuit, and write firmware.
This file is the working context — read it first. Owner: Petr Smejkal (prefers descriptive
names, named constants, docstrings, focused functions; honest capability assessments).

## Where things are (this folder = ~/Development/smartbin-local)
- `board.tsx` ............ the PCB, all REAL footprints, fully routed (tscircuit).
- `board-REAL-XIAO.tsx` .. backup copy of the same.
- `XIAO-ESP32-C6-SMD.kicad_mod` .. real Seeed XIAO footprint (imported via `tsci convert`).
- `board-gerbers.zip` .... JLCPCB-ready fab package (Gerbers + drill + bom.csv + pick_and_place.csv).
- `board-pcb-routed.svg`, `board.glb` .. routed PCB + 3D exports.
- `firmware/micropython/` .. MicroPython firmware (main.py) + bringup/ test scripts. `firmware/arduino/` .. v1 Arduino reference.
- `parts/` ............... module reference: XIAO datasheet+pinouts+footprint, real OBJ 3D for the
  OLED & tactile button (from JLCPCB), datasheets, and PARTS.md (links to every module's 3D/datasheet).
- `board-viewer.html` .... self-contained schematic/PCB/3D viewer (open in any browser).
- `SHOPPING.md` ........ what to buy, where, prices (CZ shops, checked 2026-09-23).
- `parts/SENSOR_OPTIONS.md` .. wave-sensor research + VL6180X datasheet/mounting/driver notes.
- Design docs: `BOM.md` (partly superseded), `DESIGN_RULES.md`, `PCB_PIPELINE.md`, `LID_CLOSE_DETECTION.md`, `TEST_PROTOCOL.md`.

## Hardware
Board: **Seeed XIAO ESP32-C6** (3.3V logic; module handles USB/LDO/antenna/flash/straps).
Power: logic+audio on a **LiPo** (XIAO BAT pads; amp on the VBAT rail, NOT the 5V pin which is
USB-only). The lid motor keeps its own **6V AA pack** via the bin connector. Domains share only GND.
Modules (all real, plug-in): TB6612 motor driver, DFRobot DFR0534 UART MP3 + speaker, SSD1306 I2C
OLED, DFRobot SEN0239 digital IR, 2 tactile buttons, JST connectors, 0603/0805 passives.

### Pin map v1 (board.tsx + Arduino sketch) — **the board is NOT yet updated to v2**
D0 MotorIn1(AIN1) · D1 MotorIn2(AIN2) · D3 MotorPwm(PWMA) · D2 IR OUT · D4 SDA · D5 SCL ·
D6 Open button · D7 Mode button · D9 MP3 TX→RXD · D10 MP3 RX←TXD · D8 spare. TB6612 STBY tied 3V3.

## tscircuit — how to work with the board (runs locally; installed here)
```
export PATH="$PWD/node_modules/.bin:$PATH"
tsci build board.tsx                     # -> dist/board/circuit.json
tsci export -f gerbers board.tsx -o board-gerbers.zip
tsci export -f pcb-svg|schematic-svg|glb board.tsx -o <file>
```
Check routing/DRC from circuit.json (not just CLI): count `pcb_trace` and `pcb_*error` types.

### Two rules that make it work (learned the hard way)
1. **Routing:** wire decoupling/bulk caps to the power NET (`net.V33/net.VBAT/net.MOTOR6V`), never
   directly to a chip pin — a cap→pin trace trips tscircuit's unsatisfiable 1mm rule and routing is
   skipped. Net-wired = routes clean (currently 45 traces, 0 errors).
2. **Real parts, 3 sources:** footprinter strings (`pushbutton`, `pinrow3/4`, `jst_ph_2/4`,
   `headermodule6/8`, `0603`…); `tsci convert <file.kicad_mod>` for a specific GitHub footprint (how
   the XIAO came in); and `footprint="jlcpcb:C<lcsc>"` for a real footprint **+ real OBJ 3D** (JLCPCB
   is reachable from this Mac). Full recipes: the `spark` plugin's `references/tscircuit-recipes.md`.

## Firmware — MicroPython v2 (firmware/micropython/)
OO package with a **state machine** at its core. Design + rationale: `FIRMWARE_PLAN.md`;
bench/calibration/deploy: `firmware/micropython/README.md`. Arduino v1 kept only as reference.
- `smartbin/states.py` = states + triggers + TRANSITIONS table — the behaviour, as data.
- Strategies: sensor (`TofSensor`/`IrBurstSensor`/`ButtonOnlySensor`), close detection
  (`Timed`/`LimitSwitch`/`Stall`). Chosen in `config.py`, built in `smartbin/__init__.py`.
- Events = "entered:<state>", published by the FSM; `AudioFeedback`/`LedFeedback` are listeners.
  Sounds are data (`config.SOUND_PROFILES`), MODE button cycles profiles into `/config.json`.
- `build()` constructs and starts nothing; `run()` starts the loop; `main.py` is 2 lines.
  `aiorepl` gives a live REPL while it runs. Tests: `python3 -m unittest discover -s tests -t tests`.
- Safety: hard `MOTOR_MAX_RUN_MS` inside the motion loop, motor stop in `finally` + on every
  transition out, WDT only in `run()`, **10k pulldowns on both L9110S inputs** (hardware).

### Pin map v2 (GPIO in brackets) — supersedes the v1 map above
Motor IA D3[21] · IB D8[19] · I2C SDA D4[22] / SCL D5[23] (IR config reuses these two) ·
Open btn D6[16] · Mode btn D7[17] · MP3 TX D9[20] (module TXD NOT wired — not 5V tolerant) ·
LED red D10[18] · green D0[0] · **D1[1]/D2[2] reserved: the only ADC pins (stall sense)**.

### Arduino reference build
Arduino/C++ state machine (Idle→Opening→Open→Closing). Wave/IR or Open button → drive lid open on
the TB6612, chirp via MP3, OLED status; timed close with a hard `MOTOR_MAX_RUN_MS` safety cap and a
marked v2 hook for motor-current/stall sensing. Needs Arduino libs **Adafruit_SSD1306 + Adafruit_GFX**
and the **XIAO ESP32-C6** board. TODO: calibrate `LID_OPEN/CLOSE_RUN_MS`; verify the DFR0534 command
bytes against its datasheet (parts/datasheets).

## Status / next
DONE: routed v1 board + fab package (TB6612/OLED — now superseded); **firmware v2 written + 15 tests passing**;
sensor + supplier research (SENSOR_OPTIONS.md, SHOPPING.md).
NEXT: order parts (SHOPPING.md); breadboard bring-up (bringup/, in order) BEFORE any PCB; calibrate;
then REDO board.tsx for v2 (L9110S, VL6180X, no OLED, new pin map); measure the bin connector + motor stall current;
optionally add stall-sensing (see LID_CLOSE_DETECTION.md); pull DFRobot module STEP for the Fusion enclosure.

## The `spark` plugin
This whole flow (describe→schematic→verify→route→fab, real parts, reverse-engineering) is packaged as
the **spark** plugin (v0.4.0). Install it in Claude Code to reuse the skills + recipes on any board.
