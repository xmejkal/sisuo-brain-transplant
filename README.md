# Sisuo brain transplant

A sensor-operated trash can whose control board died. Rather than bin the bin, its brain was
replaced: a **Seeed XIAO ESP32-C6** running MicroPython, driving the original motor, with a new
PCB designed in code.

![The routed board](board-pcb-routed.svg)

## Status, honestly

| Part | State |
| --- | --- |
| Firmware | Written, 60 tests passing, and **simulated end to end on a real MicroPython runtime** |
| PCB | v1 routed with real footprints and a fab package — now superseded by the v2 parts decisions |
| Hardware | **Nothing has been run on a bench yet.** Parts are still being ordered |

Everything here is verified by tests and simulation, not by a working bin. Where something is
unproven, the docs say so.

## How the lid behaves

The behaviour is a transition table rather than a pile of conditionals, so it can be read as a
picture — generated from the code itself by `tools/fsm_diagram.py`:

```mermaid
stateDiagram-v2
    [*] --> idle
    idle --> opening: hand_detected
    idle --> opening: open_pressed
    opening --> open: stroke_finished
    open --> open: hand_detected
    open --> closing: hold_expired
    closing --> idle: close_confirmed
    closing --> obstructed: safety_cap_tripped
    closing --> obstructed: hand_detected
    obstructed --> open: stroke_finished
    obstructed --> fault: retry_limit_reached
    fault --> idle: open_pressed
```

The original bin failed by retrying a close forever, waiting for a signal that never came. This
one reopens, retries a fixed number of times, then latches a fault and waits for a person.

## What's interesting here

* **The safety cap is structural.** Every motor stroke is bounded inside its own loop and stops
  in a `finally`, so no sensor, detector or calibration mistake can burn the motor.
* **Strategies for what the hardware hasn't decided.** How a hand is noticed (time-of-flight,
  infrared, or buttons only), how "shut" is known (timed, limit switch, or motor stall), and
  what idling costs (stay awake or deep sleep) are each one line of config.
* **Sounds are data.** A profile maps "state entered" to a track number, so re-voicing the bin
  never means touching code. The MODE button cycles profiles and remembers the choice.
* **Three layers of testing**, none of which needs the hardware — and the middle one found a real
  bug: a hand left in front of the sensor held the lid open until the battery would have died.

## Testing

```sh
cd firmware/micropython
python3 -m unittest discover -s tests -t tests   # 60 tests, ~1 s, no hardware
micropython sim/run_on_micropython.py            # the whole firmware on a MicroPython runtime
```

The second one matters: MicroPython's asyncio is not CPython's — a task cannot cancel itself —
and the firmware does exactly that on every lid stroke. A fake that was more forgiving than the
device once hid a bug that would have frozen the lid after a single open.

## Layout

```
firmware/micropython/   the firmware — start at smartbin/__init__.py, which is a guided tour
firmware/arduino/       the first version, kept for reference
board.tsx               the PCB, in code (tscircuit)
parts/                  datasheets, pinouts, and the sensor research
sim/                    simulation: MicroPython runtime and Wokwi
```

Design notes worth reading: [`FIRMWARE_PLAN.md`](FIRMWARE_PLAN.md) (architecture and the audit
that reshaped it), [`parts/SENSOR_OPTIONS.md`](parts/SENSOR_OPTIONS.md) (why a time-of-flight
sensor, and what its datasheet demands of the lid window),
[`LID_CLOSE_DETECTION.md`](LID_CLOSE_DETECTION.md) (how motorised bins actually detect a closed
lid, with patents), and [`TEST_PROTOCOL.md`](TEST_PROTOCOL.md) (reverse-engineering the dead
board with a multimeter).

## Hardware

Seeed XIAO ESP32-C6 · L9110S H-bridge driving the bin's original motor · VL6180X time-of-flight
sensor · DFRobot DFR0534 MP3 module and speaker · two buttons and a bicolour status LED.
Logic and audio run from a LiPo; the motor keeps the bin's own 6 V pack, sharing only ground.
