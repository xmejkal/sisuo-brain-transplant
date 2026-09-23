"""
Sound output.

`Player` is what the feedback layer depends on — something that plays a numbered cue. The
DFR0534 module is one implementation; a silent one is another. If the bin ever grows generated
speech, that is a third implementation registered in its place, and nothing else changes.

Cues are opaque to this module: `play(cue)` takes whatever the sound profile in config holds
(today a track number on the module's flash) and the player decides what it means.
"""

from . import log

VOLUME_MIN = 0
VOLUME_MAX = 30


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


class Dfr0534Player(Player):
    """
    DFRobot DFR0534 over UART, write-only, playing clips stored in the module's own flash.

    Frames are 0xAA, command, length, data..., checksum, where the checksum is the low byte of
    the sum of every preceding byte.

    The module's TXD is deliberately not wired: we never need its replies, and powered from the
    LiPo its idle level would exceed what the ESP32-C6's pins tolerate. The cost is that failures
    are invisible here — which is why the status LED, not the speaker, is the error channel.

    NOTE: the command bytes still need checking against parts/datasheets/DFR0534_mp3.pdf — they
    vary between module firmware revisions. `bringup/04_mp3.py` prints every frame it sends.
    """

    FRAME_START = 0xAA
    CMD_PLAY_TRACK = 0x07
    CMD_STOP = 0x0E
    CMD_SET_VOLUME = 0x13

    def __init__(self, uart, volume=22):
        self._uart = uart
        self._volume = volume

    def initialize(self):
        self.set_volume(self._volume)

    def play(self, cue):
        """`cue` is a track number in the module's flash."""
        track = int(cue)
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
        log.debug("mp3 tx %s", bytes(frame))
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
