"""The debounce that decides when a wave counts as a wave."""

import unittest

from fakes import FakeClock, FakePin

from smartbin import sensors


class StubSensor(sensors.ProximitySensor):
    """Raw detection is whatever the test sets, so only the base class's logic is under test."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.hand_in_front = False

    def _senses_hand(self):
        return self.hand_in_front


def build_sensor(consecutive_hits=2, cooldown_ms=1000):
    clock = FakeClock()
    sensor = StubSensor(consecutive_hits=consecutive_hits, cooldown_ms=cooldown_ms, clock=clock)
    return sensor, clock


class TestDebounce(unittest.TestCase):
    def test_a_single_reading_is_not_enough(self):
        sensor, _ = build_sensor(consecutive_hits=2)
        sensor.hand_in_front = True
        self.assertFalse(sensor.hand_detected())
        self.assertTrue(sensor.hand_detected())

    def test_a_gap_resets_the_run(self):
        """One stray reading between two real ones must not add up to a detection."""
        sensor, _ = build_sensor(consecutive_hits=3)
        sensor.hand_in_front = True
        sensor.hand_detected()
        sensor.hand_in_front = False
        sensor.hand_detected()
        sensor.hand_in_front = True
        self.assertFalse(sensor.hand_detected())
        self.assertFalse(sensor.hand_detected())
        self.assertTrue(sensor.hand_detected())

    def test_cooldown_suppresses_a_second_detection(self):
        """One wave opens the lid once, however long the hand lingers."""
        sensor, clock = build_sensor(consecutive_hits=1, cooldown_ms=1000)
        sensor.hand_in_front = True
        self.assertTrue(sensor.hand_detected())

        clock.advance(500)
        self.assertFalse(sensor.hand_detected())

        clock.advance(600)  # now past the cooldown
        self.assertTrue(sensor.hand_detected())


class TestButtonOnlySensor(unittest.TestCase):
    def test_never_detects_a_hand(self):
        sensor = sensors.ButtonOnlySensor()
        self.assertFalse(sensor.hand_detected())
        self.assertIsNone(sensor.read_distance_mm())

    def test_cannot_watch_while_asleep(self):
        """Only a self-ranging sensor can; the power policy relies on this answer."""
        self.assertFalse(sensors.ButtonOnlySensor().watches_while_asleep)
        self.assertFalse(sensors.ButtonOnlySensor().arm_for_sleep())


class TestInfraredBurstSensor(unittest.TestCase):
    def test_a_reflection_reads_as_a_hand(self):
        """The receiver pulls its output low while it hears the carrier."""
        emitter = _RecordingPwm()
        receiver = FakePin(level=0)
        sensor = sensors.InfraredBurstSensor(emitter, receiver, consecutive_hits=1)
        self.assertTrue(sensor.hand_detected())

    def test_the_emitter_is_left_off_after_a_burst(self):
        emitter = _RecordingPwm()
        sensor = sensors.InfraredBurstSensor(emitter, FakePin(level=1), consecutive_hits=1)
        sensor.hand_detected()
        self.assertEqual(emitter.duty, 0)


class _RecordingPwm:
    def __init__(self):
        self.duty = None
        self.frequency = None

    def freq(self, hertz):
        self.frequency = hertz

    def duty_u16(self, duty):
        self.duty = duty


if __name__ == "__main__":
    unittest.main()
