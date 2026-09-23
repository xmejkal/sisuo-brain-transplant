"""
The tests worth having: the safety cap, and the behaviour the transition table promises.

Run on a Mac, no hardware:
    cd firmware/micropython && python3 -m unittest discover tests -v
"""

import unittest

from fakes import (
    FakeClock,
    FakeConfig,
    FakeMotor,
    RecordingListener,
    StepRunner,
)

from smartbin import events, states
from smartbin.closing import FakeCloseDetector
from smartbin.events import EventBus
from smartbin.lid import Lid


def build_lid(config=None, detector=None):
    clock = FakeClock()
    motor = FakeMotor(clock)
    runner = StepRunner(clock)
    bus = EventBus()
    listener = RecordingListener()
    bus.subscribe(listener)
    lid = Lid(
        motor,
        detector or FakeCloseDetector(),
        config or FakeConfig(),
        bus,
        clock=clock,
        spawn=runner.spawn,
        sleep=runner.sleep,
    )
    return lid, motor, runner, listener


class TestSafetyCap(unittest.TestCase):
    """The one behaviour that protects the hardware. Everything else is convenience."""

    def test_motor_stops_at_the_cap_when_the_detector_never_fires(self):
        config = FakeConfig()
        config.LID_CLOSE_RUN_MS = 100000  # calibrated absurdly long, as a typo would be
        lid, motor, runner, _ = build_lid(config, FakeCloseDetector(is_closed=False))

        lid.fire(states.OPEN_PRESSED)
        runner.run(steps=300)

        self.assertLessEqual(motor.longest_run_ms, config.MOTOR_MAX_RUN_MS + config.MOTION_POLL_MS)
        self.assertFalse(motor.is_running)

    def test_cap_while_opening_is_treated_as_reaching_the_stop(self):
        config = FakeConfig()
        config.LID_OPEN_RUN_MS = 100000
        lid, _, runner, _ = build_lid(config)

        lid.fire(states.OPEN_PRESSED)
        runner.run(steps=300)

        self.assertEqual(lid.state, states.OPEN)


class TestOpenCloseCycle(unittest.TestCase):
    def test_hand_opens_holds_then_closes(self):
        lid, motor, runner, listener = build_lid(detector=FakeCloseDetector(is_closed=False))

        lid.fire(states.HAND_DETECTED)
        self.assertEqual(lid.state, states.OPENING)

        runner.run(steps=120)  # 1200 ms: past the 900 ms open stroke
        self.assertEqual(lid.state, states.OPEN)

        runner.run(steps=500)  # past the 4 s hold and the close stroke
        self.assertEqual(lid.state, states.IDLE)
        self.assertFalse(motor.is_running)

        self.assertIn(events.entered(states.OPENING), listener.events)
        self.assertIn(events.entered(states.CLOSING), listener.events)
        self.assertIn(events.entered(states.IDLE), listener.events)

    def test_close_detector_ends_the_stroke_early(self):
        detector = FakeCloseDetector(is_closed=True)
        lid, _, runner, _ = build_lid(detector=detector)

        lid.fire(states.OPEN_PRESSED)
        runner.run(steps=600)

        self.assertEqual(lid.state, states.IDLE)
        self.assertGreaterEqual(detector.started, 1)

    def test_a_hand_while_open_keeps_the_lid_open(self):
        lid, _, runner, _ = build_lid()
        lid.fire(states.OPEN_PRESSED)
        runner.run(steps=120)
        self.assertEqual(lid.state, states.OPEN)

        for _ in range(10):  # keep waving across what would be the hold timeout
            runner.run(steps=30)
            lid.fire(states.HAND_DETECTED)
            self.assertEqual(lid.state, states.OPEN)


class TestObstruction(unittest.TestCase):
    """The failure the original bin got wrong: it retried forever."""

    def test_obstruction_reopens_and_retries_then_faults(self):
        config = FakeConfig()
        config.MAX_CLOSE_RETRIES = 2
        lid, motor, runner, listener = build_lid(config, FakeCloseDetector(is_closed=False))

        lid.fire(states.OPEN_PRESSED)
        runner.run(steps=120)

        for _ in range(config.MAX_CLOSE_RETRIES + 1):
            lid.fire(states.HOLD_EXPIRED)
            self.assertEqual(lid.state, states.CLOSING)
            lid.fire(states.HAND_DETECTED)  # something in the way
            runner.run(steps=120)

        self.assertEqual(lid.state, states.FAULT)
        self.assertFalse(motor.is_running)
        self.assertIn(events.entered(states.FAULT), listener.events)

    def test_fault_is_latched_until_a_button_press(self):
        config = FakeConfig()
        config.MAX_CLOSE_RETRIES = 0
        lid, _, runner, _ = build_lid(config, FakeCloseDetector(is_closed=False))

        lid.fire(states.OPEN_PRESSED)
        runner.run(steps=120)
        lid.fire(states.HOLD_EXPIRED)
        lid.fire(states.CAP_TRIPPED)
        self.assertEqual(lid.state, states.FAULT)

        lid.fire(states.HAND_DETECTED)  # waving does not clear a fault
        self.assertEqual(lid.state, states.FAULT)

        lid.fire(states.OPEN_PRESSED)
        self.assertEqual(lid.state, states.IDLE)

    def test_retry_counter_resets_after_a_successful_close(self):
        lid, _, runner, _ = build_lid(detector=FakeCloseDetector(is_closed=False))
        lid.fire(states.OPEN_PRESSED)
        runner.run(steps=120)
        lid.fire(states.HOLD_EXPIRED)
        lid.fire(states.HAND_DETECTED)
        self.assertEqual(lid.retries, 1)

        runner.run(steps=120)          # reopens
        lid.fire(states.HOLD_EXPIRED)
        runner.run(steps=200)          # closes, this time uninterrupted
        self.assertEqual(lid.state, states.IDLE)
        self.assertEqual(lid.retries, 0)


if __name__ == "__main__":
    unittest.main()
