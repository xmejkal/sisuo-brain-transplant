"""
Bring-up step 6 — the whole bin, all at once.

Steps 1 to 5 prove one part each, with a throwaway script per part. This one runs the REAL
firmware — the same `build()` that `main.py` calls, the same strategies config.py names — and
asks it to do the job end to end while you watch. It is the last thing to pass before the bin is
worth putting back in its shell.

    mpremote cp -r smartbin : && mpremote cp config.py :      # the firmware must be on the device
    mpremote run bringup/06_all_together.py

Wire everything: sensor, both buttons, the LED, the amplifier and the motor, exactly as steps
2 to 5 had them. **The lid must be free to move through its whole travel**, or out of the bin
altogether — this drives real strokes, not pulses.

It runs in two halves:

  * a roll call, which asks every fitted device to prove it is there before anything moves;
  * three prompted phases — wave, press OPEN, press MODE — each of which states what it expects
    to see, then reports whether it saw it.

The verdict at the end is per-phase, because "it did not work" is not a useful bench result:
what you need to know is which of the three ways in failed, and whether the lid came back to
IDLE afterwards.

Nothing here is a fake. If this passes, the firmware works on this hardware.
"""

import sys

sys.path.insert(0, "/")

try:
    import asyncio
except ImportError:
    import uasyncio as asyncio

import config  # noqa: E402

from smartbin import build  # noqa: E402
from smartbin import events, states, status_led  # noqa: E402
# Ticks come from the firmware's own shim, never from `time` directly: MicroPython's ticks wrap
# and CPython has none, and this script is checked against the fake chip on a Mac as well as run
# on the bench.
from smartbin.timing import async_sleep_ms, sleep_ms, ticks_add, ticks_diff, ticks_ms  # noqa: E402

# How long each prompted phase waits for you to do the thing it asked for. A full open-hold-close
# cycle takes LID_OPEN_RUN_MS + LID_OPEN_HOLD_MS + LID_CLOSE_RUN_MS, so this has to comfortably
# exceed that plus human reaction time.
PHASE_SECONDS = 15
MOTOR_NUDGE_MS = 250       # roll call only: long enough to see, far too short to reach a stop
SETTLE_MS = 400            # let a stroke's own task finish before the next phase is announced
LED_STEP_MS = 400


def announce(text):
    """Bench output is a transcript someone reads later, so every line is timestamped."""
    print("[%7d] %s" % (ticks_ms(), text))


class Transcript:
    """
    Records every event the bin publishes, so a phase can be judged on what actually happened.

    It is an ordinary listener — the same interface the LED and the sounds use — which is the
    point: watching the bin from outside needs no hook inside it.
    """

    def __init__(self):
        self.seen = []

    def __call__(self, event, **event_data):
        self.seen.append(event)
        detail = " ".join("%s=%s" % pair for pair in event_data.items())
        announce("  event: %s %s" % (event, detail))

    def start_phase(self):
        self.seen = []

    def saw(self, event):
        return event in self.seen

    def missing(self, expected):
        return [event for event in expected if event not in self.seen]


def roll_call(smart_bin):
    """
    Ask every fitted device to answer before anything moves.

    A part that is silent here is a wiring fault, and finding it now costs one line of output
    instead of a confusing phase failure later.
    """
    hardware = smart_bin.hardware
    problems = []

    announce("configuration: sensor=%s close=%s power=%s audio=%s" % (
        config.SENSOR_STRATEGY, config.CLOSE_DETECTOR, config.POWER_POLICY, config.AUDIO_ENABLED))

    if hardware.sensor_bus is not None:
        found = hardware.scan_i2c()   # already formatted as hex strings
        announce("I2C: %s" % (found,))
        if not found:
            problems.append("no I2C device answered — check SDA/SCL, 3V3 and GND")

    if hardware.rangefinder is not None:
        try:
            announce("rangefinder: %d mm" % hardware.rangefinder.range())
        except Exception as error:  # noqa: BLE001 - any failure here is a bench fact, not a crash
            # An empty room legitimately gives a range error, so this is reported, not failed.
            announce("rangefinder: no measurement (%s) — fine if nothing is in front of it" % error)

    announce("audio: shutting the amplifier down until a cue asks for it")
    try:
        hardware.player.initialize()
    except Exception as error:  # noqa: BLE001
        problems.append("audio did not initialise: %s" % error)

    announce("LED: red, green, amber, off")
    for colour in (status_led.RED, status_led.GREEN, status_led.AMBER, status_led.OFF):
        hardware.led.set(colour)
        sleep_ms(LED_STEP_MS)

    announce("motor: a nudge each way (the lid should twitch open, then shut)")
    for opening, speed in ((True, config.MOTOR_OPEN_SPEED), (False, config.MOTOR_CLOSE_SPEED)):
        hardware.motor.drive(opening, speed)
        sleep_ms(MOTOR_NUDGE_MS)
        hardware.motor.stop()
        sleep_ms(MOTOR_NUDGE_MS)

    return problems


