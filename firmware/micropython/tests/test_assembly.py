"""
The wiring: does a config string produce the strategy it names?

These run on a PC against fake devices, which is only possible because `hardware.py` owns the
devices and `assembly.py` owns nothing but the choices. If someone later constructs a peripheral
inside a strategy, these tests stop compiling — which is the point.
"""

import unittest

from fakes import FakePin

from smartbin import assembly, close_detection, power, proximity


class FakeRangefinder:
    """Stands in for the VL6180X: a device, so it is fake hardware rather than a fake decision."""

    def __init__(self, distance_mm=50):
        self.distance_mm = distance_mm
        self.continuous_period_ms = None
        self.interrupts_cleared = 0

    def range(self):
        return self.distance_mm

    def last_range(self):
        return self.distance_mm

    def configure_interrupt(self, threshold_mm, active_high=True):
        self.threshold_mm = threshold_mm
        self.interrupt_active_high = active_high

    def start_continuous(self, period_ms):
        self.continuous_period_ms = period_ms

    def clear_interrupt(self):
        self.interrupts_cleared += 1


class FakeHardware:
    """Only the attributes the factory reads — the layering made this small."""

    def __init__(self):
        self.rangefinder = FakeRangefinder()
        self.rangefinder_interrupt = FakePin(level=0)
        self.ir_emitter = _RecordingPwm()
        self.ir_receiver = FakePin(level=1)
        self.current_sense = _FakeAdc()
        self.limit_switch = FakePin(level=1)
        self.led = None
        self.player = None


class FakeConfig:
    """A whole configuration, so the factory can be exercised without the real config module."""

    SENSOR_STRATEGY = "tof"
    CLOSE_DETECTOR = "timed"
    POWER_POLICY = "always_on"
    SENSOR_CONSECUTIVE_HITS = 2
    SENSOR_COOLDOWN_MS = 1500
    TOF_NEAR_MM = 30
    TOF_FAR_MM = 100
    TOF_MAX_FAILURES = 10
    TOF_INTERRUPT_PERIOD_MS = 500
    WAKE_ON_HIGH = True
    IR_BURST_US = 600
    IR_CARRIER_HZ = 38000
    LID_CLOSE_RUN_MS = 950
    STALL_COUNTS = 12000
    STALL_BLANKING_MS = 200
    STALL_SAMPLES = 8
    STALL_CONSECUTIVE_HITS = 3


def build_sensor(strategy):
    config = FakeConfig()
    config.SENSOR_STRATEGY = strategy
    return assembly.build_sensor(config, FakeHardware())


def build_close_detector(choice):
    config = FakeConfig()
    config.CLOSE_DETECTOR = choice
    return assembly.build_close_detector(config, FakeHardware())


class TestSensorChoice(unittest.TestCase):
    def test_each_name_builds_its_strategy(self):
        self.assertIsInstance(build_sensor("tof"), proximity.TimeOfFlightSensor)
        self.assertIsInstance(
            build_sensor("tof_interrupt"), proximity.SelfRangingTimeOfFlightSensor
        )
        self.assertIsInstance(build_sensor("ir"), proximity.InfraredBurstSensor)
        self.assertIsInstance(build_sensor("none"), proximity.ButtonOnlySensor)

    def test_a_typo_falls_back_to_buttons_rather_than_crashing(self):
        """A misspelled strategy must leave a usable bin, not a dead one."""
        self.assertIsInstance(build_sensor("toff"), proximity.ButtonOnlySensor)

    def test_only_the_self_ranging_sensor_can_watch_while_asleep(self):
        """The deep-sleep policy asks this question before it dares sleep."""
        self.assertTrue(build_sensor("tof_interrupt").watches_while_asleep)
        self.assertFalse(build_sensor("tof").watches_while_asleep)
        self.assertFalse(build_sensor("ir").watches_while_asleep)


class TestCloseDetectorChoice(unittest.TestCase):
    def test_each_name_builds_its_detector(self):
        self.assertIsInstance(build_close_detector("timed"), close_detection.TimedCloseDetector)
        self.assertIsInstance(build_close_detector("limit"), close_detection.LimitSwitchCloseDetector)
        self.assertIsInstance(build_close_detector("stall"), close_detection.MotorStallCloseDetector)

    def test_a_typo_falls_back_to_timed(self):
        self.assertIsInstance(build_close_detector("limitt"), close_detection.TimedCloseDetector)


class TestPowerPolicyChoice(unittest.TestCase):
    def test_each_name_builds_its_policy(self):
        config = FakeConfig()
        self.assertIsInstance(assembly.build_power_policy(config), power.StayAwakePolicy)
        config.POWER_POLICY = "deep_sleep"
        self.assertIsInstance(assembly.build_power_policy(config), power.DeepSleepPolicy)

    def test_a_typo_stays_awake(self):
        """Falling back to sleeping could strand a bin; falling back to awake cannot."""
        config = FakeConfig()
        config.POWER_POLICY = "deep_sleeep"
        self.assertIsInstance(assembly.build_power_policy(config), power.StayAwakePolicy)


class _RecordingPwm:
    def freq(self, hertz):
        self.frequency = hertz

    def duty_u16(self, duty):
        self.duty = duty


class _FakeAdc:
    def read_u16(self):
        return 0


if __name__ == "__main__":
    unittest.main()
