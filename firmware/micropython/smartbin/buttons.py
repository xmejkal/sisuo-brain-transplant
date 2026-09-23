"""
The bin's two buttons.

A device, not a decision: this knows how to read a button reliably, and nothing about what a
press means. What OPEN and MODE do is decided by the state machine and the application.

Which level means "pressed" is the board's business, not this file's — a button to ground reads
0, one to 3V3 reads 1 — so it is passed in. It matters beyond reading the button: deep sleep can
only wake on one polarity, so a button wired the wrong way for it can never wake the bin.
"""

from . import timing


class Button:
    """
    A button wired pin-to-ground, read through the internal pull-up (so pressed == 0).

    Debounced without blocking: `pressed_edge()` is polled from a task and reports a press once,
    when the level has been stable for `debounce_ms`. Nothing here sleeps, so one task can poll
    several buttons and the lid keeps moving meanwhile.
    """

    def __init__(self, pin, debounce_ms=40, clock=None, pressed_level=0):
        self._pin = pin
        self._debounce_ms = debounce_ms
        #: The level this button reads when pressed. 0 for the usual wiring (to ground with a
        #: pull-up); 1 for a button wired to 3V3 with a pull-down, which is what deep sleep
        #: wants if it is to wake on a rising edge.
        self.pressed_level = pressed_level
        self._clock = clock or timing.Clock()
        self._stable_level = pin.value()
        self._candidate_level = self._stable_level
        self._changed_at = self._clock.now_ms()

    @property
    def is_pressed(self):
        return self._stable_level == self.pressed_level

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
        return level == self.pressed_level
