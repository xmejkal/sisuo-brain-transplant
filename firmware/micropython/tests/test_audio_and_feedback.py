"""
The parts that talk to a person: the MP3 module's wire format, and what plays or lights when.

Neither had any coverage. The MP3 link is write-only — nothing ever reads back from it — so a
wrong byte is silent forever, on the bench as well as here.
"""

import unittest

import fakes  # noqa: F401 - puts the firmware on sys.path

from smartbin import events, states, status_led
from smartbin.audio import Dfr0534Player, SilentPlayer
from smartbin.feedback import DEFAULT_LED_COLOURS, AudioFeedback, LedFeedback


class RecordingUart:
    def __init__(self):
        self.written = bytearray()

    def write(self, data):
        self.written.extend(data)
        return len(data)


class TestDfr0534Frames(unittest.TestCase):
    """
    Frame format: 0xAA, command, length, data..., checksum, where the checksum is the low byte
    of the sum of everything before it.

    NOTE: these assert what the firmware sends, which is the format from the v1 Arduino sketch.
    They do not prove it is what the module expects — that needs the datasheet and a speaker,
    and is on the bring-up list (bringup/04_mp3.py prints every frame).
    """

    def test_play_track_one(self):
        uart = RecordingUart()
        Dfr0534Player(uart).play(1)

        self.assertEqual(bytes(uart.written), bytes([0xAA, 0x07, 0x02, 0x00, 0x01, 0xB4]))

    def test_the_checksum_is_the_low_byte_of_the_sum(self):
        uart = RecordingUart()
        Dfr0534Player(uart).play(255)

        frame = bytes(uart.written)
        self.assertEqual(frame[-1], sum(frame[:-1]) & 0xFF)

    def test_volume_is_clamped_to_what_the_module_accepts(self):
        uart = RecordingUart()
        player = Dfr0534Player(uart)

        player.set_volume(99)
        self.assertEqual(uart.written[3], 30)   # the module's maximum

        uart.written.clear()
        player.set_volume(-5)
        self.assertEqual(uart.written[3], 0)

    def test_initialize_sets_the_volume_before_anything_plays(self):
        uart = RecordingUart()
        Dfr0534Player(uart, volume=22).initialize()

        self.assertEqual(uart.written[1], 0x13)  # set volume
        self.assertEqual(uart.written[3], 22)


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
