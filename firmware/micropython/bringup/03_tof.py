"""
Bring-up step 3 — VL6180X time-of-flight sensor.

Wiring: SDA <- D4 (GPIO22), SCL <- D5 (GPIO23), VIN <- 3V3, GND. Breakouts with a regulator and
level shifter (Adafruit 3316, Pololu 2489) are safe on 3.3 V; a bare board may not be — check
before powering it.

Prints a live distance so you can wave a hand at it and pick the trigger window for config.py.
"""

import time

from machine import I2C, Pin

import sys

sys.path.insert(0, "/")

from smartbin.vl6180x import VL6180X, RangeError  # noqa: E402

PIN_I2C_SDA = 22  # D4
PIN_I2C_SCL = 23  # D5
SAMPLE_MS = 200
SECONDS = 30

i2c = I2C(0, sda=Pin(PIN_I2C_SDA), scl=Pin(PIN_I2C_SCL), freq=400000)
found = i2c.scan()
print("I2C devices:", [hex(address) for address in found])
if 0x29 not in found:
    raise SystemExit("FAIL: no VL6180X at 0x29 — check SDA/SCL, 3V3 and GND")

sensor = VL6180X(i2c)
print("Sensor found. Wave a hand at it. Note the mm at a comfortable wave distance.")

deadline = time.ticks_add(time.ticks_ms(), SECONDS * 1000)
while time.ticks_diff(deadline, time.ticks_ms()) > 0:
    try:
        print("range:", sensor.range(), "mm")
    except RangeError as error:
        print("range error", error.status, "(out of range or too little signal)")
    time.sleep_ms(SAMPLE_MS)

print("PASS if the numbers drop as your hand approaches and settle around 200+ / error when empty.")
print("Set TOF_NEAR_MM / TOF_FAR_MM in config.py from what you saw.")
