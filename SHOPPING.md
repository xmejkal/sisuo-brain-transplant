# Shopping list — Czech shops (prices checked 2026-09-23)

> **Updated 2026-09-25.** Two changes since this list was first written, and one correction
> that would have wasted a parcel.
>
> The microcontroller is a DFRobot FireBeetle 2 ESP32-S3, not a XIAO ESP32-C6 — the cell plugs
> into the module, so the board carries no LiPo connector. **The audio is now I2S**: a DFR0954
> MAX98357A amplifier, with the ESP32 synthesising the tones. There is no UART MP3 module on the
> board any more, and no switched rail for one.
>
> **The correction: this list was buying through-hole passives for a board with SMD pads.**
> Every resistor and capacitor on the board except the bulk electrolytic is **0603 SMD**
> (`res0603` / `cap0603` in `board.tsx`). The old entries bought RC0204 axial resistors and
> 5 mm-pitch capacitors, which do not fit those pads at all. The shunt was listed as 1 Ω when the
> design needs **0.1 Ω in 2512** — a tenfold error in what the stall detector would read.

Petr is in Czechia and buys single pieces. **Hadex** is cheapest and covers nearly everything;
LaskaKit fills the gaps (JST PH, taller buttons, proper 1/4 W resistors). Shipping costs more
than the parts, so spares are worth adding. Prices are CZK incl. VAT, per piece.

## Already owned — do NOT buy
LiPo · **L9110S dual motor driver module** (blue, HG7881 type; also owns an L298N
and an A4988 stepper driver, both unsuitable) · **a DFRobot audio module — identity UNCONFIRMED,
see below** · DFRobot speaker ·
**VL6180X ToF sensor** (see [parts/SENSOR_OPTIONS.md](parts/SENSOR_OPTIONS.md)) · breadboards,
jumper wires, perfboard.

> **This line said "DFR0534 MP3 module" from the first commit and nobody recorded who checked.**
> That single unverified word is the root of the project's longest-standing blocker: the board
> was drawn twice for a module nobody had looked at. It is a five-second test —
> **microSD slot** → DFPlayer Mini (DFR0299); **micro-USB, no card slot, "Voice Module V1.0"**
> on the silkscreen → DFR0534; pads marked **BCLK / LRC / DIN** → the I2S amplifier.
> The current board assumes the last of those. Until somebody looks, the entry below for a
> DFR0954 is "buy unless you already have it", not "buy".
The original Sisuo board stays **untouched** — nothing gets desoldered from it.

**XIAO ESP32-C6** — owned, but no longer the design's board. Kept as a spare; `boards/` still
carries its definition, so switching back is one line in `boards/active.json`.

## Confirm before ordering anything else
**DFRobot FireBeetle 2 ESP32-S3** — the design now assumes one. **Do you already have it?**
Either SKU works, the header pinout is identical: **DFR0975** (N16R8, 16 MB flash + 8 MB PSRAM)
or **DFR1145** (N4, 4 MB, no PSRAM). The N4 is the cheaper and entirely sufficient one — nothing
in this firmware uses PSRAM. Beware **DFR1154**, which is a different product (an ESP32-S3 AI
camera board) with a different pinout.
It needs **two 2.54 mm female headers, 1x18 and 1x14** (or a 1x40 strip cut down) to sit on the
PCB — the rows are **22.86 mm** apart.

## Buy — Hadex ([hadex.cz](https://www.hadex.cz)), all in stock

