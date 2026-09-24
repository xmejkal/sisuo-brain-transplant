"""
The bench script, checked before anyone is at the bench.

`bringup/06_all_together.py` is the last gate before the bin goes back in its shell: it runs the
real firmware and asks a person to wave, press OPEN and press MODE. The worst time to discover
that script calls a method that no longer exists is while standing over a half-wired bin with a
multimeter in one hand.

So it is run here against the fake chip, with a stand-in for the person: a task that watches
which phase the script is asking for and supplies exactly that stimulus — a hand for the wave
phase, the OPEN button for the open phase, MODE for the mode phase, and nothing else. Supplying
only the stimulus the phase asked for is what makes this worth running: if the script's "wave"
phase were secretly satisfied by a button press, this would fail.

What it proves: the script's API calls are real, its phases are reachable, and its verdict is 0.
What it cannot prove: any of the electrical facts. That is what the bench is for.
"""

import asyncio
import os
import unittest

import fakes  # noqa: F401 - puts the firmware on sys.path
import fake_machine

fake_machine.install()   # must precede any import that reaches the hardware

import config                                      # noqa: E402
from smartbin.timing import async_sleep_ms         # noqa: E402

BRINGUP_SCRIPT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bringup", "06_all_together.py")

HAND_NEAR_MM = 60
NOTHING_THERE_MM = 200
OPERATOR_POLL_MS = 5
# Comfortably longer than BUTTON_DEBOUNCE_MS below: the button reports a press only once the
# level has been *stable* past the debounce window, so a press exactly that long is a coin toss.
PRESS_MS = 120

# The script is written for a person at a bench: seconds of LED self-test, a quarter-second nudge
# each way, fifteen seconds to react. None of that is worth waiting for here, and none of it is
# what this test is about.
# The bench script's own pace, shrunk so the test is quick. PHASE_SECONDS is a DEADLINE, not a
# wait: a phase ends the moment the expected events arrive, so a generous value costs nothing on
# a normal run and only buys headroom on a slow one. It was 2, and this test failed inside a
# pre-commit hook while tsci and bun were competing for the same cores — a flaky gate is worse
# than a slow one, because it teaches everyone to ignore a red build.
BENCH_PACE = {"PHASE_SECONDS": 8, "MOTOR_NUDGE_MS": 5, "LED_STEP_MS": 5, "SETTLE_MS": 20}
FAST_LID = {
    "LID_OPEN_RUN_MS": 30, "LID_CLOSE_RUN_MS": 30, "LID_OPEN_HOLD_MS": 40,
    "MAX_OPEN_MS": 400, "MOTOR_MAX_RUN_MS": 200,
    "SENSOR_POLL_MS": 5, "BUTTON_POLL_MS": 5, "SENSOR_CONSECUTIVE_HITS": 1,
    "SENSOR_COOLDOWN_MS": 0, "WATCHDOG_MS": 0, "REPL_ENABLED": False,
    "BUTTON_DEBOUNCE_MS": 20,
}


def load_bringup_script():
    """
    Import the script by path: its name starts with a digit, so it is not importable by name.

    Importing it is safe because its entry point is guarded — importing defines the functions
    and runs nothing.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("bringup_06", BRINGUP_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BenchOperator:
    """
    The person the script is talking to.

    It supplies one stimulus per phase and nothing else, then takes it away again, so each phase
    is proved by the input it actually asked for.
    """

    def __init__(self, script, sensor):
        self.script = script
        self.sensor = sensor
        self.phases_served = []

    async def attend(self):
        while True:
            phase = self.script.CURRENT_PHASE
            if phase is not None and phase not in self.phases_served:
                self.phases_served.append(phase)
                await self.serve(phase)
            await async_sleep_ms(OPERATOR_POLL_MS)

    async def serve(self, phase):
        if phase == "wave":
            self.sensor.distance_mm = HAND_NEAR_MM
            await async_sleep_ms(PRESS_MS)
            self.sensor.distance_mm = NOTHING_THERE_MM
        elif phase == "open":
            await self.press(config.PIN_BUTTON_OPEN)
        elif phase == "mode":
            await self.press(config.PIN_BUTTON_MODE)

    async def press(self, gpio):
        """
        Press the pin the *firmware* built, not one of our own.

        The script builds its own hardware, so a pin object made here would be a different object
        that nothing reads — which is exactly how this test failed the first time it ran.
        """
        button = fake_machine.FakePin.by_number[gpio]
        button.value(0)
        await async_sleep_ms(PRESS_MS)
        button.value(1)


class BringUpScriptTest(unittest.TestCase):
    def setUp(self):
        fake_machine.reset()
        self.sensor = fake_machine.FakeVL6180X(distance_mm=NOTHING_THERE_MM)
        fake_machine.FakeI2C.devices[0x29] = self.sensor

        self.script = load_bringup_script()
        self.restore = {}
        for name, value in BENCH_PACE.items():
            self.restore[(self.script, name)] = getattr(self.script, name)
            setattr(self.script, name, value)
        for name, value in FAST_LID.items():
            self.restore[(config, name)] = getattr(config, name)
            setattr(config, name, value)

    def tearDown(self):
        for (module, name), value in self.restore.items():
            setattr(module, name, value)

    def test_every_phase_passes_when_the_bench_does_its_part(self):
        async def scenario():
            operator = BenchOperator(self.script, self.sensor)
            attending = asyncio.ensure_future(operator.attend())
            try:
                return await self.script.main(), operator
            finally:
                attending.cancel()

        verdict, operator = asyncio.new_event_loop().run_until_complete(scenario())

        self.assertEqual(verdict, 0, "the bring-up script reported a failure on fake hardware")
        self.assertEqual(operator.phases_served, ["wave", "open", "mode"],
                         "the script did not ask for the three ways in, in order")


if __name__ == "__main__":
    unittest.main()
