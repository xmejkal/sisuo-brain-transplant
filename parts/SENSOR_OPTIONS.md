# Wave-to-open sensor — options researched (2026-09-23)

Goal: detect a hand at ~5–15 cm and open the lid. Petr's constraint: **as digital and
plug-and-play as possible** (no hand-calculated analog), and ideally a module reusable in other
projects. Firmware is **MicroPython only**.

## Decision

**Try the VL6180X Petr already owns** (I2C, 0x29) on the breadboard first — it costs nothing, it
is pure digital, it shares the I2C pins freed by dropping the OLED, and its range band is the
right one. If the lid-window mounting defeats it, buy **DFRobot SEN0245 (Gravity VL53L0X)**.
Discrete IR LED + receiver is now the *fallback*, not the plan — it is the only option that fits
the bin's existing IR holes, but it needs a transistor + resistors (against the "all digital" goal).

## Option comparison

| Option | Interface | Range | Cost | MicroPython driver | Verdict |
| --- | --- | --- | --- | --- | --- |
| **VL6180X (owned)** | I2C 0x29 | **0–100 mm guaranteed** (more only "with certain reflectance/ambient") | free | one abandoned 2017 file; better to port Adafruit's | **1st choice** — right range class, has crosstalk/range-ignore features made for windows |
| **DFRobot SEN0245** Gravity VL53L0X | I2C, Gravity 4-pin | 30–2000 mm | $12.90 / **330 Kč** [Botland](https://botland.cz), in stock | mature, several forks | **Fallback** — plug-and-play Gravity, but sees floor/wall/legs so needs tight thresholds |
| DFRobot SEN0315 Gravity PAJ7620U2 gesture | I2C 0x73, Gravity | 3–20 cm, real "wave" gesture | $13.90 / **275 Kč** Botland, in stock | **thin** — only one unproven repo; would need porting | Best false-trigger rejection, worst driver situation |
| DFRobot SEN0427 Fermion VL6180X | I2C, 2.54 header | 5–100 mm | $9.50 | same as owned part | No reason to buy — Petr owns the chip already |
| DFRobot SEN0239 Gravity digital IR (in old BOM) | 1 digital pin | 0–200 cm adjustable | $12.90 | none needed | **Rejected** — Ø18 mm × 75 mm cylinder, will not fit the lid |
| DFRobot SEN0019 digital IR | 1 digital pin | 10–80 cm | $6.90 | none needed | **Rejected — 5V only**, XIAO/LiPo has no 5V rail |
| Discrete IR LED + 38 kHz receiver | 1 GPIO out (38 kHz burst) + 1 GPIO in | tune by LED current | ~15 Kč | none needed | Fallback; fits the original holes; needs transistor + resistors |
| Ultrasonic (URM09 etc.) | I2C | 2–500 cm | $12.90 | — | Rejected — wide cone sees floor/wall/legs |

DFRobot has **no** VL53L1X module. TEL0157 is a GNSS module, not a rangefinder.
Nothing DFRobot-IR is stocked in Czechia; Botland stocks the Gravity ToF and gesture modules.

## VL6180X — what the datasheet says (ST DocID026171 Rev 6, AN4545)

- **Range 0–100 mm guaranteed.** Beyond that is explicitly not guaranteed. In 5 kLux
  (≈10–15 kLux sunlight) worst-case range falls to ~60–70 mm. **So use a 30–100 mm trigger
  window, not 150 mm.**
- I2C address **0x29**, 400 kHz, 16-bit register addresses. No conflict with anything else here.
- **The die is a 2.8 V part (2.6–3.0 V).** Adafruit #3316 and Pololu #2489 breakouts add a
  regulator + level shifter and are safe on 3.3 V. **A bare GY-VL6180 style board may not —
  confirm before wiring 3.3 V.**
- 850 nm emitter (not 940 nm), ranging ~1.7 mA, convergence ≤15 ms → 10–20 Hz polling is fine.
- Also has an ambient-light sensor (unused here).

### Mounting behind the lid window — the make-or-break part
- **Crosstalk** (light bouncing off the inside of the window back into the receiver) is the
  failure mode. ST: above a **2.5 mm air gap crosstalk rises rapidly** → mount the sensor face
  **≤1 mm** behind the window, hard against it. A bare hole is easiest.
- Window material: glass/acrylic/PMMA/PC, ~1 mm thick, clear at **850 nm**, flat, parallel, clean.
- **Calibrate in the assembled lid**, through the real window:
  - offset: 88% white target at 50 mm from the window top; if the average is 50 ± 3 mm, skip.
    Else `SYSRANGE__PART_TO_PART_RANGE_OFFSET{0x24}`.
  - crosstalk: 3% black target at 100 mm, `SYSRANGE__CROSSTALK_COMPENSATION_RATE{0x1E}` (9.7
    fixed point) = `avg_return_rate{0x66} × (1 − avg_range{0x62}/100)`.
  - range-ignore so a dirty window never reads as "hand": `SYSRANGE__RANGE_CHECK_ENABLES{0x2D}`
    bit 1, `SYSRANGE__RANGE_IGNORE_THRESHOLD{0x26}` ≥ 1.2 × crosstalk.
- Re-gluing/replacing the window invalidates the calibration.

### MicroPython driver situation (checked 2026-09-23)
- [Ledbelly2142/VL6180X](https://github.com/Ledbelly2142/VL6180X) — the only real MicroPython
  driver, 117 lines, last commit **2017**, MIT. Works with hardware `machine.I2C` (`addrsize=16`).
  Known defects: `default_settings()` called before `init()`; `address()` calls a missing method;
  `init()` raises `RuntimeError("Failure reset")` on any soft reboot without power-cycling the
  sensor (fresh-out-of-reset register self-clears); `range()` never checks
  `RESULT__RANGE_STATUS{0x4D}`, so an error is indistinguishable from a real 255 mm.
- [Adafruit_CircuitPython_VL6180X](https://github.com/adafruit/Adafruit_CircuitPython_VL6180X) —
  actively maintained, has the model-ID check, `range_status`, offset. **Port this**: only four
  private I2C helpers need swapping to `machine.I2C.writeto_mem/readfrom_mem(..., addrsize=16)`.
  Then add the four calibration registers above, which no existing driver exposes.
- VL53L0X/VL53L1X have livelier MicroPython drivers
  ([uceeatz/VL53L0X](https://github.com/uceeatz/VL53L0X),
  [antirez/vl53l0x-nb](https://github.com/antirez/vl53l0x-nb) non-blocking,
  [drakxtwo/vl53l1x_pico](https://github.com/drakxtwo/vl53l1x_pico)) — relevant only if we fall
  back to SEN0245.

## Firmware consequences
- Sensor moves onto **I2C (D4 SDA / D5 SCL)** — the pins the dropped OLED used. **D2 is freed.**
- Trigger logic: `30 mm < range < 100 mm` for N consecutive samples at 10–20 Hz, plus a cooldown,
  instead of a single digital level.
