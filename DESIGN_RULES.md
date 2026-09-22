# Circuit & PCB design rules — reusable knowledge layer

The reusable "grade the design against this" reference for the spark skill. Three parts:
general best practices, ESP32-C6/XIAO module specifics, and how AI is actually made good
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

## Part 2 — ESP32-C6 / XIAO ESP32-C6 checklist (module-level)

**The big simplification:** the XIAO is a *module*, so EN/RC, boot & reset buttons, USB, the
3V3 LDO + LiPo charger, crystal, RF matching, antenna switch, flash, strapping pull-ups and
all bare-chip decoupling are **already done**. You're a pin-allocation + power-budget problem.

- [ ] **Motor VM off battery/5 V, never the 3V3 LDO.** The 3V3 pad only feeds logic-level
      peripherals (OLED, IR, amp logic, TB6612 *VCC*). Give VM its own bulk cap.
- [ ] **0.1 µF at every peripheral** (OLED, amp, IR, driver) + the VM bulk cap.
- [ ] **I2C pull-ups (4.7 kΩ)** on D4/SDA (GPIO22) and D5/SCL (GPIO23) — the module doesn't add them.
- [ ] **Only use the 11 broken-out GPIOs**; none are strapping/flash/USB/antenna, so the
      classic boot-strap failure is designed out. Respect default roles:
      D6/D7 = UART0 TX/RX (GPIO16/17), D8/D9/D10 = SPI (GPIO19/20/18), D3 = SS (GPIO21),
      D4/D5 = I2C (GPIO22/23), D0/D1/D2 = ADC (GPIO0/1/2).
- [ ] **Analog reads** (if IR is read analog): put a 0.1 µF filter on the ADC pin; use D0/D1/D2.
- [ ] **Don't assume GPIO3/GPIO14 are free** in firmware — they run the antenna RF switch
      (not on the header, but the Arduino core drives them).
- [ ] Everything is **3.3 V logic** — confirm every peripheral is 3.3 V-compatible.
- [ ] Power design (not firmware) fixes brownout: motor inrush + Wi-Fi TX + amp share the rail →
      separate motor rail + bulk caps.

**Authoritative XIAO C6 pin map:** D0=GPIO0(A0) · D1=GPIO1(A1) · D2=GPIO2(A2) · D3=GPIO21(SS) ·
D4=GPIO22(SDA) · D5=GPIO23(SCL) · D6=GPIO16(TX) · D7=GPIO17(RX) · D8=GPIO19(SCK) ·
D9=GPIO20(MISO) · D10=GPIO18(MOSI). Source of truth = the Seeed wiki pin list + `pins_arduino.h`.
**This resolves the D6–D10 uncertainty flagged earlier** (they are GPIO16/17/19/20/18).

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
- [Espressif ESP32-C6 Schematic Checklist](https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32c6/schematic-checklist.html) · [Hardware Design Guidelines](https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32c6/index.html) · [ESP32-C6 datasheet](https://documentation.espressif.com/esp32-c6_datasheet_en.html)
- [XIAO ESP32C6 wiki](https://wiki.seeedstudio.com/xiao_esp32c6_getting_started/) · [pins_arduino.h](https://raw.githubusercontent.com/espressif/arduino-esp32/master/variants/XIAO_ESP32C6/pins_arduino.h) · [strapping pins guide](https://www.espboards.dev/blog/esp32-strapping-pins/)
- [kicad-happy](https://github.com/aklofas/kicad-happy) · [tscircuit/skill](https://github.com/tscircuit/skill) · [atopile](https://github.com/atopile/atopile) · [circuit-synth](https://github.com/circuit-synth/circuit-synth) · [@jlcpcb/mcp](https://www.npmjs.com/package/@jlcpcb/mcp)
- [Hackaday: Can AI now design PCBs that just work?](https://hackaday.com/2026/09/05/can-ai-now-design-pcbs-that-just-work/) · [Awesome KiCad](https://github.com/joanbono/awesome-kicad)
