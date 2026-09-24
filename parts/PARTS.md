# Smart-bin parts reference (real modules Petr owns)

Design keeps the real MODULES. Footprints are real; the module 3D bodies come from the vendor
STEP files linked below (ideal for the Fusion 360 enclosure).

Two ways a module reaches the board, and the difference decides the board size:

- **On the board**, plugged onto a header: the XIAO, the L9110S driver, the DFR0534 MP3 module.
  These take real board area — 21 x 17.5, 29 x 23 and 30 x 22 mm — which is why the outline is
  70 x 45 mm and why `tools/check-module-clearance.py` exists.
- **On a ribbon**, because the part has to be somewhere else in the bin: the rangefinder looks
  out through the lid, and the speaker sits behind a grille. Both carry 2.54 mm headers of their
  own, so a flat multi-way cable plugs straight on. The board carries only the mating header or
  JST, and no body is drawn for them — they are not on the board.

## Seeed XIAO ESP32-C6  (the brain)   [reference DOWNLOADED -> ./xiao/]
- Footprint: XIAO-ESP32-C6-SMD.kicad_mod (real, in ./xiao/ and used in board.tsx)
- Pinout diagrams: ./xiao/pinout_front.png, pinout_back.png
- Datasheet/getting-started: ./xiao/getting_started.md
- Hardware repo (schematic + more): https://github.com/Seeed-Studio/OSHW-XIAO-Series
- Wiki: https://wiki.seeedstudio.com/xiao_esp32c6_getting_started/

## DFRobot DFR0534  (UART MP3 module + built-in amp)
- Wiki: https://wiki.dfrobot.com/dfr0534  ·  Product: https://www.dfrobot.com/product-1741.html
- Dimension drawing (the only mechanical source DFRobot publish): https://dfimg.dfrobot.com/wiki/19342/DFR0534_mp3-player-module_dimension_V1.0.pdf
- Datasheet, 11 pp, DFRobot-authored, with the full `AA ..` command table: https://media.digikey.com/pdf/Data%20Sheets/DFRobot%20PDFs/DFR0534_Web.pdf
- **No STEP and no schematic exist for this SKU.** An earlier version of this line linked
  product-1121, which is the DFPlayer Mini — a different module — and promised both.
- Interface: UART (RXD/TXD), VCC 3.3-5V, SPK+/SPK- to the speaker.

## L9110S motor driver  (the one in the design)
- The blue two-channel module (also sold as HG7881): two SOP-8 chips, green screw terminals
  marked MOTOR A / MOTOR B, 6-pin header B-IA/B-IB/GND/VCC/A-IA/A-IB.
- 2.5-12 V, ~0.8 A per channel, 3.3 V logic. Only channel A is used.
- No enable or PWM pin: direction and speed both live on the two inputs. See
  `firmware/micropython/smartbin/motor.py` for what that means in code.
- Datasheet: <https://www.elecrow.com/download/datasheet-l9110.pdf>
- **Input thresholds, read off that datasheet (2026-09-24):** `VH in` = **2.5 V min** / 5.0 typ /
  9.0 max; `VL in` = 0 / 0.5 / **0.7 V max**. The high threshold is an **absolute voltage, not
  0.7 x VCC** — which is why 3.3 V logic drives a 6 V-powered L9110S at all. Worth checking
  because the ratiometric case would have meant 4.2 V and a motor that never turns.
- **The shunt eats that margin, and there is a hard ceiling.** The driver's GND sits on
  `net.MOTOR_SENSE`, above system ground by `I x 0.33 R`. The chip judges its inputs against *its
  own* ground, so the effective input high is `3.3 - 0.33 x I`:

  | Motor current | Effective V_in | Margin over 2.5 V |
  | --- | --- | --- |
  | 0.5 A | 3.14 V | 0.64 V |
  | 1.0 A | 2.97 V | 0.47 V |
  | 2.0 A | 2.64 V | 0.14 V |
  | **2.42 A** | **2.50 V** | **zero** |

  Above ~2.4 A the inputs fall below threshold and the driver stops seeing a valid high. It is
  self-limiting rather than destructive — current falls, the input recovers, and it may chatter —
  but it is a real ceiling that the 0.33 R shunt imposes on top of the driver's own ~0.8 A rating.
  **One more reason the stall measurement matters**, and a reason to prefer a smaller shunt with
  gain over a larger one.

## VL6180X time-of-flight rangefinder  (the wave sensor in the design)
- I2C at 0x29, 0-100 mm guaranteed, 850 nm. Reports millimetres, so the trigger distance is a
  number in `config.py` rather than a trimpot.
- **The die is a 2.8 V part.** Adafruit 3316 and Pololu 2489 carry a regulator and level shifter
  and are safe on 3.3 V; a bare board may not be.
- Mounting and calibration behind the lid window are the hard part — see
  `parts/SENSOR_OPTIONS.md`, which has ST's procedures and the numbers.
- Datasheet: <https://www.st.com/resource/en/datasheet/vl6180x.pdf>

## Superseded: DFRobot motor driver  (v1 design only)
- If DRI0044 (TB6612, 2x1.2A): https://wiki.dfrobot.com/2x1.2A_DC_Motor_Driver__TB6612FNG__SKU__DRI0044
- If DRI0040 (HR8833): https://wiki.dfrobot.com/Dual_1.5A_Motor_Driver_-_HR8833_SKU__DRI0040
- STEP + schematic on the product page Download tab.

## Fallback: IR proximity  (only if the rangefinder will not fit the lid)
- DFRobot SEN0239 (Gravity digital, adjustable): https://wiki.dfrobot.com/sen0239
- Interface: VCC/GND/OUT (digital).

## Superseded: OLED 0.96" I2C (SSD1306) — dropped, the bin never had a screen
- Generic SSD1306 module; LCSC C5248081 (0.91" 128x32) / C-number varies — JLCPCB has a real 3D model.
- Interface: VCC/GND/SDA/SCL, addr 0x3C.

## DFRobot speaker  (8 ohm)
- e.g. FIT0502 (3W 8 ohm enclosed): https://www.dfrobot.com/product-1506.html  (JST PH2.0)

## Connectors, buttons, passives (real 3D available from JLCPCB/LCSC)
- Tactile switch 6mm: LCSC C318938  · JST PH: LCSC C495693  · 0603/0805 passives: standard.
- These have real OBJ 3D models via `footprint="jlcpcb:C<number>"` in tscircuit.

## How to get a module's real 3D into tscircuit
tscircuit renders 3D from the footprint; a breakout board's true 3D needs the vendor STEP.
For a part that IS on LCSC, `footprint="jlcpcb:C<number>"` brings the real footprint AND a real
OBJ 3D model automatically (JLCPCB is reachable from this machine).
