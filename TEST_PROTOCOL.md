# Bench test protocol — confirm the reconstruction & identify the parts

Goal: with a multimeter, (1) confirm the reconstructed connections and (2) narrow down
which exact parts these are. Work top to bottom; each test says what result confirms what.
Write your reading in the "you measured" column and we'll update the schematic.

## Setup
- Board **out of the bin, batteries OUT** for all continuity/resistance tests (Parts A–D, F).
- Multimeter modes used: **continuity (beep)**, **resistance (Ω)**, **DC volts** (Part E only, batteries in).
- Pin 1 on an SOP chip = the pin by the dot/notch, counting anticlockwise from the top.
- Reference names: **U1** = 14-pin chip (MCU), **U2** = 8-pin chip (driver), **J1** = 4-pin connector.

## Your instruments
- **Multimeter** *(model not on file — tell me which and I'll note it)*: the workhorse for Parts A–D and F (continuity, resistance, DC volts).
- **Hantek 6022BL** (USB scope + 16-ch logic analyzer), with **PulseView/sigrok on the Raspberry Pi** and **OpenHantek6022 on the Pi/Mac**: adds the *dynamic* tests the multimeter can't do (Part E + optional capture).
  - **Scope safety:** input tolerates only **±5 V at ×1**. The 6 V rail/motor exceeds that, so set the probe switch to **×10 before probing anything on the 6 V rail or motor**.
  - **Logic-analyzer safety:** its channels are **0–5.5 V TTL** — never feed the raw 6 V rail into a logic input; use the scope with ×10 for anything above 5 V.

---

## Part A — Confirm the resistor values (resistance mode)
The printed codes we read: R2 & R4 = `101` (100 Ω), R5 = `151` (150 Ω), R1 = `331` (330 Ω), **R3 = ?**.

- [ ] Read the code printed on **R3** (three digits) and measure it → tells us its role.
- [ ] Measure R5 → expect ~150 Ω. Confirms the IR-emitter series resistor.
- [ ] Measure R1 → expect ~330 Ω. Confirms the status-LED resistor.
- [ ] Measure R2, R4 → expect ~100 Ω each (in-circuit may read a bit low — that's fine).

*Why:* the values tell us which resistor does which job before we even trace them.

---

## Part B — Confirm the connector J1 (continuity)
- [ ] Probe each J1 pin against **U2 pin 5/6** and **U2 pin 7/8**. The two J1 pins that beep to the driver outputs are the **MOTOR pair** (and this tells us which J1 pin is MOTA vs MOTB).
- [ ] Of the remaining two J1 pins, the one that beeps to the board's ground/copper pour is **BAT−**; the other is **BAT+**.
- [ ] Note the actual order → this replaces my guessed J1 pin order.

---

## Part C — Confirm the driver U2 & prove it's the RZ7899/TA6586 family
This IC family has a signature: the two motor outputs are each **doubled** (pins 5+6 tied, 7+8 tied).

- [ ] U2 **pin 5 to pin 6** → should beep (tied). U2 **pin 7 to pin 8** → should beep (tied).
- [ ] U2 **pin 3** → beeps to GND pour. U2 **pin 4** → beeps to the VM rail (C1 + / U1 VDD).
- [ ] U2 **pins 1 and 2** → do NOT beep to power or ground; they trace back toward U1.
- [ ] U2 pins 5/6 beep to one J1 motor pin; 7/8 to the other.

*Result:* if all of that holds, it's **near-certainly RZ7899 / TA6586** (or the pin-identical AM7899/FM7899). If pins 5≠6 or the middle isn't GND/VCC, it's a **different driver** and we re-identify.

---

## Part D — Map the MCU U1 pins (continuity)
For each, probe U1's pins one by one until it beeps to the target; note the U1 pin number.

- [ ] U1 pin that beeps to **VM rail** = VDD. U1 pin that beeps to **GND** = VSS.
- [ ] U1 pin that beeps to **U2 pin 1 (FIN)** = the OPEN command line.
- [ ] U1 pin that beeps to **U2 pin 2 (RIN)** = the CLOSE command line.
- [ ] U1 pin that connects **through R5** to the clear IR-emitter LED = IR drive.
- [ ] U1 pin that connects to the **IR receiver** output = IR sense.
- [ ] Each **button**: one leg to a U1 pin, the other leg to GND. Note both U1 pins.
- [ ] U1 pin that connects **through R1** to the status LED = LED drive.

---

## Part E — Identify the stall-detection method (the key open question)
We saw **no low-value shunt** in the motor return, so the theory is **supply-rail sag into an MCU analog pin**. Two checks:

- [ ] **Divider hunt (Ω mode, unpowered):** find any U1 pin that reaches the VM rail *through a resistor* (not a direct beep) **and** reaches GND *through a resistor*. Measure both. Two sensible values (kΩ range) = a **voltage divider** = supply-sag stall sense. If no such divider exists, the board likely used **blind timed drive**.
- [ ] **Sag test (DC volts, batteries IN):** probe across the battery terminals, watch during a close attempt. A drop of a few hundred mV when the motor jams = the signal the MCU watches. (This matches the live diagnosis: it kept retrying, waiting for a stall it never registered.)
- [ ] Confirm the motor OUT pins run **straight** to J1 with no series resistor (rules out a shunt).

### With the Hantek (better than the multimeter for the dynamic behaviour)
- [ ] **Scope the rail sag** (OpenHantek, **×10 probe**): probe VM vs GND, timebase ~100 ms/div, single-shot trigger, power-cycle so the board attempts a close. A dip of a few hundred mV as the motor jams = the stall signal; you can measure how big and how long it is (the multimeter can't show the shape).
- [ ] **Scope the IR emitter** (**×10**): probe across the clear IR LED at idle — periodic pulses confirm the IR-drive net and reveal the strobe rate.
- [ ] **Optional — logic-analyzer capture** (PulseView on the Pi): clip logic channels onto the two MCU→driver command lines (FIN/RIN, ≤5 V logic) and the IR-drive line; capture during a close attempt. This records the exact command sequence the dead brain emits — a portfolio artifact and the reference for what the ESP32 must reproduce. **Keep the 6 V rail off the logic inputs.**

---

## Part F — Narrow the MCU identity (honest limits)
The MCU is house-marked, so an exact part number isn't provable electrically — but we can class it:

- [ ] Does U1 **VDD beep directly to the 6 V rail** (no regulator)? If yes → a wide-Vdd OTP micro (Padauk PMS/PFS or Cmsemicon CMS79F class), which is the expected family.
- [ ] Count analog-capable pins in use (IR sense + any stall divider). ADC use → narrows to ADC-equipped parts (e.g. Padauk PMS132/PMS154, Cmsemicon CMS79F-series).
- Beyond class, exact ID would need decapping — not worth it. We treat it as "replace, don't identify."

---

## Educated part guesses (to confirm/refute with the tests above)

| Ref | Best guess | Confidence | Test that decides |
| --- | --- | --- | --- |
| U2 (8-pin) | RZ7899 / TA6586 H-bridge (Wuxi Ruizhi / RZ-MIC) | High (family) | Part C signature |
| U1 (14-pin) | Padauk PMS132-class or Cmsemicon CMS79F-class OTP MCU | Low (house-marked) | Part F (class only) |
| D_IR | 3–5 mm clear IR LED (~940 nm) | High | visual + Part D |
| Q_RX | Reflective IR photodiode/phototransistor | Med | Part D |
| D_ST | Bi-colour red/green indicator LED | Med | Part D |
| SW1/SW2 | 6 mm tactile switches | High | visual |
| J1 | 4-pin JST (PH 2.0 mm or XH 2.5 mm) | Med | measure pitch |
| R5 / R1 / R2,R4 | 150 Ω / 330 Ω / 100 Ω | High (printed) | Part A |
| C1 | Bulk cap on rail (electrolytic/tantalum) | Med | visual |

When you send back the readings, I'll lock the reconstruction, fix any net I got wrong, and update the schematic.
