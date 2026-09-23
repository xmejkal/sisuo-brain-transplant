# Shopping list — Czech shops (prices checked 2026-09-23)

Petr is in Czechia and buys single pieces. **Hadex** is cheapest and covers nearly everything;
LaskaKit fills the gaps (JST PH, taller buttons, proper 1/4 W resistors). Shipping costs more
than the parts, so spares are worth adding. Prices are CZK incl. VAT, per piece.

## Already owned — do NOT buy
XIAO ESP32-C6 · LiPo · **L9110S dual motor driver module** (blue, HG7881 type; also owns an L298N
and an A4988 stepper driver, both unsuitable) · DFR0534 MP3 module + DFRobot speaker ·
**VL6180X ToF sensor** (see [parts/SENSOR_OPTIONS.md](parts/SENSOR_OPTIONS.md)) · breadboards,
jumper wires, perfboard.
The original Sisuo board stays **untouched** — nothing gets desoldered from it.

## Buy — Hadex ([hadex.cz](https://www.hadex.cz)), all in stock

| Part | Qty | Kč ea | Link |
| --- | --- | --- | --- |
| Tactile switch 6×6, **height TBD** (4.3 / 5 / 8 mm variants, 2 Kč each) | 10 | 2 | [KFC-A06-5](https://www.hadex.cz/p/l367-mikrospinac-kfc-a06-5-6x6mm-v-5mm) |
| LED 5 mm bicolour red/green, common cathode (3 leads) | 3 | 4 | [K130A](https://www.hadex.cz/p/k130a-led-5mm-dvoubarevna-r-g-40-45mcd-20ma-50-cira) |
| Resistor 330 Ω (status LED) | 10 | 1.50 | [H931](https://www.hadex.cz/p/h931-330r-rc0204-rezistor-0-25w-5) |
| Capacitor 100 nF X7R, 5 mm pitch | 10 | 2 | [J461B](https://www.hadex.cz/p/j461b-100n-50v-rm-5-keramicky-kondenzator-dielektrikum-x7r) |
| Capacitor 220 µF / 16 V | 5 | 1 | [I845](https://www.hadex.cz/p/i845-220u-16v-105-6x11x3-5mm-elektrolyt-kondenzator-radialni) |
| JST XH 4-pin cable + socket (**only if the bin plug is 2.5 mm pitch**) | 2 | 6 | [D477C](https://www.hadex.cz/p/d477c-konektor-jst-xh-4pin-kabel-15cm-zdirka-jst-xh-4pin) |

≈ **90 Kč** for the table above, ≈ **55 Kč** for the IR set below → **≈ 145 Kč** total.
Free shipping starts at 1500 Kč, so shipping is payable either way — one parcel, both options.

### IR parts — ordered as the mechanical-fallback set
The bin's lid already has two 5 mm holes for an IR LED + receiver pair, so this path is the one
guaranteed to fit. Buy it alongside the ToF plan and decide on the bench.
| Part | Qty | Kč ea | Link |
| --- | --- | --- | --- |
| IR receiver CHQ1838 (38 kHz, VS1838/HX1838 clone) | 5 | 3 | [K519B](https://www.hadex.cz/p/k519b-chq1838-infraprijimac-s-tvarovacem-v-krytu-hx1838-vs1838) |
| IR LED 940 nm 5 mm Kingbright L-53F3BT | 5 | 5 | [K090A](https://www.hadex.cz/p/k090a-led-5mm-infra-940nm-kingbright-l-53f3bt) |
| NPN BC337-25 TO-92 (switches the IR LED) | 10 | 1.50 | [B097](https://www.hadex.cz/p/b097-bc337-25-n-45v-0-5a-0-625w-100mhz-ss-160-400-to92) |
| Resistor 1 kΩ (transistor base) | 10 | 1.50 | [H937](https://www.hadex.cz/p/h937-1k0-rc0204-rezistor-0-125w-5) |
| Resistor 100 Ω (IR LED series) | 10 | 1.50 | [H925](https://www.hadex.cz/p/h925-100r-rc0204-rezistor-0-25w-5) |

Note: Hadex RC0204 resistors have thin legs — they sit loosely in a breadboard. LaskaKit's Yageo
MFR-25 1/4 W at 1 Kč grip better ([link](https://www.laskakit.cz/metal-oxidovy-rezistor-yageo-mfr-25fte52-1-4w-1-/)).

### Added after the 2026-09-23 electronics review (all Hadex, few Kč each)
Reasons in `FIRMWARE_PLAN.md` + `parts/SENSOR_OPTIONS.md`.

| Part | Qty | Why |
| --- | --- | --- |
| Resistor 10 kΩ | 10 | Pulldowns on both L9110S inputs — the only thing that keeps the motor off while the XIAO's pins are high-Z after a reset, or during a reflash |
| Capacitor 470–1000 µF / 16 V | 2 | At the DFR0534 VCC. An 8 Ω speaker peak pulls hundreds of mA from the same LiPo; audio thump → brownout reset is a classic failure |
| Capacitor 100 nF (extra) | — | One goes **across the motor brushes**, at the motor. Brush arcing — not inductive kickback — is what upsets I2C and IR receivers |
| Capacitor 4.7 µF + resistor 100 Ω | 5 each | Supply filter at the IR receiver. Its datasheet **requires** this, it is not optional |
| Resistor 470 Ω | 10 | IR LED transistor base (supersedes the 1 kΩ if we drive the LED hard: 470 Ω saturates BC337 at 100 mA) |
| Resistor 15 Ω and 22 Ω | 5 each | IR LED series resistor if 100 Ω gives too little range (100 Ω ≈ 20 mA, 15 Ω ≈ 100 mA pulsed) |
| Resistor 1 Ω 0.5 W metal film | 5 | Current-sense shunt, only if we add stall detection (70 mV running / 230 mV stall, ADC on D1) |
| Microswitch, lever type | 2 | The alternative to stall sensing: deterministic end-of-travel detection, zero calibration |


## LaskaKit ([laskakit.cz](https://www.laskakit.cz)) — for the gaps
- Tactile switch **6×6×12 mm** (if the bin's buttons are taller than Hadex's 8 mm), 2 Kč —
  [link](https://www.laskakit.cz/tlacitko-6x6x5mm/) (height is a variant on that page)
- **JST PH 2.0** 4-pin cable 8 Kč ([link](https://www.laskakit.cz/jst-ph-4-2mm-4pin-konektor-s-20cm-vodici/)),
  or PCB header + housing + crimps ≈ 6 Kč ([link](https://www.laskakit.cz/jst-ph-2mm-konektor-do-dps/))
- Resistors Yageo MFR-25 1/4 W 1 %, 1 Kč each

## Botland ([botland.cz](https://botland.cz)) — only if the ToF sensor changes
- DFRobot **SEN0245** Gravity VL53L0X ToF — **330 Kč**, in stock
- DFRobot **SEN0315** Gravity PAJ7620U2 gesture — **275 Kč**, in stock (MicroPython support thin)
- Pololu VL6180X carrier — 440 Kč (only buy if the owned breakout turns out to lack the
  3.3 V regulator/level shifter)

## Not stocked in Czechia
Vishay TSSP4038 (the proper reflective-IR presence receiver) — TME lists it at 0 stock;
RS Components CZ has it. Bare L9110S chip — only robotelektro.cz, on order, 22 Kč.
GME has genuine Vishay TSOP4838 (18 Kč) and TSAL6100 IR LED (5 Kč) if a clone won't do, but its
minimum order quantities (BC337 min 24, 220 µF min 18, resistors min 5) push a GME-only cart to
~150–180 Kč.

## Open measurements before ordering
1. **Button height** — board surface to top of the black cap (Hadex tops out at 8 mm).
2. **Bin connector pin pitch** — 2.0 mm = JST PH (LaskaKit), 2.5 mm = JST XH (Hadex).
3. **VL6180X breakout markings** — confirm it has a regulator + level shifter before 3.3 V.
4. **Real motor current** — multimeter in series, running and stalled by hand. The 70/230 mA
   figures are from patent literature, not this motor. **If it stalls above ~500 mA the L9110S has
   almost no margin** and the driver choice has to change. This is the single assumption that could
   invalidate the design.
