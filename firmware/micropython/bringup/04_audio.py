"""
Bring-up step 4 — the I2S amplifier: DFR0954 (MAX98357A) on the three pins named below.

Wiring, module pad -> board pin:
    BCLK -> SCK, LRC -> MO, DIN -> MI, SD -> D3, VCC -> 3V3, GND -> GND.
    Speaker across SPK+ and SPK-, which are the RIGHTMOST pad of each row — directly across
    from each other, NOT an adjacent pair. Getting that wrong is the classic way to hear
    nothing at all.

Plays a rising three-note arpeggio, then shuts the amplifier down. You should hear three clean
tones with no click at either end of each.

IF YOU HEAR NOTHING: check SD first. It must be driven HIGH to play — the module pulls it up,
but a pin left as an input floats and the module reads that as a channel selection rather than
"on". This script drives it, so a silent amplifier with SD measured high is a wiring or speaker
fault, not a configuration one.

IF YOU HEAR A LOUD CLICK AND THEN NOTHING: stop and check the speaker. The one thing that can
destroy it is a DC offset, which Maxim say happens if LRCLK stops while BCLK is still running.
This script never does that — it stops both together — but a half-finished edit of it could.
"""
import math
import struct
import time

from machine import I2S, Pin

PIN_I2S_BCLK = 17         # SCK
PIN_I2S_LRC = 15          # MO
PIN_I2S_DIN = 16          # MI
PIN_AUDIO_SD = 38         # D3

RATE_HZ = 16000
NOTES_HZ = (523, 659, 784)    # C, E, G — a major triad, so a wrong one is obvious
NOTE_MS = 250
AMPLITUDE = 0.4               # short of full scale: clipping into a small driver sounds worse
RAMP_MS = 4                   # fade at each end, or every note starts with a click

shutdown = Pin(PIN_AUDIO_SD, Pin.OUT, value=0)
audio = I2S(
    0,
    sck=Pin(PIN_I2S_BCLK), ws=Pin(PIN_I2S_LRC), sd=Pin(PIN_I2S_DIN),
    mode=I2S.TX, bits=16, format=I2S.MONO, rate=RATE_HZ, ibuf=4096,
)


def tone(frequency_hz, duration_ms):
    """Signed 16-bit mono samples, faded in and out."""
    count = RATE_HZ * duration_ms // 1000
    ramp = max(1, RATE_HZ * RAMP_MS // 1000)
    peak = int(32767 * AMPLITUDE)
    step = 2 * math.pi * frequency_hz / RATE_HZ
    buffer = bytearray(count * 2)
    for index in range(count):
        edge = min(index, count - 1 - index, ramp)
        struct.pack_into("<h", buffer, index * 2,
                         int(peak * (edge / ramp) * math.sin(step * index)))
    return buffer


print("driving SD high")
shutdown.value(1)
for frequency in NOTES_HZ:
    print("  %d Hz" % frequency)
    audio.write(tone(frequency, NOTE_MS))
    time.sleep_ms(60)

shutdown.value(0)
audio.deinit()
print("SD low: the amplifier is now at 0.6 uA, not the 340 uA of a stopped clock")
print("PASS if you heard three rising tones, each clean at both ends")
