"""Buttons and the status LED — the parts of the bin a person touches and looks at."""

from . import compat

RED = "red"
GREEN = "green"
AMBER = "amber"
OFF = "off"


class Button:
    """
    A button wired pin-to-ground, read through the internal pull-up (so pressed == 0).

    Debounced without blocking: `pressed_edge()` is polled from a task and reports a press once,
    when the level has been stable for `debounce_ms`. Nothing here sleeps, so one task can poll
    several buttons and the lid keeps moving meanwhile.
    """

    def __init__(self, pin, debounce_ms=40, clock=None):
        self._pin = pin
        self._debounce_ms = debounce_ms
        self._clock = clock or compat.Clock()
        self._stable_level = pin.value()
        self._candidate_level = self._stable_level
        self._changed_at = self._clock.now_ms()

    @property
    def is_pressed(self):
        return self._stable_level == 0

    def pressed_edge(self):
        """True exactly once per press, on the debounced transition to pressed."""
        level = self._pin.value()
        if level != self._candidate_level:
            self._candidate_level = level
            self._changed_at = self._clock.now_ms()
            return False

        if level == self._stable_level:
            return False

        if self._clock.elapsed_ms(self._changed_at) < self._debounce_ms:
            return False

        self._stable_level = level
        return level == 0


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
