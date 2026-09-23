"""
Proximity sensing strategies — "is a hand there?"

Which sensor the bin ends up with is a mechanical question (does it fit the lid?), not a software
one, so all of them satisfy the same tiny interface and are chosen in config:

    read()     -> distance in mm, or None when this sensor cannot measure distance
    detected() -> bool, the decision, with debounce and hysteresis already applied

Keeping the decision inside the sensor (rather than in the lid) is what lets a distance sensor
and a bare on/off sensor be swapped without the lid noticing.
"""

from . import compat, log


class ProximitySensor:
    """
    Base class holding the debounce that every implementation needs: a detection must survive
    `consecutive` polls in a row, and after a detection the sensor stays quiet for `cooldown_ms`
    so one wave does not trigger three times.
    """

    def __init__(self, consecutive=2, cooldown_ms=1500, clock=None):
        self._consecutive = consecutive
        self._cooldown_ms = cooldown_ms
        self._clock = clock or compat.Clock()
        self._hits = 0
        self._last_detection = None

    def read(self):
        return None

    def arm_for_sleep(self):
        """Prepare to keep watching while the CPU is off. Only the interrupt sensor can."""
        return False

    def acknowledge_wake(self):
        """Called after the chip wakes because of this sensor."""
        return None

    def _sees_hand(self):
        """Implemented by each strategy: the raw, undebounced answer."""
        raise NotImplementedError

    def detected(self):
        if self._last_detection is not None:
            if self._clock.elapsed_ms(self._last_detection) < self._cooldown_ms:
                return False

        if not self._sees_hand():
            self._hits = 0
            return False

        self._hits += 1
        if self._hits < self._consecutive:
            return False

        self._hits = 0
        self._last_detection = self._clock.now_ms()
        return True


class TofSensor(ProximitySensor):
    """
    VL6180X time-of-flight over I2C. Triggers on a hand inside a distance window.

    The window matters: the datasheet guarantees 0-100 mm, and in bright light the guaranteed
    range falls to about 60-70 mm, so the default is deliberately not optimistic. The near limit
    keeps the lid itself, or a dirty window, from reading as a hand.

    I2C is a cable that can be knocked loose, so reads are wrapped: a few failures are reported
    as "no hand", and persistent failure raises `SensorFailure` for the app to turn into a fault.
    """

    def __init__(self, driver, near_mm=30, far_mm=100, max_failures=10, **kwargs):
        super().__init__(**kwargs)
        self._driver = driver
        self._near_mm = near_mm
        self._far_mm = far_mm
        self._max_failures = max_failures
        self._failures = 0

    def read(self):
        try:
            distance = self._driver.range()
        except OSError as exception:
            self._failures += 1
            log.warn("tof read failed (%d/%d): %s", self._failures, self._max_failures, exception)
            if self._failures >= self._max_failures:
                raise SensorFailure("VL6180X unreachable")
            return None
        self._failures = 0
        return distance

    def _sees_hand(self):
        distance = self.read()
        if distance is None:
            return False
        return self._near_mm < distance < self._far_mm


class IrBurstSensor(ProximitySensor):
    """
    The fallback that fits the bin's existing lid holes: an IR LED pulsed at 38 kHz and a
    TSOP-style receiver.

    These receivers have automatic gain control that suppresses a *continuous* carrier, so the
    LED must be sent in short bursts with gaps — hence `burst_us`. The receiver output is active
    low while it hears the carrier, so a reflection off a hand reads as 0.

    It reports no distance: `read()` returns None and sensitivity is set by LED current and
    aiming, in hardware.
    """

    def __init__(self, emitter_pwm, receiver_pin, burst_us=600, carrier_hz=38000, **kwargs):
        super().__init__(**kwargs)
        self._emitter = emitter_pwm
        self._receiver = receiver_pin
        self._burst_us = burst_us
        self._carrier_hz = carrier_hz
        self._emitter.freq(carrier_hz)
        self._emitter.duty_u16(0)

    def _sees_hand(self):
        import time

        self._emitter.duty_u16(32768)  # 50% duty is what these receivers expect
        time.sleep_us(self._burst_us)
        heard = self._receiver.value() == 0
        self._emitter.duty_u16(0)
        return heard


class TofInterruptSensor(TofSensor):
    """
    The same VL6180X, doing the watching itself.

    The sensor ranges continuously on its own clock and asserts its interrupt pin when something
    comes closer than the threshold. While awake we read that pin instead of the I2C bus, which
    is cheaper and gives the same answer; asleep, that pin is what wakes the chip.

    `interrupt_pin` must be D0, D1 or D2 — the only pins on this board that can wake an
    ESP32-C6 — and `power.DeepSleepPolicy` refuses to sleep otherwise.
    """

    def __init__(self, driver, interrupt_pin, period_ms=500, active_high=True, **kwargs):
        super().__init__(driver, **kwargs)
        self._pin = interrupt_pin
        self._period_ms = period_ms
        self._active_high = active_high
        self._asserted = 1 if active_high else 0
        self._configure()

    def _configure(self):
        self._driver.configure_interrupt(self._far_mm, active_high=self._active_high)
        self._driver.start_continuous(self._period_ms)

    def _sees_hand(self):
        if self._pin.value() != self._asserted:
            return False
        self._driver.clear_interrupt()
        return True

    def read(self):
        """The last continuous reading — no new measurement, so this is cheap to poll."""
        try:
            return self._driver.last_range()
        except OSError as exception:
            log.warn("tof read failed: %s", exception)
            return None

    def arm_for_sleep(self):
        """Clear any latched interrupt so we do not wake instantly on the one we just handled."""
        self._driver.clear_interrupt()
        return True

    def acknowledge_wake(self):
        self._driver.clear_interrupt()


class ButtonOnlySensor(ProximitySensor):
    """No proximity sensing at all — the bin opens on the button. Useful during bring-up."""

    def _sees_hand(self):
        return False


class FakeSensor(ProximitySensor):
    """Test double: set `.hand` to choose what it sees."""

    def __init__(self, hand=False, **kwargs):
        super().__init__(**kwargs)
        self.hand = hand

    def _sees_hand(self):
        return self.hand


class SensorFailure(Exception):
    """Raised when a sensor has failed often enough that the bin should fault rather than guess."""
