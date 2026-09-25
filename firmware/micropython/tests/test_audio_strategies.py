"""
Two players, one vocabulary — and the proof that swapping them cannot change what a profile means.

This is the test that would have caught the defect the vocabulary exists to prevent. A cue used
to be a bare integer, and the integer meant "track 1 in the module's flash" to the DFR0534 and
"entry 1 in the tone table" to the amplifier. The same `SOUND_PROFILES`, the same numbers, two
unrelated sounds, and nothing anywhere could notice — because there was no statement that the
two were supposed to agree, only an assumption that nobody wrote down.

Now there is one: `audio.ALL_CUES`. A profile names what the bin is EXPRESSING; each player
translates that into its own mechanism. These tests check the translation is total in both
directions, which is the only thing that makes the two interchangeable.

The second half is about the boards. The two strategies are not two settings of one bin — they
need different PCBs, and asking for one on the other's board must fail loudly rather than emit
serial data onto an amplifier's shutdown line.
"""

import unittest

import fakes  # noqa: F401 - puts the firmware on sys.path

import config as real_config
from smartbin import audio, states
from smartbin.audio import Dfr0534Player, I2sTonePlayer, SilentPlayer


class EveryPlayerSpeaksTheWholeVocabularyTest(unittest.TestCase):
    """
    A player missing a cue is a bin that goes quiet for one state and nowhere else, which is
    close to undiscoverable by ear: you would have to know the sound was supposed to be there.
    """

    def test_the_amplifier_has_a_tone_for_every_cue(self):
        self.assertEqual(set(I2sTonePlayer.TONES), set(audio.ALL_CUES))

    def test_the_uart_module_has_a_track_for_every_cue(self):
        self.assertEqual(set(Dfr0534Player.TRACKS), set(audio.ALL_CUES))

    def test_neither_invents_a_cue_the_vocabulary_does_not_have(self):
        # The reverse direction. A table entry for a cue nothing can request is dead weight that
        # reads as a supported sound.
        for table in (I2sTonePlayer.TONES, Dfr0534Player.TRACKS):
            with self.subTest(table=table):
                self.assertEqual(set(table) - set(audio.ALL_CUES), set())

    def test_no_two_cues_share_a_track(self):
        # Tones may legitimately repeat — SETTLED sounds the same wherever it is used — but two
        # names on one TRACK means the module plays the wrong clip for one of them.
        tracks = list(Dfr0534Player.TRACKS.values())
        self.assertEqual(len(tracks), len(set(tracks)))


class ProfilesAreWrittenInThatVocabularyTest(unittest.TestCase):
    def test_every_cue_named_in_every_profile_exists(self):
        # Profiles are hand-edited and the MODE button cycles them, so a typo here is a silent
        # state rather than an error.
        for name, profile in real_config.SOUND_PROFILES.items():
            for state, cue in profile.items():
                with self.subTest(profile=name, state=state):
                    self.assertIn(cue, audio.ALL_CUES,
                                  "%s maps %s to %r, which is not a cue" % (name, state, cue))

    def test_every_state_named_in_every_profile_exists(self):
        for name, profile in real_config.SOUND_PROFILES.items():
            for state in profile:
                with self.subTest(profile=name, state=state):
                    self.assertIn(state, states.ALL_STATES)

    def test_a_profile_means_the_same_thing_under_either_player(self):
        """
        The whole point, stated as an assertion.

        Both players can render every cue any profile names, so switching the strategy changes
        HOW the bin sounds and never WHEN. Under the old integer cues this was false and looked
        true.
        """
        for name, profile in real_config.SOUND_PROFILES.items():
            for cue in profile.values():
                with self.subTest(profile=name, cue=cue):
                    self.assertIn(cue, I2sTonePlayer.TONES)
                    self.assertIn(cue, Dfr0534Player.TRACKS)


class ChoosingOneNeedsTheBoardThatCarriesItTest(unittest.TestCase):
    """
    `AUDIO_STRATEGY` is a statement about which PCB is fitted, not a preference. The pin map is
    the other statement, and the two must agree.
    """

    class Settings:
        """The real configuration, with the audio choice overridden."""

        def __init__(self, **overrides):
            for name in dir(real_config):
                if name.isupper():
                    setattr(self, name, getattr(real_config, name))
            for name, value in overrides.items():
                if value is None:
                    if hasattr(self, name):
                        delattr(self, name)
                else:
                    setattr(self, name, value)

    def _player(self, **overrides):
        import fake_machine
        fake_machine.reset()
        fake_machine.FakeI2C.devices[0x29] = fake_machine.FakeVL6180X(distance_mm=200)
        from smartbin.hardware import Hardware
        return Hardware(self.Settings(**overrides)).player

    def test_the_default_configuration_builds_the_amplifier(self):
        self.assertIsInstance(self._player(), I2sTonePlayer)

    def test_asking_for_the_uart_module_on_a_board_without_it_falls_back_to_silence(self):
        # The v4 pin map has no PIN_MP3_TX, because D3 carries the amplifier's shutdown line.
        # Building a UART on it would put serial data on that pin: no error, no sound, and a
        # shutdown input being driven with frames. Silence is the safe answer, loudly logged.
        self.assertIsInstance(self._player(AUDIO_STRATEGY="dfr0534"), SilentPlayer)

    def test_the_uart_module_builds_when_the_board_does_carry_it(self):
        # The v3 configuration: a serial pin exists, so the strategy is satisfiable.
        player = self._player(AUDIO_STRATEGY="dfr0534", PIN_MP3_TX=38,
                              MP3_UART_ID=1, MP3_BAUD=9600)
        self.assertIsInstance(player, Dfr0534Player)

    def test_an_unknown_strategy_is_silence_rather_than_a_crash(self):
        self.assertIsInstance(self._player(AUDIO_STRATEGY="gramophone"), SilentPlayer)

    def test_audio_can_still_be_switched_off_entirely(self):
        self.assertIsInstance(self._player(AUDIO_ENABLED=False), SilentPlayer)


if __name__ == "__main__":
    unittest.main()
