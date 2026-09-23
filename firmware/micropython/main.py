"""
Production entry point — deliberately the whole file.

Any logic here would be logic you cannot reach from the REPL, so there is none. Hold the MODE
button during boot to skip the auto-start: insurance against a board that reboot-loops into lid
motion, and the way back in if a bad calibration makes the bin unusable.
"""

from machine import Pin

import config

_mode_button = Pin(config.PIN_BUTTON_MODE, Pin.IN, Pin.PULL_UP)

if _mode_button.value() == 0:
    print("MODE held at boot: auto-start skipped. Use: import smartbin; b = smartbin.build()")
else:
    import smartbin

    smartbin.run()
