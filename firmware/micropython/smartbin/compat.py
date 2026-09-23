"""
Timing shims so the logic modules run both on MicroPython and under CPython on a Mac.

MicroPython's `time.ticks_ms()` returns an opaque, wrapping counter that must only be compared
with `ticks_diff()`. CPython has neither, so it gets equivalents built on `time.monotonic()`.
Everything in the firmware imports ticks from here, never from `time` directly.
"""

import time

try:  # MicroPython
    ticks_ms = time.ticks_ms
    ticks_diff = time.ticks_diff
    ticks_add = time.ticks_add
    sleep_ms = time.sleep_ms
    sleep_us = time.sleep_us
    MICROPYTHON = True
except AttributeError:  # CPython
    MICROPYTHON = False

    def ticks_ms():
        return int(time.monotonic() * 1000)

    def ticks_diff(later, earlier):
        return later - earlier

    def ticks_add(ticks, delta):
        return ticks + delta

    def sleep_ms(milliseconds):
        time.sleep(milliseconds / 1000)

    def sleep_us(microseconds):
        time.sleep(microseconds / 1_000_000)


class Clock:
    """
    Injectable time source. The real one reads ticks; `FakeClock` in the tests advances by hand,
    so the state machine's timing can be tested without waiting for real seconds to pass.
    """

    def now_ms(self):
        return ticks_ms()

    def elapsed_ms(self, since):
        return ticks_diff(self.now_ms(), since)


try:
    import asyncio
except ImportError:  # pragma: no cover - older MicroPython builds
    import uasyncio as asyncio

if hasattr(asyncio, "sleep_ms"):  # MicroPython
    async_sleep_ms = asyncio.sleep_ms
else:  # CPython takes seconds

    def async_sleep_ms(milliseconds):
        return asyncio.sleep(milliseconds / 1000)
