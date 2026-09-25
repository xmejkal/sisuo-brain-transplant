"""
The I2S amplifier's player: what it writes, and — more importantly — when it is silent.

The wiring cannot enforce either of the amplifier's two dangerous rules, so both live in the
player and both are tested here:

  * **SD must end LOW on every path**, including a failed write and a cue cancelled by the next
    one. Held low the MAX98357A draws 0.6 uA; left high with the clock stopped it draws 340 uA,
    five hundred times more, and that is most of this bin's sleeping budget. A leak here would
    never be noticed by ear.
  * **SD must be DRIVEN, never floated.** The module pulls it up, and floating selects a channel
    rather than shutting anything down.

The tone generator is checked for the things that are audible when wrong: length, a fade at both
ends so a cue does not click, and amplitude that tracks volume without ever clipping.
"""

import asyncio
import struct
import unittest

import fakes  # noqa: F401 - puts the firmware on sys.path

from smartbin import audio
from smartbin.audio import (
    OPEN_START, TONE_PEAK, TONE_RATE_HZ, FAULT, I2sTonePlayer, tone_samples)


class RecordingI2s:
    """Enough of `machine.I2S` for `asyncio.StreamWriter` to wrap it."""

    def __init__(self, fail_with=None):
        self.written = bytearray()
        self._fail_with = fail_with

    def write(self, data):
        if self._fail_with is not None:
            raise self._fail_with
        self.written.extend(data)
        return len(data)

    def ioctl(self, request, argument):
        return 0


class RecordingPin:
    def __init__(self):
        self.level = None
        self.history = []

    def value(self, level=None):
        if level is None:
            return self.level
        self.level = level
        self.history.append(level)


def played(player, cue):
    """Run one cue to completion, the way the event loop would."""
    async def scenario():
        player.play(cue)
        await player._task
    asyncio.run(scenario())


