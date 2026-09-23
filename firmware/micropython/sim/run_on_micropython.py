"""
Run the real firmware, on a real MicroPython runtime, with a fake chip underneath it.

    micropython sim/run_on_micropython.py     # real MicroPython semantics — the point of this
    python3     sim/run_on_micropython.py     # same script under CPython, as a sanity check

This is the layer between the unit tests and Wokwi, and it is the cheapest way to catch the
mistakes that only MicroPython makes: its asyncio is not CPython's (a task cannot cancel itself),
its ticks wrap, and its compiler accepts a different subset of the language.

It drives a whole lid cycle through the buttons and the sensor, and prints the firmware's own
transition log as it goes, so what you read is what the bin would do.
"""

import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests")     # fake_machine lives with the tests that use it
sys.path.insert(0, "sim")

import fake_machine  # noqa: E402

fake_machine.install()          # must precede any import that reaches the hardware

import asyncio  # noqa: E402

import config as real_config  # noqa: E402

from smartbin import assembly, states  # noqa: E402
from smartbin import log  # noqa: E402
from smartbin.timing import async_sleep_ms  # works on both runtimes  # noqa: E402

OPEN_BUTTON = real_config.PIN_BUTTON_OPEN
HAND_DISTANCE_MM = 60
NOTHING_THERE_MM = 200


class Settings:
    """The real configuration with the timings scaled down, so a cycle takes under a second."""

    def __init__(self):
        for name in dir(real_config):
            if name.isupper():
                setattr(self, name, getattr(real_config, name))
        self.LID_OPEN_RUN_MS = 120
        self.LID_CLOSE_RUN_MS = 120
        self.LID_OPEN_HOLD_MS = 200
        self.MAX_OPEN_MS = 600
        self.MOTOR_MAX_RUN_MS = 400
        self.SENSOR_POLL_MS = 20
        self.BUTTON_POLL_MS = 10
        self.IDLE_TICK_MS = 20
        self.WATCHDOG_MS = 0
        self.REPL_ENABLED = False
        # Short enough that a hand held in the beam is noticed again while the lid is closing,
        # which is what makes the obstruction check below mean anything.
        self.SENSOR_COOLDOWN_MS = 80
        self.MAX_CLOSE_RETRIES = 2
        # This scenario waves a hand at the rangefinder, so it pins that configuration rather
        # than inheriting whatever config.py ships with. Changing the shipped default should not
        # break a harness that is about a different build.
        self.SENSOR_STRATEGY = "tof"
        self.CLOSE_DETECTOR = "timed"
        self.POWER_POLICY = "always_on"

    def save(self, values):
        return True


def build():
    fake_machine.reset()
    fake_machine.FakeI2C.devices[0x29] = fake_machine.FakeVL6180X(distance_mm=NOTHING_THERE_MM)
    return assembly.build(Settings())


def motor_state(smart_bin):
    duty_a = smart_bin.hardware.motor_pwm_a.duty
    duty_b = smart_bin.hardware.motor_pwm_b.duty
    if duty_a:
        return "opening at duty %d" % duty_a
    if duty_b:
        return "closing at duty %d" % duty_b
    return "stopped"


async def press_open(smart_bin, hold_ms=60):
    fake_machine.FakePin.by_number[OPEN_BUTTON].value(0)
    await async_sleep_ms(hold_ms)
    fake_machine.FakePin.by_number[OPEN_BUTTON].value(1)
    await async_sleep_ms(40)


async def wait_for_state(smart_bin, state, timeout_ms=4000, step_ms=20):
    """
    Wait until the lid reaches `state`, or give up.

    Polling beats a fixed sleep: the simulation runs at whatever speed the host manages, so
    guessing a duration makes a test that fails for the wrong reason.
    """
    waited_ms = 0
    while waited_ms < timeout_ms:
        if smart_bin.lid.state == state:
            return True
        await async_sleep_ms(step_ms)
        waited_ms += step_ms
    return False


def set_distance(millimetres):
    fake_machine.FakeI2C.devices[0x29].distance_mm = millimetres


class Checks:
    """Tiny pass/fail recorder, so this script is a test rather than a demonstration."""

    def __init__(self):
        self.failures = 0

    def that(self, description, condition):
        print("  %s %s" % ("PASS" if condition else "FAIL", description))
        if not condition:
            self.failures += 1


async def scenario():
    smart_bin = build()
    checks = Checks()
    print("runtime: %s %s" % (sys.implementation.name,
                              ".".join(str(part) for part in sys.implementation.version)))
    print("sensor: %s | close detection: %s | power: %s"
          % (smart_bin.config.SENSOR_STRATEGY, smart_bin.config.CLOSE_DETECTOR,
             smart_bin.power_policy.name))

    tasks = smart_bin._start_tasks()
    try:
        print("\n1. the OPEN button runs a full cycle")
        await press_open(smart_bin)
        opened = smart_bin.lid.state in (states.OPENING, states.OPEN)
        driving = smart_bin.hardware.motor_pwm_a.duty > 0
        await async_sleep_ms(900)
        checks.that("the press opened the lid", opened)
        checks.that("the motor was driven", driving)
        checks.that("it returned to idle", smart_bin.lid.state == states.IDLE)
        checks.that("the motor is stopped", motor_state(smart_bin) == "stopped")

        print("\n2. a hand at the sensor does the same")
        set_distance(HAND_DISTANCE_MM)
        await async_sleep_ms(120)
        waved_open = smart_bin.lid.state in (states.OPENING, states.OPEN)
        set_distance(NOTHING_THERE_MM)
        await async_sleep_ms(900)
        checks.that("the wave opened the lid", waved_open)
        checks.that("it returned to idle", smart_bin.lid.state == states.IDLE)

        print("\n3. something permanently in the way does not hold the lid open forever")
        set_distance(HAND_DISTANCE_MM)            # a hand, a bin bag, a wall: it never goes away
        reached_fault = await wait_for_state(smart_bin, states.FAULT, timeout_ms=6000)
        checks.that("the lid closed anyway once MAX_OPEN_MS was reached", reached_fault)
        checks.that("it retried before giving up", smart_bin.lid.failed_close_attempts > 1)
        checks.that("it ended in FAULT rather than fighting", smart_bin.lid.state == states.FAULT)
        checks.that("the motor is stopped in FAULT", motor_state(smart_bin) == "stopped")

        print("\n4. a fault is cleared by a button, not by waving")
        await async_sleep_ms(200)
        checks.that("waving does not clear it", smart_bin.lid.state == states.FAULT)
        set_distance(NOTHING_THERE_MM)
        await press_open(smart_bin)
        await async_sleep_ms(100)
        checks.that("the OPEN button cleared it",
                    smart_bin.lid.state in (states.IDLE, states.OPENING, states.OPEN))

        print("\n5. the bin announced itself along the way")
        frames_sent = len(fake_machine.FakeUART.instances[0].written)
        checks.that("MP3 frames were sent (%d bytes)" % frames_sent, frames_sent > 0)

        print("\nlast transitions:")
        for entry in smart_bin.lid.history[-6:]:
            print("   %s --%s--> %s" % (entry[1], entry[2], entry[3]))

        print("\nRESULT: %d check(s) failed" % checks.failures
              if checks.failures else "\nRESULT: all checks passed")
        return checks.failures
    finally:
        for task in tasks:
            if task is not None:
                task.cancel()
        smart_bin.hardware.enter_safe_state()


log.LEVEL = log.WARN   # the checks are the output; raise to INFO to watch every transition
sys.exit(1 if asyncio.run(scenario()) else 0)
