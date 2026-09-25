"""
Sound output.

`Player` is what the feedback layer depends on — something that plays a numbered cue. The
DFR0534 module is one implementation; a silent one is another. If the bin ever grows generated
speech, that is a third implementation registered in its place, and nothing else changes.

Cues are opaque to this module: `play(cue)` takes whatever the sound profile in config holds
(a small integer) and the player decides what it means. `I2sTonePlayer` reads it as an entry in its own
tone table; the DFR0534 player this replaced read it as a track number in that module's flash.
That is the whole reason the contract is worded this way, and it is what let the audio move from
a UART MP3 module to an I2S amplifier without touching the feedback layer, the sound profiles,
or the MODE button that cycles them.

Which player is built is `config.AUDIO_STRATEGY`, and the choice is really a choice of BOARD:
`i2s` needs the v4 design, `dfr0534` needs `board-v3-dfr0534.tsx`. They are different versions
of the bin, not two settings of one — which is why the strategy names the hardware it requires
and `assembly` refuses a combination that cannot work.
"""

import math
import struct

import asyncio

from . import log

VOLUME_MIN = 0
VOLUME_MAX = 30

#: Every sound the bin can make, named for WHAT IT EXPRESSES rather than how it is produced.
#:
#: This vocabulary is the interface between the sound design and the hardware, and it exists
#: because a cue used to be a bare integer. That integer meant "track 1 in the module's flash"
#: to a DFR0534 and "entry 1 in the tone table" to the amplifier — the same profile, the same
#: number, two unrelated sounds, and nothing anywhere could notice. The systems behaved
#: differently while claiming to share a configuration.
#:
#: A name cannot drift that way. `config.SOUND_PROFILES` maps a state to one of these; a Player
#: maps the same name to whatever it can actually do. Adding a player means writing a
#: translation table, not reinterpreting somebody else's numbering — and a player that is
#: missing a cue is a gap a test can see.
OPEN_START = "open-start"          # the lid has begun to move
OPEN_START_BRIGHT = "open-start-bright"
OPEN_REACHED = "open-reached"      # fully open
CLOSE_START = "close-start"
SETTLED = "settled"                # back to idle, lid shut: a full stop
BLOCKED = "blocked"                # something is in the way
FAULT = "fault"                    # gave up; needs a person

ALL_CUES = (OPEN_START, OPEN_START_BRIGHT, OPEN_REACHED, CLOSE_START, SETTLED, BLOCKED, FAULT)


class Player:
    """
    What the feedback layer needs to make a noise:

        initialize()       once, before first use (the module needs its volume set)
        play(cue)          start playing; cues come from config.SOUND_PROFILES
        set_volume(level)  0-30
        stop()
    """

    def initialize(self):
        """Players needing no set-up may do nothing."""

    def play(self, cue):
        raise NotImplementedError

    def set_volume(self, level):
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError


#: Sample rate for generated tones. 16 kHz is far above anything a bin chirp needs and keeps the
#: buffers small: a 120 ms cue is 1920 samples, under 4 KB.
TONE_RATE_HZ = 16000

#: How long the amplitude ramps at each end of a cue. A tone that starts and stops at full
#: amplitude puts a step into the speaker, which is audible as a click and is exactly the kind
#: of detail that makes a device feel cheap. 4 ms is inaudible as a fade and removes the step.
TONE_RAMP_MS = 4

#: Peak amplitude at VOLUME_MAX, as a fraction of full scale. Deliberately short of 1.0: the
#: MAX98357A is a bridged output into a small speaker, and clipping a square-ish waveform into
#: a 30 mm driver sounds worse than the same cue quieter.
TONE_PEAK = 0.6


