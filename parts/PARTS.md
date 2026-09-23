# Smart-bin parts reference (real modules Petr owns)

Design keeps the real MODULES (plugged into headers/JST). Footprints are real; the module 3D
bodies come from the vendor STEP files linked below (ideal for the Fusion 360 enclosure).

## Seeed XIAO ESP32-C6  (the brain)   [reference DOWNLOADED -> ./xiao/]
- Footprint: XIAO-ESP32-C6-SMD.kicad_mod (real, in ./xiao/ and used in board.tsx)
- Pinout diagrams: ./xiao/pinout_front.png, pinout_back.png
- Datasheet/getting-started: ./xiao/getting_started.md
- Hardware repo (schematic + more): https://github.com/Seeed-Studio/OSHW-XIAO-Series
- Wiki: https://wiki.seeedstudio.com/xiao_esp32c6_getting_started/

## DFRobot DFR0534  (UART MP3 module + built-in amp)
- Wiki: https://wiki.dfrobot.com/DFR0534  ·  Product (STEP + schematic under Download tab): https://www.dfrobot.com/product-1121.html
- Interface: UART (RXD/TXD), VCC 3.3-5V, SPK+/SPK- to the speaker.

## L9110S motor driver  (the one in the design)
- The blue two-channel module (also sold as HG7881): two SOP-8 chips, green screw terminals
  marked MOTOR A / MOTOR B, 6-pin header B-IA/B-IB/GND/VCC/A-IA/A-IB.
- 2.5-12 V, ~0.8 A per channel, 3.3 V logic. Only channel A is used.
- No enable or PWM pin: direction and speed both live on the two inputs. See
  `firmware/micropython/smartbin/motor.py` for what that means in code.
- Datasheet: <https://www.elecrow.com/download/datasheet-l9110.pdf>

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
