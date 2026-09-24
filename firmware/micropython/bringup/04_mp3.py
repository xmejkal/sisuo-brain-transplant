"""
Bring-up step 4 — DFR0534 MP3 over UART: XIAO D9 (GPIO20, TX) -> module RXD,
The module's TXD stays UNWIRED: we never need its replies, and powered from the LiPo its idle
level would exceed what the ESP32-C6's pins tolerate. Speaker on the module; flash needs tracks
1 and 2. Plays track 1, then track 2, printing every frame it sends.
If nothing plays, verify the command bytes against a real DFR0534 datasheet from DFRobot's
wiki. The repo does not have one: what was filed as the datasheet is a product photo.
"""
import time

from machine import UART

PIN_MP3_TX = 20   # D9
MP3_BAUD = 9600
MP3_VOLUME = 18   # 0-30, a bit quieter for the bench
MP3_FRAME_START = 0xAA
MP3_CMD_SET_VOLUME = 0x13
MP3_CMD_PLAY_TRACK = 0x07
TRACK_PLAY_WAIT_MS = 3000

uart = UART(1, baudrate=MP3_BAUD, tx=PIN_MP3_TX, rx=-1)


def send_command(command, data=b""):
    """Frame: 0xAA, CMD, LEN, DATA..., SUM (low byte of the sum of all preceding bytes)."""
    frame = bytearray((MP3_FRAME_START, command, len(data)))
    frame.extend(data)
    frame.append(sum(frame) & 0xFF)
    print("TX:", frame.hex(" "))
    uart.write(frame)


time.sleep_ms(200)
send_command(MP3_CMD_SET_VOLUME, bytes((MP3_VOLUME,)))
for track in (1, 2):
    send_command(MP3_CMD_PLAY_TRACK, bytes((track >> 8, track & 0xFF)))
    time.sleep_ms(TRACK_PLAY_WAIT_MS)
print("PASS if you heard track 1 then track 2")