def tone_samples(frequency_hz, duration_ms, amplitude, rate=TONE_RATE_HZ):
    """
    One cue, as little-endian signed 16-bit mono samples.

    A sine rather than a square: the amplifier reconstructs what it is given, and a square wave
    into a small driver is all harmonics. `amplitude` is 0.0-1.0 of full scale.
    """
    count = max(1, rate * duration_ms // 1000)
    ramp = max(1, rate * TONE_RAMP_MS // 1000)
    peak = int(32767 * amplitude)
    step = 2 * math.pi * frequency_hz / rate

    buffer = bytearray(count * 2)
    for index in range(count):
        # Linear fade at both ends. `min` of the two distances handles a cue shorter than two
        # ramps, where the fades overlap and the tone simply never reaches full amplitude.
        edge = min(index, count - 1 - index, ramp)
        value = int(peak * (edge / ramp) * math.sin(step * index))
        struct.pack_into("<h", buffer, index * 2, value)
    return buffer


class I2sTonePlayer(Player):
    """
    Tones the ESP32 synthesises itself, into a MAX98357A over I2S.

    A cue arrives as a name from ALL_CUES — what the bin is expressing — and TONES below is this
    player's answer to each. Nothing outside this class knows a frequency, and nothing inside it
    knows which state is being entered.

    TWO RULES FROM THE AMPLIFIER'S DATASHEET, BOTH LIVING HERE BECAUSE NO WIRING CAN ENFORCE THEM

    * **Never stop LRCLK while BCLK runs.** Maxim say twice that it produces a large DC output
      voltage, and DC into an 8 ohm voice coil is a dead speaker. `machine.I2S` has no way to
      stop one clock and not the other, so this holds as long as nothing here reaches past the
      driver — which is why the I2S object is never deinitialised mid-cue.
    * **SD must be DRIVEN, never floated.** The module pulls it up, and floating selects a
      channel rather than shutting down. Held low the amplifier draws 0.6 uA; merely stopping
      the clock leaves it in standby at 340 uA, five hundred times more, and that difference is
      most of this bin's sleeping current budget.

    So SD is low except while a cue is actually being rendered.
    """

    #: This player's translation of the vocabulary: cue -> (frequency in Hz, duration in ms).
    #: A module holding recorded clips would translate the same names to track numbers instead.
    TONES = {
        OPEN_START: (880, 120),         # bright and short
        OPEN_START_BRIGHT: (988, 100),  # the chatty profile's livelier version
        OPEN_REACHED: (784, 80),
        CLOSE_START: (587, 80),
        SETTLED: (660, 90),             # lower than the rest: a full stop
        BLOCKED: (440, 200),            # long and low enough to read as "stop"
        FAULT: (330, 400),              # longest and lowest; it should sound wrong
    }

    def __init__(self, i2s, shutdown_pin, volume=22):
        self._i2s = i2s
        self._shutdown = shutdown_pin
        self._volume = volume
        self._task = None
        self._cache = {}

    def initialize(self):
        """Nothing to configure on the amplifier; make sure it is off until asked."""
        self._silence()

    def play(self, cue):
        tone = self.TONES.get(cue)
        if tone is None:
            log.debug("i2s player: no tone for cue %s", cue)
            return
        # A new cue replaces one still playing. Cancelling another task is safe; a task
        # cancelling ITSELF is not, and never happens here because `play` is called from the
        # event bus, not from inside `_render`.
        if self._task is not None and not self._task.done():
            self._task.cancel()
        self._task = asyncio.create_task(self._render(cue, *tone))

    def set_volume(self, level):
        level = max(VOLUME_MIN, min(VOLUME_MAX, level))
        if level != self._volume:
            self._volume = level
            self._cache.clear()   # amplitude is baked into the samples

    def stop(self):
        if self._task is not None and not self._task.done():
            self._task.cancel()
        self._silence()

    def _silence(self):
        self._shutdown.value(0)

    def _samples_for(self, cue, frequency_hz, duration_ms):
        if cue not in self._cache:
            amplitude = TONE_PEAK * self._volume / VOLUME_MAX
            self._cache[cue] = tone_samples(frequency_hz, duration_ms, amplitude)
        return self._cache[cue]

    async def _write(self, samples):
        """
        Hand the samples to the driver without blocking the event loop.

        MicroPython's I2S object IS an asyncio stream, so `StreamWriter` drives it directly and
        the write yields while the peripheral drains. CPython's `StreamWriter` is a transport
        wrapper and cannot be constructed around an arbitrary object, so under CPython — which
        is where the unit tests run — this falls back to a plain write.

        That fallback is one call, not a second implementation, and the difference it hides is
        the DRIVER rather than anything in this class. The real path is exercised where it
        exists: `sim/run_on_micropython.py` runs this code on a real MicroPython runtime.
        """
        try:
            writer = asyncio.StreamWriter(self._i2s)
        except (TypeError, AttributeError):
            self._i2s.write(samples)
            return
        writer.write(samples)
        await writer.drain()

    async def _render(self, cue, frequency_hz, duration_ms):
        samples = self._samples_for(cue, frequency_hz, duration_ms)
        self._shutdown.value(1)
        try:
            await self._write(samples)
        except asyncio.CancelledError:
            raise
        except Exception as exception:  # noqa: BLE001
            # A bin that cannot chirp still empties itself. This is the same reasoning that
            # makes a missing module fall back to silence rather than stop the firmware.
            log.error("i2s write failed (%s); cue %s dropped", exception, cue)
        finally:
            # 0.6 uA, not the 340 uA of a clock-stopped standby. Reached on every path out,
            # including cancellation by the next cue.
            self._silence()


class Dfr0534Player(Player):
    """
    DFRobot DFR0534 over UART, write-only, playing clips stored in the module's own flash.

    **This needs the v3 board.** The current design has no UART module and no 6-way header — D3
    carries the amplifier's shutdown line instead — so selecting this on a v4 board gets you
    frames sent into a pin nothing is listening on. `board-v3-dfr0534.tsx` is the design that
    fits it, kept for exactly this reason: the module in the drawer has never been identified.

    Frames are 0xAA, command, length, data..., checksum, where the checksum is the low byte of
    the sum of every preceding byte.

    The module's TXD is deliberately not wired: we never need its replies, and powered from the
    LiPo its idle level would exceed what the ESP32's pins tolerate. The cost is that failures
    are invisible here — which is why the status LED, not the speaker, is the error channel.

    NOTE: the command bytes still need checking against a real DFR0534 datasheet, which this
    repo does not have (what was filed as one is a product photo) — they vary between module
    firmware revisions.
    """

    FRAME_START = 0xAA
    CMD_PLAY_TRACK = 0x07
    CMD_STOP = 0x0E
    CMD_SET_VOLUME = 0x13

    #: This player's translation of the vocabulary: cue -> track number in the module's flash.
    #:
    #: The point of the whole arrangement is visible here. `I2sTonePlayer.TONES` maps the same
    #: names to frequencies. Neither table knows the other exists, and a profile written for one
    #: means precisely the same thing under the other — which was NOT true while a cue was a
    #: bare integer, because "1" was track 1 to this player and a 880 Hz chirp to that one.
    TRACKS = {
        OPEN_START: 1,
        OPEN_START_BRIGHT: 4,
        OPEN_REACHED: 5,
        CLOSE_START: 6,
        SETTLED: 2,
        BLOCKED: 3,
        FAULT: 8,
    }

    def __init__(self, uart, volume=22):
        self._uart = uart
        self._volume = volume

    def initialize(self):
        self.set_volume(self._volume)

    def play(self, cue):
        track = self.TRACKS.get(cue)
        if track is None:
            log.debug("dfr0534: no track for cue %s", cue)
            return
        self._send(self.CMD_PLAY_TRACK, bytes((track >> 8, track & 0xFF)))

    def set_volume(self, level):
        self._volume = max(VOLUME_MIN, min(VOLUME_MAX, level))
        self._send(self.CMD_SET_VOLUME, bytes((self._volume,)))

    def stop(self):
        self._send(self.CMD_STOP)

    def _send(self, command, data=b""):
        frame = bytearray((self.FRAME_START, command, len(data)))
        frame.extend(data)
        frame.append(sum(frame) & 0xFF)
        log.debug("dfr0534 tx %s", bytes(frame))
        self._uart.write(frame)


class SilentPlayer(Player):
    """
    Logs instead of playing. Used when audio is switched off and in tests — the bin has to work
    with no speaker attached.
    """

    def __init__(self):
        self.played_cues = []

    def play(self, cue):
        self.played_cues.append(cue)
        log.debug("silent player: cue %s", cue)

    def set_volume(self, level):
        pass

    def stop(self):
        pass
