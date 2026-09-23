"""
The bicolour status LED.

One device with two pins sharing a cathode, so "amber" is simply both lit. Which colour means
what is not decided here — see feedback.py, where it is a table.
"""

RED = "red"
GREEN = "green"
AMBER = "amber"
OFF = "off"


class StatusLed:
    """
    The bicolour LED, as two pins sharing a cathode. Both on reads as amber, which is why the
    colours are named rather than exposed as raw pins.
    """

    def __init__(self, red_pin, green_pin):
        self._red = red_pin
        self._green = green_pin
        self.colour = OFF
        self.set(OFF)

    def set(self, colour):
        self.colour = colour
        self._red.value(1 if colour in (RED, AMBER) else 0)
        self._green.value(1 if colour in (GREEN, AMBER) else 0)

    def toggle(self):
        """Used by the fault blink; keeps the blinking logic in the caller's task."""
        if self.colour == OFF:
            self.set(self._last_on or RED)
        else:
            self._last_on = self.colour
            self.set(OFF)

    _last_on = RED
