# Circuit & PCB design rules — reusable knowledge layer

The reusable "grade the design against this" reference for the spark skill. Three parts:
general best practices, FireBeetle 2 ESP32-S3 module specifics, and how AI is actually made good
at this. Sources at the end.

## Part 1 — General circuit & PCB best practices

**Power & decoupling**
- One bulk cap at the supply entry (10–100 µF); one **0.1 µF per IC power pin, placed right at the pin**.
- Extra bulk (100–470 µF) next to any high-current/switching load — here, the motor driver's VM.
- Budget every rail's current; don't run heavy loads off a small on-board regulator.

**Grounding**
- Solid ground pour/plane; keep it continuous under signals.
- Star/single-point ground where power, analog and digital meet — motor return current must not flow through signal ground. Join grounds at one point.
- Two supply domains (motor vs logic) share **only** ground, never a supply rail.

**Currents & traces**
- Size traces to current: ~0.25 mm handles ~0.5 A, ~0.5 mm ~1 A on 1 oz copper — widen motor traces; use a trace-width calculator.
- Keep signal traces short and off noisy switching nodes; minimise current-loop area (EMC).

**Level & protection**
- Match logic levels (3.3 V here); a motor/actuator never touches a GPIO.
- Inductive loads need flyback protection (the H-bridge has internal diodes); add TVS/ESD on any externally exposed connector; optional series R on long logic lines.
- I2C: one set of pull-ups (typ. 4.7 kΩ) per bus. Buttons: input→GND with a pull-up (internal is fine).

**Thermal & DFM (for cheap fabs like JLCPCB)**
- Copper pour + thermal vias under the motor driver.
- Min trace/space ~6 mil, standard drills, E24 resistor values, 0603/0805 for hand assembly, stay 2-layer when you can.
- Antenna keep-out: no copper under a module's antenna; keep it at the board edge.
- Add test points on key nets, silkscreen labels, and fiducials if assembled.

## Part 2 — FireBeetle 2 ESP32-S3 checklist (module-level)

*Rewritten 2026-10-01 for the board the bin uses (spark backlog B6). Until then this was the XIAO
ESP32-C6's checklist, a week after the board changed; that version is in git history.*

**The big simplification:** the FireBeetle is a *module*, so USB, the 3V3 buck, the LiPo charger
(ETA6003, 1 A) and its JST socket, the crystal, RF, antenna, flash, the BOOT button and all
bare-chip decoupling are **already done**. You're a pin-allocation + power-budget problem.

**The pin map is not restated here** — that is how this section went stale. Silkscreen to GPIO,
what each pin can do and its roles: `boards/firebeetle2-esp32s3.json`. Signal to GPIO: `config.py`.
Signal to silkscreen: `mcu-pins.ts`. `make check` proves the three agree.

- [x] **Motor VM off the bin's 6 V pack, never the module's 3V3.** 3V3 feeds logic and audio only;
      the motor rail has its own bulk cap, and the two domains share ground and nothing else.
- [x] **0.1 µF at every peripheral** (amplifier, rangefinder, driver logic) + the motor bulk cap.
- [x] **I2C pull-ups 2.2 kΩ** on SDA (GPIO1) and SCL (GPIO2): **V1.2 and later boards have none
      anywhere** (V1.1's AXP313A brings 5.1 k, which then sit in parallel — know which board you
      hold, `hardware_revisions` in the board file). `SdaPullup`/`SclPullup` in `board.tsx`.
- [x] **Strapping pins left empty:** D9 = GPIO0 (BOOT) and D2 = GPIO3 (JTAG source); GPIO45/46
      are not on the header.
- [ ] **ADC on ADC1 only** (GPIO1-10): ADC2 (GPIO11-20, A5 included) cannot be read with WiFi on.
      The stall sense uses A0 (GPIO4) behind a filter cap.
- [ ] **Wake pins are RTC pins** (GPIO0-21). GPIO38/43/44/47 cannot wake the chip — D14 (GPIO47)
      is also the on-board button, and D13 (GPIO21) the on-board LED.
- [ ] **TX/RX (GPIO43/44) are the console** — the ROM bootloader prints there on every reset.
- [ ] Everything is **3.3 V logic** — confirm every peripheral is 3.3 V-compatible (the VL6180X die
      is 2.8 V; its breakout must regulate and level-shift).
- [ ] Power design (not firmware) fixes brownout: motor inrush, Wi-Fi TX and the amplifier must not
      share a rail → separate motor rail + bulk caps.

## Part 3 — How AI is actually made good at circuit design

The pattern that works is **agent + verified parts + reference-design reuse + a design-rule
checker in the loop** — not "LLM invents a schematic." Build the knowledge layer as three
retrievable assets the agent composes:

1. **Verified part library** — real MPN + footprint + datasheet specs, backed by a JLCPCB/LCSC
   lookup (so no hallucinated/unbuildable parts). This is the #1 failure-mode fix.
2. **Proven reference modules** — Espressif front-ends, power/USB/reset blocks, known-good
   sub-schematics reused as blocks (composition beats generation).
3. **Design-rule checklists** — the Espressif Schematic Checklist + DRC/EMC rules, gating every output.

**Tools people actually use (2025–26):**
- `kicad-happy` — the most mature (1.1k★, validated on 5,800+ projects): Claude Code skills for
  KiCad parse + DRC + EMC + datasheet extraction + BOM/sourcing. The strongest *checker* layer.
- `tscircuit/skill` (our engine), `atopile` (ships its own MCP), `circuit-synth` (7 verified
  reference patterns + JLCPCB stock lookup).
- Part-lookup MCPs: `@jlcpcb/mcp`, `pcbparts-mcp`, LCSC skills — the highest-impact single add.
- Espressif Hardware Design Guidelines = the checklist the AI is graded against.

**Honest verdict:** verified parts + reference modules + rule-checking genuinely work; autonomous
production-ready boards and good auto-routing do not yet (best models ~69% on the EEBench hardware
benchmark) — human validation before fab is non-negotiable.

## Sources
- [Espressif ESP32-S3 Schematic Checklist](https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32s3/schematic-checklist.html) · [Hardware Design Guidelines](https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32s3/index.html) · [ESP32-S3 datasheet](https://documentation.espressif.com/esp32-s3_datasheet_en.html)
- [FireBeetle 2 ESP32-S3 wiki](https://wiki.dfrobot.com/SKU_DFR0975_FireBeetle_2_Board_ESP32_S3) · [pins_arduino.h](https://raw.githubusercontent.com/espressif/arduino-esp32/master/variants/dfrobot_firebeetle2_esp32s3/pins_arduino.h) · [strapping pins guide](https://www.espboards.dev/blog/esp32-strapping-pins/)
- [kicad-happy](https://github.com/aklofas/kicad-happy) · [tscircuit/skill](https://github.com/tscircuit/skill) · [atopile](https://github.com/atopile/atopile) · [circuit-synth](https://github.com/circuit-synth/circuit-synth) · [@jlcpcb/mcp](https://www.npmjs.com/package/@jlcpcb/mcp)
- [Hackaday: Can AI now design PCBs that just work?](https://hackaday.com/2026/09/05/can-ai-now-design-pcbs-that-just-work/) · [Awesome KiCad](https://github.com/joanbono/awesome-kicad)
