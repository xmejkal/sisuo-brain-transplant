# How motorized bin lids detect "closed" — research

Question: is motor stall/current sensing really how the Sisuo detects the lid is closed?
Answer: it's one of three real methods. Stall sensing is the most likely for this bin, but it
must be confirmed at the bench — and for the ESP32 rebuild we get to choose, so it doesn't gate us.

## The three methods actually used (with sources)

1. **Motor current / stall sensing** — a small sense resistor in the motor's ground path; the MCU
   reads the voltage across it on an ADC. When the lid hits the end stop the motor stalls and
   current spikes; the MCU sees the spike and cuts power. No extra sensors.
   - US11973450B2 "Current detection circuit and garbage can" — sense resistor → ADC, duty-cycle
     modulated, "judge whether a cover is opened and closed in place." https://patents.google.com/patent/US11973450
   - US11390458 "Power-saving control device for an electronic garbage can" — **states ~70 mA
     running, ~230 mA stalled, 200 mA threshold, checked every 25 ms.** These are the exact numbers
     our reverse-engineering used → this bin is very likely this class of design.
     https://patents.justia.com/patent/11390458

2. **Timed run (open reverse for N seconds), no feedback** — cheapest; the MCU just runs the motor
   a fixed time. Sometimes paired with mechanical end-stops so the gears simply jam at the limit.
   - WO2018184318A1 — "motor rotated 1 s to open… reversed 1 s to close," no position sensing.
     https://patents.google.com/patent/WO2018184318A1
   - EP2289821A1 — mechanical blocked-section stops + a timer. https://patents.google.com/patent/EP2289821A1

3. **Optical / position feedback** — higher-end bins: a flag on the lift arm crosses paired
   emitter/receiver sensors, or a servo's internal potentiometer reports angle.
   - US8686676B2 (simplehuman-class) — optical position detectors + flag. https://patents.google.com/patent/US8686676B2
   - Kpower BLDC article — servo with internal pot feedback. https://www.kpower.com/insight_bldc/7617.html

## Why stall is the best fit for the Sisuo (but still a hypothesis)
- No limit microswitches or optical position flags were found in the reverse-engineering — that
  rules method 3 out and leaves timed vs stall.
- The observed fault ("drives closed, never detects it, retries forever even when the lid is held
  shut") is a **broken close-confirmation loop** — a purely timed design wouldn't retry forever,
  it would just run its fixed time and stop. Retrying implies the board is *waiting for a signal
  that never comes*.
- Our hypothesized "STALL" line (rail/sense divider → MCU ADC) is exactly method 1's wiring.
- The 70/230 mA figures match US11390458 almost exactly.
- **Confirm at the bench:** probe the suspected sense line / motor-ground while cycling the lid and
  watch for the current-rise-at-stall (TEST_PROTOCOL.md). That's the one measurement that proves it.

## What this means for the ESP32 rebuild
We choose the close-detection method; the original's doesn't constrain us.
- **Start: timed close** — calibrate "close = run reverse ~N seconds." Simplest, no extra parts,
  matches the cheap-bin approach. Good enough to get moving.
- **Robust upgrade: current/stall sensing** — needs either a sense resistor on the motor ground +
  an ADC pin, or a motor-driver breakout that exposes current. Adds a touch of analog (against the
  "minimize analog" goal), so treat as a v2 once the mechanism is understood.
- **Safety in both cases:** cap the close time and/or current so a blocked lid never burns the motor.
- Hand-wave to OPEN stays on the digital IR module regardless.
