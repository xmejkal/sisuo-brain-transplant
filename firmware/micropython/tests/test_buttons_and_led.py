"""Button debounce and the status LED — small, and easy to get subtly wrong."""

import unittest

from fakes import FakeClock, FakePin

from smartbin import buttons, status_led

PRESSED = 0
RELEASED = 1


def build_button(debounce_ms=40):
    pin = FakePin(level=RELEASED)
    clock = FakeClock()
    return buttons.Button(pin, debounce_ms=debounce_ms, clock=clock), pin, clock


def poll(button, clock, times=4, step_ms=20):
    """
    Poll the way the button task does, and report whether a press was seen.

    Polling matters: the debounce measures from the poll that first *observed* a change, so a
    change is confirmed on a later poll, never the same one.
    """
    saw_press = False
    for _ in range(times):
        clock.advance(step_ms)
        if button.pressed_edge():
            saw_press = True
    return saw_press


class TestButton(unittest.TestCase):
    def test_a_clean_press_reports_exactly_one_edge(self):
        button, pin, clock = build_button()
        pin.level = PRESSED
        self.assertTrue(poll(button, clock))

        self.assertFalse(poll(button, clock))  # still held: not a second press

    def test_bouncing_contacts_do_not_report_a_press(self):
        """Chatter faster than the debounce window must never look like a press."""
        button, pin, clock = build_button(debounce_ms=40)
        for level in (PRESSED, RELEASED, PRESSED, RELEASED, PRESSED, RELEASED):
            pin.level = level
            clock.advance(5)
            self.assertFalse(button.pressed_edge())

    def test_release_then_press_reports_again(self):
        button, pin, clock = build_button()
        pin.level = PRESSED
        self.assertTrue(poll(button, clock))

        pin.level = RELEASED
        self.assertFalse(poll(button, clock))

        pin.level = PRESSED
        self.assertTrue(poll(button, clock))


class TestStatusLed(unittest.TestCase):
    def test_colours_drive_the_expected_pins(self):
        red, green = FakePin(0), FakePin(0)
        led = status_led.StatusLed(red, green)

        led.set(status_led.RED)
        self.assertEqual((red.level, green.level), (1, 0))

        led.set(status_led.GREEN)
        self.assertEqual((red.level, green.level), (0, 1))

        led.set(status_led.AMBER)
        self.assertEqual((red.level, green.level), (1, 1))

        led.set(status_led.OFF)
        self.assertEqual((red.level, green.level), (0, 0))

    def test_toggle_restores_the_previous_colour(self):
        """The fault blinker relies on this: off, then back to red, not to some default."""
        red, green = FakePin(0), FakePin(0)
        led = status_led.StatusLed(red, green)
        led.set(status_led.RED)

        led.toggle()
        self.assertEqual((red.level, green.level), (0, 0))

        led.toggle()
        self.assertEqual((red.level, green.level), (1, 0))


if __name__ == "__main__":
    unittest.main()
