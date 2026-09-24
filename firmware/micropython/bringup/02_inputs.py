"""
Bring-up step 2 — buttons and the status LED.

Wiring is printed at startup from the constants below. Both buttons go to GND with no
external resistors — the internal pull-ups do it. The status LED is common cathode to GND,
each anode through its own 330R.

NOTE: on this board the MODE pin is also the module's OWN on-board button, which carries a
5.1k pull-up and a 100nF cap. It will read 1 and respond to a press with nothing connected,
so this step cannot prove the external MODE button is wired. Press the external one.

Press each button; the LED follows (OPEN = green, MODE = red, both = amber).
"""

import time

from machine import Pin

PIN_BUTTON_OPEN = 13      # D11  [wake-capable]
PIN_BUTTON_MODE = 47      # D14
PIN_LED_RED = 9           # D7
PIN_LED_GREEN = 7         # D5
WATCH_SECONDS = 30
POLL_MS = 20

button_open = Pin(PIN_BUTTON_OPEN, Pin.IN, Pin.PULL_UP)
button_mode = Pin(PIN_BUTTON_MODE, Pin.IN, Pin.PULL_UP)
led_red = Pin(PIN_LED_RED, Pin.OUT, value=0)
led_green = Pin(PIN_LED_GREEN, Pin.OUT, value=0)

print("Idle levels (both should be 1):", button_open.value(), button_mode.value())
print("LED self-test: red, green, amber...")
for red, green in ((1, 0), (0, 1), (1, 1), (0, 0)):
    led_red.value(red)
    led_green.value(green)
    time.sleep_ms(500)

last = (button_open.value(), button_mode.value())
deadline = time.ticks_add(time.ticks_ms(), WATCH_SECONDS * 1000)
while time.ticks_diff(deadline, time.ticks_ms()) > 0:
    now = (button_open.value(), button_mode.value())
    if now != last:
        print("OPEN:", now[0], " MODE:", now[1])
        last = now
    led_green.value(0 if now[0] else 1)
    led_red.value(0 if now[1] else 1)
    time.sleep_ms(POLL_MS)

led_red.value(0)
led_green.value(0)
print("PASS if each button read 0 when pressed and lit its colour.")