# The phase now being asked for, or None. Published so that the off-bench check in
# tests/test_bringup.py can play the part of the person at the bench — pressing the right button
# at the right moment — and so prove that each way in really is wired to what it claims.
CURRENT_PHASE = None


async def run_phase(transcript, phase, instruction, expected, lid):
    """One prompted phase: say what to do, wait, then report what arrived."""
    global CURRENT_PHASE
    CURRENT_PHASE = phase
    transcript.start_phase()
    announce("")
    announce("=> %s   (%d seconds)" % (instruction, PHASE_SECONDS))

    deadline = ticks_add(ticks_ms(), PHASE_SECONDS * 1000)
    while ticks_diff(deadline, ticks_ms()) > 0:
        if not transcript.missing(expected):
            break
        await async_sleep_ms(100)

    await async_sleep_ms(SETTLE_MS)
    CURRENT_PHASE = None
    missing = transcript.missing(expected)
    if missing:
        announce("   FAIL — never saw: %s" % ", ".join(missing))
    else:
        announce("   pass")
    announce("   lid is now %s" % lid.state)
    return missing


async def exercise(smart_bin, transcript):
    """The three ways a bin is asked to open, each checked separately."""
    cycle = [
        events.state_entered(states.OPENING),
        events.state_entered(states.OPEN),
        events.state_entered(states.CLOSING),
        events.state_entered(states.IDLE),
    ]
    failures = {}

    if config.SENSOR_STRATEGY != "none":
        failures["wave"] = await run_phase(
            transcript, "wave", "WAVE a hand in front of the sensor", cycle, smart_bin.lid)
    else:
        announce("no sensor fitted (SENSOR_STRATEGY='none') — skipping the wave phase")

    failures["open button"] = await run_phase(
        transcript, "open", "PRESS the OPEN button", cycle, smart_bin.lid)

    failures["mode button"] = await run_phase(
        transcript, "mode", "PRESS the MODE button (the sound profile should change)",
        [events.MODE_CHANGED], smart_bin.lid)

    return failures


async def main():
    smart_bin = build(config)
    transcript = smart_bin.bus.subscribe(Transcript())

    announce("---------------- roll call")
    problems = roll_call(smart_bin)
    if problems:
        for problem in problems:
            announce("   FAIL — %s" % problem)
        announce("\nStopping: fix the wiring before running the lid.")
        smart_bin.hardware.enter_safe_state()
        return 1

    announce("---------------- running the firmware")
    running = asyncio.create_task(smart_bin.main())
    await async_sleep_ms(SETTLE_MS)

    try:
        failures = await exercise(smart_bin, transcript)
    finally:
        # Cancelling another task is fine; a task cancelling *itself* is not, which is why this
        # is here and not inside the bin.
        running.cancel()
        await async_sleep_ms(SETTLE_MS)
        smart_bin.hardware.enter_safe_state()

    announce("")
    announce("---------------- verdict")
    for phase, missing in failures.items():
        announce("  %-12s %s" % (phase, "FAIL" if missing else "pass"))
    if smart_bin.lid.state != states.IDLE:
        announce("  lid did not return to IDLE — it is %s" % smart_bin.lid.state)

    failed = [phase for phase, missing in failures.items() if missing]
    if failed:
        announce("\nFAIL: %s. The transcript above shows how far each got." % ", ".join(failed))
        return 1

    announce("\nPASS — the bin opened on a wave, on the button, and changed sounds.")
    announce("Next: calibrate the stroke times with tools/calibrate.py, then measure the motor's")
    announce("running and stalled current before trusting the driver choice.")
    return 0


# Guarded so the checks can import this file, shrink the phases and drive it against the fake
# chip. On the bench `mpremote run` makes __name__ "__main__" and it runs as written.
if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
