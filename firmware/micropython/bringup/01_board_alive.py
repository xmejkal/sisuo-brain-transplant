"""
Bring-up step 1 — XIAO alone on USB, nothing wired.
Blinks the on-board user LED and prints chip info. Proves MicroPython + mpremote work.
"""
import time

import machine
from machine import Pin

PIN_USER_LED = 15   # XIAO ESP32-C6 on-board user LED
BLINK_COUNT = 10
BLINK_HALF_PERIOD_MS = 250

print("CPU MHz:", machine.freq() // 1_000_000)
print("Unique ID:", machine.unique_id().hex())

led = Pin(PIN_USER_LED, Pin.OUT)
for _ in range(BLINK_COUNT):
    led.toggle()
    time.sleep_ms(BLINK_HALF_PERIOD_MS)
print("PASS if the user LED blinked", BLINK_COUNT // 2, "times")