| Part | Qty | Kč ea | Link |
| --- | --- | --- | --- |
| Tactile switch 6×6, **height TBD** (4.3 / 5 / 8 mm variants, 2 Kč each) | 10 | 2 | [KFC-A06-5](https://www.hadex.cz/p/l367-mikrospinac-kfc-a06-5-6x6mm-v-5mm) |
| LED 5 mm bicolour red/green, common cathode (3 leads) | 3 | 4 | [K130A](https://www.hadex.cz/p/k130a-led-5mm-dvoubarevna-r-g-40-45mcd-20ma-50-cira) |
| Capacitor 220 µF / 16 V **radial THT, 6×11 mm** | 5 | 1 | [I845](https://www.hadex.cz/p/i845-220u-16v-105-6x11x3-5mm-elektrolyt-kondenzator-radialni) |

The 220 µF is the **only** through-hole passive on this board: `MotorBulkCap` is `doNotPlace`,
hand-soldered, and deliberately not on the assembler's list. Everything else is 0603 SMD — see
the table below, which is derived from the board rather than written beside it.
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
| Capacitor 100 nF (extra, THT) | 2 | One goes **across the motor brushes**, at the motor itself — not on the board. Brush arcing, not inductive kickback, is what upsets I2C and IR receivers |
| Capacitor 4.7 µF + resistor 100 Ω | 5 each | Supply filter at the IR receiver. Its datasheet **requires** this, it is not optional |
| Resistor 470 Ω | 10 | IR LED transistor base (supersedes the 1 kΩ if we drive the LED hard: 470 Ω saturates BC337 at 100 mA) |
| Resistor 15 Ω and 22 Ω | 5 each | IR LED series resistor if 100 Ω gives too little range (100 Ω ≈ 20 mA, 15 Ω ≈ 100 mA pulsed) |
| ~~Resistor 1 Ω 0.5 W metal film~~ | — | **Wrong. The design uses 0.1 Ω in 2512** — see the SMD table below. 1 Ω would drop ten times the voltage and steal that much more of the motor's supply |
| Microswitch, lever type | 2 | The alternative to stall sensing: deterministic end-of-travel detection, zero calibration |



### The board's own passives — **0603 SMD**, generated from the netlist

Derived from `dist/board/circuit.json`, not written alongside it, because the two drifted once
already: this list bought axial RC0204 resistors and 5 mm-pitch capacitors for pads that are
0603. Regenerate after any board change.

Hadex and LaskaKit both stock 0603 in assortment books, which is the sane way to buy these —
single values cost almost the same as a book of twenty. **These are hand-solderable but small;**
if that is unwelcome, the alternative is changing the footprints in `board.tsx` to 0805 or
through-hole, which is a board change and not a shopping decision.

| Value | Package | On board | Buy | What for |
| --- | --- | --- | --- | --- |
| **1 kΩ** | 0603 | 1 | 10 | series into the shunt ADC |
| **1 µF** | 0603 | 1 | 10 | filter on the shunt sense line |
| **10 kΩ** | 0603 | 2 | 10 | hold the L9110S inputs down while the MCU's pins are high-Z — after reset, during a reflash. Must be external: internal pulls are inactive in exactly that window |
| **100 kΩ** | 0603 | 2 | 10 | hold each deep-sleep wake input at a defined level while the chip is off |
| **100 nF** | 0603 | 4 | 20 | decoupling, one per module |
| **2.2 kΩ** | 0603 | 2 | 10 | I2C pull-ups. The board carries its own because a V1.2+ FireBeetle has none |
| **330 Ω** | 0603 | 2 | 10 | status LED series, one per colour |
| **100 mΩ** | 2512 | 1 | 10 | current-sense shunt. 2512 for the dissipation: 0.225 W at the driver's 1.5 A limit, against a 1 W part |

Plus **1× 220 µF radial THT** (`MotorBulkCap`, hand-soldered) and **1× 100 nF THT** across the
motor brushes, at the motor.


### Modules and headers the board mates with

Every module is plug-in — nothing is soldered down — so each needs a **2.54 mm female header** on
the board and the module's own pins through it. Row spacings are from the footprints in
`board.tsx`, and getting one wrong means a module that will not seat.

| For | Header | Note |
| --- | --- | --- |
| **FireBeetle 2 ESP32-S3** | 1×18 + 1×14 female | rows **22.86 mm** apart. A 1×40 strip cut down is fine |
| **DFR0954 I2S amplifier** | 2× 1×6 female | rows **15.24 mm** apart. 12 castellated pads, no pad-1 marker — see `Dfr0954I2sAmp.tsx`, which places them by name for that reason |
| **L9110S motor driver** | 1×6 female | `headermodule6` |
| **VL6180X**, off-board | 1×5 female | `pinrow5`. The sensor looks out through the lid on a five-wire ribbon (VIN, GND, SDA, SCL, INT), so only the ribbon's connector is on the board |
| **Status LED**, off-board | 1×3 female | `pinrow3`, bicolour common cathode |
| **Speaker** | JST PH 2-pin | `jst_ph_2` |
| **Bin connector** | JST PH 4-pin | `jst_ph_4` — **pitch unconfirmed.** 2.0 mm is PH, 2.5 mm is XH, and they do not mate. Measure the bin's own plug before buying either |

**The amplifier itself** — DFRobot **DFR0954** (MAX98357A), ~250 Kč. Buy **only if the module in
the drawer is not already one**; see the note under *Already owned*. If it turns out to be a
DFR0534 instead, buy nothing: `board-v3-dfr0534.tsx` is the design that fits it and
`config.AUDIO_STRATEGY = "dfr0534"` is the firmware side, with no sound profile changes.

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

## Open questions before ordering
0. **Which audio module is in the drawer.** Everything in the audio path turns on it, and it is
   a look, not a measurement. See the note under *Already owned*.
1. **Button height** — board surface to top of the black cap (Hadex tops out at 8 mm).
2. **Bin connector pin pitch** — 2.0 mm = JST PH (LaskaKit), 2.5 mm = JST XH (Hadex).
3. **VL6180X breakout markings** — confirm it has a regulator + level shifter before 3.3 V.
   The board wires a five-wire ribbon, which suits the Adafruit 3316 and the Pololu 2489; the
   generic GY-VL6180 boards vary between factories and were not checked.
4. **Real motor current** — multimeter in series, running and stalled by hand. The 70/230 mA
   figures are from patent literature, not this motor. **If it stalls above ~500 mA the L9110S has
   almost no margin** and the driver choice has to change. This is the single assumption that could
   invalidate the design. Note that `.spark/rules.json` states 1.5 A for the motor rail — that is
   the L9110S's own limit used to size copper, **not** a measurement of this motor, and the two
   must not be confused.
5. **Whether hand-soldering 0603 is acceptable.** If not, that is a board change (0805 or
   through-hole footprints in `board.tsx`), not a shopping decision — decide before buying a
   reel of the wrong size.
