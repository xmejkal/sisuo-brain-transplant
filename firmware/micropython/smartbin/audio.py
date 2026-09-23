"""
Sound output.

`AudioFeedback` (in feedback.py) talks to a *player*, not to a specific module, so what makes the
noise can change without touching anything else:

    play(track)   -> start playing a numbered clip
    set_volume(v) -> 0-30
    stop()

Today that is the DFR0534, which plays clips stored in its own flash. If the bin ever grows
generated speech, that means a different player object (one that streams to an I2S amplifier, or
fetches audio first) registered in its place — the lid, the state machine and the sound profiles
stay exactly as they are.
"""

from . import log

FRAME_START = 0xAA
CMD_PLAY_TRACK = 0x07
CMD_STOP = 0x0E
CMD_SET_VOLUME = 0x13


class Dfr0534:
    """
    DFRobot DFR0534 over UART, write-only.

    Frames are 0xAA, command, length, data..., checksum, where the checksum is the low byte of
    the sum of every preceding byte.

    The module's own TXD is deliberately not wired: we never need its replies, and powered from
    the LiPo its idle level would exceed what the ESP32-C6's pins tolerate.

    NOTE: the command bytes still need checking against parts/datasheets/DFR0534_mp3.pdf — they
    vary between module firmware revisions. bringup/06_mp3.py prints the frames it sends.
    """

    def __init__(self, uart, volume=22):
        self._uart = uart
        self._volume = volume

    def begin(self):
        self.set_volume(self._volume)

    def _send(self, command, data=b""):
        frame = bytearray((FRAME_START, command, len(data)))
        frame.extend(data)
        frame.append(sum(frame) & 0xFF)
        log.debug("mp3 tx %s", bytes(frame))
        self._uart.write(frame)

    def play(self, track):
        self._send(CMD_PLAY_TRACK, bytes((track >> 8, track & 0xFF)))

    def set_volume(self, volume):
        self._volume = max(0, min(30, volume))
        self._send(CMD_SET_VOLUME, bytes((self._volume,)))

    def stop(self):
        self._send(CMD_STOP)


class NullPlayer:
    """
    A player that logs instead of playing. Used when audio is disabled, and in tests — the bin
    must work with no speaker attached.
    """

    def __init__(self):
        self.played = []

    def begin(self):
        pass

    def play(self, track):
        self.played.append(track)
        log.debug("null player: track %d", track)

    def set_volume(self, volume):
        pass

    def stop(self):
        pass