class TheToneItselfTest(unittest.TestCase):
    def test_a_cue_is_as_long_as_it_says(self):
        samples = tone_samples(880, 100, amplitude=0.5)
        self.assertEqual(len(samples) // 2, TONE_RATE_HZ * 100 // 1000)

    def test_it_starts_and_ends_at_silence(self):
        # Without the ramp a cue begins at full amplitude, which is a step into the speaker and
        # is audible as a click. This is the cheapest thing that separates a device that feels
        # finished from one that does not.
        samples = tone_samples(880, 100, amplitude=1.0)
        first = struct.unpack_from("<h", samples, 0)[0]
        last = struct.unpack_from("<h", samples, len(samples) - 2)[0]
        self.assertEqual(first, 0)
        self.assertEqual(last, 0)

    def test_it_reaches_close_to_the_requested_amplitude_in_the_middle(self):
        samples = tone_samples(1000, 200, amplitude=1.0)
        middle = [abs(value) for (value,) in struct.iter_unpack("<h", samples)]
        self.assertGreater(max(middle), 30000)

    def test_nothing_ever_clips(self):
        # int16 wraps rather than saturating, so a sample one over full scale becomes a large
        # NEGATIVE number - an inverted spike, not a slightly loud one.
        samples = tone_samples(440, 150, amplitude=1.0)
        for (value,) in struct.iter_unpack("<h", samples):
            self.assertLessEqual(abs(value), 32767)

    def test_a_cue_shorter_than_two_ramps_still_works(self):
        # The fades overlap; the tone simply never reaches full amplitude. It must not produce a
        # negative length, an empty buffer, or a division by zero.
        samples = tone_samples(880, 1, amplitude=1.0)
        self.assertGreater(len(samples), 0)


class WhatThePlayerWritesTest(unittest.TestCase):
    def setUp(self):
        self.bus = RecordingI2s()
        self.shutdown = RecordingPin()
        self.player = I2sTonePlayer(self.bus, self.shutdown, volume=30)

    def test_a_known_cue_reaches_the_amplifier(self):
        played(self.player, OPEN_START)
        self.assertTrue(self.bus.written)

    def test_an_unknown_cue_writes_nothing_and_starts_no_task(self):
        # Profiles are edited by hand and the MODE button cycles them; a cue with no tone must
        # be silence, not an exception inside an event-bus callback.
        self.player.play("no-such-cue")
        self.assertIsNone(self.player._task)
        self.assertEqual(self.bus.written, bytearray())

    def test_each_cue_in_the_table_renders(self):
        for cue in I2sTonePlayer.TONES:
            with self.subTest(cue=cue):
                bus = RecordingI2s()
                player = I2sTonePlayer(bus, RecordingPin(), volume=30)
                played(player, cue)
                self.assertTrue(bus.written, "cue %s produced no samples" % cue)

    def test_the_samples_are_cached_so_a_repeated_cue_is_not_regenerated(self):
        played(self.player, OPEN_START)
        first = self.player._cache[OPEN_START]
        played(self.player, OPEN_START)
        self.assertIs(self.player._cache[OPEN_START], first)


class TheAmplifierIsOffUnlessItIsPlayingTest(unittest.TestCase):
    """
    Each of these is a path by which SD could be left high. Every one of them is a 340 uA leak
    that makes no sound, so none would be found by listening.
    """

    def setUp(self):
        self.shutdown = RecordingPin()

    def test_initialize_leaves_it_shut_down(self):
        I2sTonePlayer(RecordingI2s(), self.shutdown).initialize()
        self.assertEqual(self.shutdown.value(), 0)

    def test_it_is_raised_to_play_and_dropped_afterwards(self):
        player = I2sTonePlayer(RecordingI2s(), self.shutdown, volume=30)
        played(player, OPEN_START)
        self.assertEqual(self.shutdown.history, [1, 0])

    def test_it_is_dropped_even_when_the_write_fails(self):
        # A bin that cannot chirp still empties itself - but it must not also sit there leaking.
        player = I2sTonePlayer(RecordingI2s(fail_with=OSError("no peripheral")),
                               self.shutdown, volume=30)
        played(player, OPEN_START)
        self.assertEqual(self.shutdown.value(), 0)

    def test_it_is_dropped_when_a_cue_is_cancelled_by_the_next_one(self):
        async def scenario():
            player = I2sTonePlayer(RecordingI2s(), self.shutdown, volume=30)
            player.play(FAULT)      # the longest cue in the table
            first = player._task
            player.play(OPEN_START)  # interrupts it
            await asyncio.gather(first, player._task, return_exceptions=True)
            return player
        asyncio.run(scenario())
        self.assertEqual(self.shutdown.value(), 0)

    def test_stop_silences_it(self):
        player = I2sTonePlayer(RecordingI2s(), self.shutdown, volume=30)
        played(player, OPEN_START)
        self.shutdown.value(1)      # pretend something left it on
        player.stop()
        self.assertEqual(self.shutdown.value(), 0)


class VolumeTest(unittest.TestCase):
    def test_louder_volume_produces_larger_samples(self):
        quiet = I2sTonePlayer(RecordingI2s(), RecordingPin(), volume=5)
        loud = I2sTonePlayer(RecordingI2s(), RecordingPin(), volume=30)
        played(quiet, OPEN_START)
        played(loud, OPEN_START)
        peak = lambda player: max(abs(v) for (v,) in struct.iter_unpack("<h", player._cache[OPEN_START]))
        self.assertLess(peak(quiet), peak(loud))

    def test_changing_volume_discards_the_cached_samples(self):
        # Amplitude is baked into the buffer, so a cache that survived a volume change would
        # keep playing the old level until the bin was restarted.
        player = I2sTonePlayer(RecordingI2s(), RecordingPin(), volume=10)
        played(player, OPEN_START)
        self.assertIn(OPEN_START, player._cache)
        player.set_volume(25)
        self.assertEqual(player._cache, {})

    def test_setting_the_same_volume_keeps_the_cache(self):
        player = I2sTonePlayer(RecordingI2s(), RecordingPin(), volume=10)
        played(player, OPEN_START)
        player.set_volume(10)
        self.assertIn(OPEN_START, player._cache)

    def test_volume_is_clamped_to_the_range_the_contract_promises(self):
        player = I2sTonePlayer(RecordingI2s(), RecordingPin(), volume=10)
        player.set_volume(99)
        self.assertEqual(player._volume, 30)
        player.set_volume(-5)
        self.assertEqual(player._volume, 0)

    def test_full_volume_still_leaves_headroom(self):
        # TONE_PEAK exists because a bridged class-D output driving a 30 mm speaker sounds worse
        # clipped than it does quieter.
        samples = tone_samples(1000, 200, amplitude=TONE_PEAK)
        self.assertLess(max(abs(v) for (v,) in struct.iter_unpack("<h", samples)), 32767)


if __name__ == "__main__":
    unittest.main()
