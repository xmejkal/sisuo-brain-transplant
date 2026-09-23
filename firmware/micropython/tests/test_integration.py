"""
The one test that does not use the fake task runner.

`tests/fakes.py` models asyncio closely, but a model is a model: this runs the real lid against
real `asyncio`, on a real clock, with the timings scaled down so the whole cycle takes a fraction
of a second. It is the test that would have caught a stroke's self-cancellation being fatal.
"""

import asyncio
import unittest

from fakes import FakeCloseDetector, FakeMotor

from smartbin import compat, events, states
from smartbin.events import EventBus
from smartbin.lid import Lid


class FastConfig:
    """The real behaviour at 1/30th of the duration, so the suite stays quick."""

    LID_OPEN_RUN_MS = 30
    LID_CLOSE_RUN_MS = 30
    LID_OPEN_HOLD_MS = 60
    MOTOR_MAX_RUN_MS = 100
    MOTOR_OPEN_SPEED = 220
    MOTOR_CLOSE_SPEED = 200
    MAX_CLOSE_RETRIES = 2
    MOTION_POLL_MS = 5


def build_lid(close_detector=None):
    """A lid wired to real asyncio: the defaults for `spawn` and `sleep`, not the fakes."""
    clock = compat.Clock()
    motor = FakeMotor(clock)
    bus = EventBus()
    seen = []
    bus.subscribe(lambda event, **data: seen.append(event))
    lid = Lid(motor, close_detector or FakeCloseDetector(), FastConfig(), bus, clock=clock)
    return lid, motor, seen


class TestUnderRealAsyncio(unittest.TestCase):
    def test_a_full_cycle_completes(self):
        """Open, hold, close, back to idle — the sequence that self-cancellation used to break."""

        async def scenario():
            lid, motor, seen = build_lid()
            lid.fire(states.OPEN_PRESSED)
            self.assertEqual(lid.state, states.OPENING)

            await asyncio.sleep(0.25)  # comfortably past open + hold + close
            return lid, motor, seen

        lid, motor, seen = asyncio.run(scenario())
        self.assertEqual(lid.state, states.IDLE)
        self.assertFalse(motor.is_running)
        self.assertIn(events.state_entered(states.OPEN), seen)
        self.assertIn(events.state_entered(states.CLOSING), seen)
        self.assertIn(events.state_entered(states.IDLE), seen)

    def test_the_safety_cap_stops_a_stroke_that_would_run_forever(self):
        async def scenario():
            lid, motor, _ = build_lid(FakeCloseDetector(is_shut=False))
            lid._config.LID_CLOSE_RUN_MS = 100000  # as a mis-calibration would look
            lid.fire(states.OPEN_PRESSED)
            await asyncio.sleep(0.4)
            return lid, motor

        lid, motor = asyncio.run(scenario())
        self.assertFalse(motor.is_running)
        self.assertLessEqual(
            motor.longest_run_ms, FastConfig.MOTOR_MAX_RUN_MS + FastConfig.MOTION_POLL_MS * 3
        )

    def test_obstruction_reopens_and_eventually_faults(self):
        async def scenario():
            lid, motor, _ = build_lid(FakeCloseDetector(is_shut=False))
            lid.fire(states.OPEN_PRESSED)
            await asyncio.sleep(0.05)

            for _ in range(FastConfig.MAX_CLOSE_RETRIES + 1):
                lid.fire(states.HOLD_EXPIRED)
                lid.fire(states.HAND_DETECTED)   # something in the way, every time
                await asyncio.sleep(0.06)
            return lid, motor

        lid, motor = asyncio.run(scenario())
        self.assertEqual(lid.state, states.FAULT)
        self.assertFalse(motor.is_running)


if __name__ == "__main__":
    unittest.main()
