# Bill of materials — smart bin (Seeed XIAO ESP32-C6)

> **SUPERSEDED IN PART (2026-09-23).** Current decisions: no OLED (dropped); motor driver =
> the **L9110S module Petr owns** (not TB6612); wave sensor = the **VL6180X he owns**, see
> `parts/SENSOR_OPTIONS.md`; what to buy and from where: `SHOPPING.md`. The original Sisuo board
> is not desoldered — all small parts are bought new. Sections below still hold for power domains
> and passive values.

Prototyping philosophy (per Petr): **plug-and-play vendor modules, minimal analog work,
all-digital signal chain.** Every module below is real, 3.3V-native, and runs off the LiPo
rail. Where a bare/simple part is genuinely easier, it's offered as a choice.

Power: **logic + audio on a LiPo** (on the XIAO's BAT pads; the XIAO charges it from USB).
The lid motor keeps its own **6V AA pack** via the bin connector. Domains share only GND.

## Modules — chosen parts + alternatives (all 3.3V, all digital)

| Function | Primary pick | Alternative | Interface |
| --- | --- | --- | --- |
| MCU | Seeed XIAO ESP32-C6 | — | — |
| IR "wave to open" | **DFRobot SEN0239** Gravity digital IR, adjustable 0–200 cm, 3–5V | Seeed Grove IR Distance Interrupter v1.2 | 1 digital GPIO |
| OLED status | **DFRobot DFR0486** Gravity I2C OLED 128×64 (SSD1306, 0x3C) | Seeed Grove OLED 0.96" SSD1315 (0x3C) | I2C |
| Motor driver | **DFRobot TB6612/HR8833 breakout (owned)** — H-bridge, reverses the lid motor | all-I2C Grove driver (below) | 3 GPIO (IN1/IN2/PWM) |
| Audio | **DFRobot DFR0534 UART MP3 module (owned)** — stored chirps, built-in amp | — | UART (2 pins) |
| Speaker | **DFRobot speaker (owned)** — driven straight from the MP3 module (confirm 8Ω) | any 8Ω 1–2W | — |
| Buttons | 2× 6 mm tactile | — | 2 digital GPIO |

**Motor driver vs bare MOSFETs:** the lid motor runs both directions, so it needs an H-bridge
(4 switches). The driver module already is one, with flyback diodes and logic-level control.
Bare MOSFETs would mean hand-building the H-bridge (gate drive, shoot-through, diodes) — avoid
for the prototype; keep the MOSFETs for a one-directional on/off load later.

### Optional simplification — go all-I2C
Swap the PWM motor driver for an **I2C** one and the entire prototype rides one shared I2C bus
(OLED + motor + any I2C sensor), freeing GPIOs D0/D1/D3:
- **Seeed Grove Mini I2C Motor Driver** (DRV8830, 2.75–6.8V — sized exactly for the 6V pack), or
- **Seeed Grove I2C Motor Driver (TB6612FNG)**, 2.5–13.5V.
Trade-off: motor commands go over I2C (tiny latency, no fast-PWM tricks) — fine for a lid.

### Audio — DECIDED: DFR0534 UART MP3 module (Petr owns it)
Stored WAV/MP3 chirps triggered by index over 2 UART wires; built-in amp drives the DFRobot
speaker directly. No I2S code. This is now in the schematic (Mp3Player + Speaker), powered from
VBAT. If a real-time "talking bin" is wanted later, a MAX98357A I2S amp can be added back.

## Passive values — specified & calculated
- **I2C pull-ups (PullupSda / PullupScl): 4.7 kΩ** for 100 kHz (many Grove/Gravity OLED
  modules already include pull-ups — if so, **omit ours**). Drop to 2.2–3.3 kΩ for 400 kHz.
  - Calc: R_min = (3.3 − 0.4)/3 mA ≈ 1.0 kΩ; R_max ≈ 11.8 kΩ at 100 kHz/100 pF. 4.7 kΩ is safe.
- **Decoupling caps: 100 nF (0.1 µF) X7R 16 V, one at each IC power pin** — now in the schematic
  (motor VM, motor VCC, amp, OLED, IR).
- **Motor bulk cap (MotorBulkCap): 220 µF (up to 470 µF), ≥ 10 V** at the driver's VM, + 0.1 µF.
  - Motor draws ~70 mA running, ~230 mA at stall; the reservoir absorbs inrush.
- **Amp reservoir cap: 100 µF, ≥ 10 V** on the VBAT rail at the amp, + 0.1 µF.

## Config straps (choices, no calc)
- **TB6612 STBY:** tie to 3V3 = enabled. (An I2C driver needs none of this.)
- **MP3 module:** set volume/EQ over UART commands in firmware; no strap pins.

## Remaining unknowns — needed for the BOM to be fully orderable
1. **Speaker impedance** — confirm the DFRobot speaker is 8Ω (easier on the LiPo than 4Ω).
2. **Motor driver style** — direct PWM (owned breakout, current schematic) vs an all-I2C Grove
   driver. The owned breakout is fine; only switch if you want one-bus wiring.
3. **Bin connector (BinConnector)** — pitch/part of the bin's existing plug (measure; the
   reverse-engineering Test 1 also confirms which pins are motor vs battery).
4. **Motor stall current** — quick bench measurement to confirm the bulk-cap size (multimeter).
5. **Cap voltage ratings / packages** — VBAT/6V-rail caps ≥ 10 V; 3.3V-rail caps ≥ 6.3 V (use
   10–16 V for margin).

**None of these block writing the firmware** — the pin map is locked.
