"""
The difference between "nothing is there" and "the sensor is gone".

Conflating them is not theoretical: the firmware used to count a routine measurement error
toward its failure budget, so an empty room faulted the bin in about six hundred milliseconds.
No test noticed, because both fakes always reported a good reading.
"""

import unittest

import fakes  # noqa: F401 - puts the firmware on sys.path
import fake_machine

fake_machine.install()

import config                                     # noqa: E402
from smartbin import assembly, proximity, states  # noqa: E402


class Settings:
    def __init__(self):
        for name in dir(config):
            if name.isupper():
                setattr(self, name, getattr(config, name))
        # Pin the configuration this file is about, rather than inheriting whatever config.py
        # currently says. These tests describe the rangefinder build; switching the shipped
        # default to the IR sensor should not make them fail — it should make them irrelevant.
        self.SENSOR_STRATEGY = "tof"
        self.CLOSE_DETECTOR = "timed"
        self.POWER_POLICY = "always_on"
        self.SENSOR_CONSECUTIVE_HITS = 1
        self.SENSOR_COOLDOWN_MS = 0
        self.WATCHDOG_MS = 0

    def save(self, values):
        return True


def build(distance_mm=200, status=0):
    fake_machine.reset()
    sensor = fake_machine.FakeVL6180X(distance_mm=distance_mm, status=status)
    fake_machine.FakeI2C.devices[0x29] = sensor
    return assembly.build(Settings()), sensor


class TestAnEmptyRoom(unittest.TestCase):
    RANGE_STATUS_NO_CONVERGENCE = 7  # what the sensor reports with nothing in front of it

    def test_a_measurement_error_is_not_a_hand(self):
        smart_bin, sensor = build()
        sensor.status = self.RANGE_STATUS_NO_CONVERGENCE

        self.assertIsNone(smart_bin.sensor.read_distance_mm())
        self.assertFalse(smart_bin.sensor.hand_detected())

    def test_an_empty_room_never_faults_the_bin(self):
        """The bug: ten of these in a row used to raise SensorFailure and latch a fault."""
        smart_bin, sensor = build()
        sensor.status = self.RANGE_STATUS_NO_CONVERGENCE

        for _ in range(config.TOF_MAX_FAILURES * 3):
            self.assertFalse(smart_bin.sensor.hand_detected())

        self.assertEqual(smart_bin.lid.state, states.IDLE)


class TestADeadSensor(unittest.TestCase):
    def test_a_silent_bus_eventually_faults_the_bin(self):
        """A cable that comes out must be noticed, or the bin quietly stops seeing hands."""
        smart_bin, sensor = build()
        sensor.unplugged = True

        with self.assertRaises(proximity.SensorFailure):
            for _ in range(config.TOF_MAX_FAILURES + 1):
                smart_bin.sensor.hand_detected()

    def test_one_bad_transaction_is_forgiven(self):
        """I2C is a cable; a single glitch is not a dead sensor."""
        smart_bin, sensor = build(distance_mm=60)

        sensor.unplugged = True
        self.assertIsNone(smart_bin.sensor.read_distance_mm())

        sensor.unplugged = False
        self.assertEqual(smart_bin.sensor.read_distance_mm(), 60)

        # ...and the failure count went back to zero, so the next glitch starts afresh.
        sensor.unplugged = True
        for _ in range(config.TOF_MAX_FAILURES - 1):
            self.assertIsNone(smart_bin.sensor.read_distance_mm())


class TestRecovery(unittest.TestCase):
    def test_pressing_open_after_a_fault_restarts_sensing(self):
        smart_bin, sensor = build()
        smart_bin.lid.fire(states.SENSOR_FAILED)
        self.assertEqual(smart_bin.lid.state, states.FAULT)

        smart_bin.lid.fire(states.OPEN_PRESSED)
        self.assertEqual(smart_bin.lid.state, states.IDLE)


if __name__ == "__main__":
    unittest.main()
