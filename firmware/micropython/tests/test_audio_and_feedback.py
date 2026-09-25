"""
What plays and what lights, when.

This file used to also hold the DFR0534's wire format. Both it and the class it tested went when
the audio moved to I2S on 2026-09-25: the board has no UART module any more, so the code was
unreachable and the tests were proving the wire format of a part that is not on the design. The
I2S player has its own file, `test_i2s_audio.py`.
"""

import unittest

import fakes  # noqa: F401 - puts the firmware on sys.path

from smartbin import events, states, status_led
from smartbin.audio import SilentPlayer
from smartbin.feedback import DEFAULT_LED_COLOURS, AudioFeedback, LedFeedback


class TestAudioFeedback(unittest.TestCase):
    PROFILES = {"default": {states.OPENING: 1, states.IDLE: 2}, "silent": {}}

    def test_a_cue_plays_when_its_state_is_entered(self):
        player = SilentPlayer()
        feedback = AudioFeedback(player, self.PROFILES)

        feedback(events.state_entered(states.OPENING))
        self.assertEqual(player.played_cues, [1])

    def test_an_unmapped_state_is_silence_rather_than_an_error(self):
        player = SilentPlayer()
        feedback = AudioFeedback(player, self.PROFILES)

        feedback(events.state_entered(states.CLOSING))
        self.assertEqual(player.played_cues, [])

    def test_the_silent_profile_plays_nothing_at_all(self):
        player = SilentPlayer()
        feedback = AudioFeedback(player, self.PROFILES, active="silent")

        for state in states.ALL_STATES:
            feedback(events.state_entered(state))
        self.assertEqual(player.played_cues, [])

    def test_the_mode_button_cycles_through_the_profiles_and_comes_back(self):
        feedback = AudioFeedback(SilentPlayer(), self.PROFILES)
        names = [feedback.next_profile() for _ in range(3)]

        self.assertEqual(names, ["silent", "default", "silent"])

    def test_a_profile_name_from_a_stale_config_file_does_not_crash_the_button(self):
        feedback = AudioFeedback(SilentPlayer(), self.PROFILES, active="does-not-exist")

        self.assertIn(feedback.active, self.PROFILES)
        self.assertIn(feedback.next_profile(), self.PROFILES)


class TestLedFeedback(unittest.TestCase):
    class FakeLed:
        colour = None

        def set(self, colour):
            self.colour = colour

    def test_each_state_lights_its_colour(self):
        led = self.FakeLed()
        feedback = LedFeedback(led, DEFAULT_LED_COLOURS)

        feedback(events.state_entered(states.FAULT))
        self.assertEqual(led.colour, status_led.RED)

        feedback(events.state_entered(states.OPENING))
        self.assertEqual(led.colour, status_led.GREEN)

    def test_a_bin_at_rest_draws_nothing(self):
        led = self.FakeLed()
        LedFeedback(led, DEFAULT_LED_COLOURS)(events.state_entered(states.IDLE))

        self.assertEqual(led.colour, status_led.OFF)


if __name__ == "__main__":
    unittest.main()
