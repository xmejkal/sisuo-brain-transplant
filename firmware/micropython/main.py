"""
Production entry point — deliberately the whole file.

Any logic here would be logic you cannot reach from the REPL, so there is none.

Hold the MODE button during boot to skip the auto-start: insurance against a board that
reboot-loops into lid motion, and the way back in if a bad calibration makes the bin unusable.
"""

import time

from machine import Pin

import config

_mode_button = Pin(config.PIN_BUTTON_MODE, Pin.IN, Pin.PULL_UP)

# Let the pull-up charge the cable capacitance before trusting the level, and require two
# agreeing reads: a single early read can report a press that never happened.
time.sleep_ms(5)
_held_at_boot = _mode_button.value() == 0 and _mode_button.value() == 0

if _held_at_boot:
    print("MODE held at boot: auto-start skipped.")
    print("Bench use: import smartbin; b = smartbin.build()")
else:
    import smartbin

    smartbin.run()
