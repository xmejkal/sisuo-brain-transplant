"""
Checks on the configuration itself: the invariants a calibration typo would break.

These read the real config.py, so they fail on the Mac before a bad value ever reaches the bin.
"""

import unittest

import fakes  # noqa: F401 - puts the firmware on sys.path

import config
from smartbin import board, feedback, states


class TestSafetyInvariants(unittest.TestCase):
    def test_the_safety_cap_exceeds_both_calibrated_run_times(self):
        """A cap below a run time would stop every stroke early and look like a broken lid."""
        self.assertGreater(config.MOTOR_MAX_RUN_MS, config.LID_OPEN_RUN_MS)
        self.assertGreater(config.MOTOR_MAX_RUN_MS, config.LID_CLOSE_RUN_MS)

    def test_the_distance_window_is_the_right_way_round_and_within_spec(self):
        self.assertLess(config.TOF_NEAR_MM, config.TOF_FAR_MM)
        self.assertLessEqual(
            config.TOF_FAR_MM, 100, "the VL6180X datasheet only guarantees 100 mm"
        )

    def test_speeds_are_within_the_pwm_scale(self):
        for speed in (config.MOTOR_OPEN_SPEED, config.MOTOR_CLOSE_SPEED):
            self.assertTrue(0 <= speed <= 255)


class TestPinMap(unittest.TestCase):
    def test_wake_sources_are_on_wake_capable_pins(self):
        """Only GPIO0-7 can wake this chip; anything else silently never wakes the bin."""
        for pin in (config.PIN_BUTTON_OPEN, config.PIN_TOF_INTERRUPT):
            self.assertTrue(board.supports_wake(pin), "GPIO%d cannot wake the chip" % pin)

    #: Signals that deliberately share a pin with another, because only one of each pair is
    #: ever constructed. The IR fallback reuses the I2C pins; the limit switch reuses the shunt
    #: input. Listed individually so that a NEW collision is still a failure.
    DELIBERATE_ALTERNATES = ("PIN_IR_EMITTER", "PIN_IR_RECEIVER", "PIN_LIMIT_SWITCH")

    def test_no_two_signals_share_a_pin_in_one_configuration(self):
        """
        Pins are deliberately reused *between* configurations, never within one.

        Every PIN_* in config is read, rather than a list written out here. The hand-written
        version named ten constants and went stale the first time the pin map changed — it
        referenced PIN_MP3_TX after the audio moved to I2S, so it errored instead of checking,
        and while it was being repaired it was checking nothing. A test that has to be edited
        whenever the thing it guards changes will be wrong exactly when it matters.
        """
        used = {}
        for name in sorted(dir(config)):
            if not name.startswith("PIN_") or name in self.DELIBERATE_ALTERNATES:
                continue
            pin = getattr(config, name)
            self.assertNotIn(
                pin, used,
                "%s and %s are both GPIO%d, and both are built in the same configuration"
                % (name, used.get(pin), pin))
            used[pin] = name
        self.assertTrue(used, "no PIN_* constants were found, so this checked nothing")


class TestFeedbackCompleteness(unittest.TestCase):
    def test_every_state_has_a_led_colour(self):
        """A state with no colour is a bin that goes dark for reasons nobody can see."""
        for state in states.ALL_STATES:
            self.assertIn(state, feedback.DEFAULT_LED_COLOURS)

    def test_sound_profiles_only_name_real_states(self):
        for name, profile in config.SOUND_PROFILES.items():
            for state in profile:
                self.assertIn(state, states.ALL_STATES, "%s: no such state %r" % (name, state))


class TestCalibrationWhitelist(unittest.TestCase):
    def test_pins_cannot_be_overridden_from_the_calibration_file(self):
        self.assertFalse(config.save({"PIN_MOTOR_IA": 99}))
        self.assertNotEqual(config.PIN_MOTOR_IA, 99)

    def test_calibratable_keys_all_exist(self):
        for key in config.CALIBRATABLE:
            self.assertTrue(hasattr(config, key), "CALIBRATABLE names %s, which does not exist" % key)


if __name__ == "__main__":
    unittest.main()
