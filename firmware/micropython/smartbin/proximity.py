"""
Proximity sensing — "is a hand there?"

Which sensor the bin ends up with is a mechanical question (does it fit the lid?) rather than a
software one, so they all satisfy `ProximitySensor` and are chosen by `config.SENSOR_STRATEGY`.

Keeping the *decision* inside the sensor, rather than in the lid, is what lets a distance sensor
and a bare on/off sensor be swapped without the lid noticing.
"""

from . import timing, log
from .vl6180x import RangeError

# Two different kinds of "no answer", and conflating them faults a working bin.
#
#   RangeError  the sensor answered and said it could not measure. An empty field of view does
#               this every time, so it is the *normal* reading for a bin nobody is using.
#   OSError     the bus did not answer at all: a loose cable, a dead sensor.
#
# Only the second is evidence of a broken sensor. Counting the first toward failure faulted the
# bin after ten polls of an empty room — about six hundred milliseconds.
NO_MEASUREMENT = RangeError
BUS_FAILURE = OSError


class SensorFailure(Exception):
    """Raised when a sensor has failed often enough that the bin should fault rather than guess."""


class ProximitySensor:
    """
    What the lid needs from a hand sensor:

        hand_detected()     the decision: True once per wave, debounced and rate-limited
        read_distance_mm()  distance in mm, or None if this sensor cannot measure one
                            (may raise SensorFailure when the hardware has stopped answering)
        arm_for_sleep()     prepare to keep watching with the CPU off; False if it cannot
        acknowledge_wake()  called after the chip wakes because of this sensor

    This base class holds the debounce every implementation needs: a detection must survive
    `consecutive_hits` polls in a row, and afterwards the sensor stays quiet for `cooldown_ms` so
    one wave does not open the lid three times.
    """

    watches_while_asleep = False

    def __init__(self, consecutive_hits=2, cooldown_ms=1500, clock=None):
        self._consecutive_hits = consecutive_hits
        self._cooldown_ms = cooldown_ms
        self._clock = clock or timing.Clock()
        self._hits = 0
        self._last_detection_at = None

    def read_distance_mm(self):
        """None means "this sensor has no notion of distance", not "nothing is there"."""
        return None

    def arm_for_sleep(self):
        return False

    def acknowledge_wake(self):
        """Most sensors need nothing; ones with a latching interrupt must clear it."""

    def hand_detected(self):
        if self._within_cooldown():
            return False

        if not self._senses_hand():
            self._hits = 0
            return False

        self._hits += 1
        if self._hits < self._consecutive_hits:
            return False

        self._hits = 0
        self._last_detection_at = self._clock.now_ms()
        return True

    def _within_cooldown(self):
        if self._last_detection_at is None:
            return False
        return self._clock.elapsed_ms(self._last_detection_at) < self._cooldown_ms

    def _senses_hand(self):
        """The raw, undebounced answer. Each implementation provides this one method."""
        raise NotImplementedError


class TimeOfFlightSensor(ProximitySensor):
    """
    VL6180X time-of-flight over I2C, polled: the lid asks it for a distance and decides.

    The distance window matters. The datasheet guarantees 0-100 mm, and in bright light the
    guaranteed range falls to about 60-70 mm, so the default is deliberately not optimistic. The
    near limit keeps the lid itself, or a dirty window, from reading as a hand.

    A measurement error is routine — an empty field of view reports one every time — so it means
    "no hand" and nothing more. A bus failure is different: I2C is a cable that can be knocked
    loose, and when it stops answering entirely `SensorFailure` tells the app to fault rather
    than silently stop noticing hands.
    """

    def __init__(self, driver, near_mm=30, far_mm=100, max_failures=10, **kwargs):
        super().__init__(**kwargs)
        self._driver = driver
        self._near_mm = near_mm
        self._far_mm = far_mm
        self._max_failures = max_failures
        self._failures = 0

    def read_distance_mm(self):
        try:
            distance_mm = self._driver.range()
        except NO_MEASUREMENT as exception:
            # The sensor is alive and saying "nothing in range". That is not a fault; it is what
            # an empty room looks like.
            log.debug("tof: no measurement (%s)", exception)
            self._failures = 0
            return None
        except BUS_FAILURE as exception:
            return self._note_bus_failure(exception)
        self._failures = 0
        return distance_mm

    def _note_bus_failure(self, exception):
        """
        The bus did not answer. That is only alarming if it keeps happening — I2C is a cable, and
        one bad transaction is not a dead sensor.
        """
        self._failures += 1
        log.warn("tof: bus failure (%d/%d): %s", self._failures, self._max_failures, exception)
        if self._failures >= self._max_failures:
            raise SensorFailure("VL6180X unreachable after %d attempts" % self._failures)
        return None

    def _senses_hand(self):
        distance_mm = self.read_distance_mm()
        if distance_mm is None:
            return False
        return self._near_mm < distance_mm < self._far_mm


class SelfRangingTimeOfFlightSensor(TimeOfFlightSensor):
    """
    The same VL6180X, doing the watching itself.

    It ranges continuously on its own clock and asserts its interrupt pin when something comes
    within `far_mm`. While the bin is awake we read that pin instead of the I2C bus; while it is
    asleep, that pin is what wakes the chip — which is the whole point, and why this is the only
    sensor that works with `POWER_POLICY = "deep_sleep"`.

    The distance is still checked after the pin fires, because the sensor's threshold has no near
    limit: without that check the lid's own window (closer than `near_mm`) would latch the
    interrupt permanently.

    `interrupt_pin` must be wake-capable — D0, D1 or D2 on this board.
    """

    watches_while_asleep = True

    def __init__(self, driver, interrupt_pin, period_ms=500, interrupt_active_high=True, **kwargs):
        super().__init__(driver, **kwargs)
        self._pin = interrupt_pin
        self._period_ms = period_ms
        self._asserted_level = 1 if interrupt_active_high else 0
        driver.configure_interrupt(self._far_mm, active_high=interrupt_active_high)
        driver.start_continuous(period_ms)

    def _senses_hand(self):
        if self._pin.value() != self._asserted_level:
            return False

        # The interrupt latches, so it must be cleared whether or not we believe it.
        self._driver.clear_interrupt()
        distance_mm = self.read_last_distance_mm()
        if distance_mm is None:
            return False
        return self._near_mm < distance_mm < self._far_mm

    def read_last_distance_mm(self):
        """The most recent continuous reading — no new measurement, so it is cheap to poll."""
        try:
            return self._driver.last_range()
        except BUS_FAILURE as exception:
            # `_note_bus_failure`, not `_note_failure`: the latter never existed. Because this is
            # the interrupt strategy's only error branch, the typo turned the FIRST bus hiccup
            # into an AttributeError, which `SmartBin.poll_sensor`'s blanket handler turned into
            # an immediate FAULT — so `TOF_MAX_FAILURES` was dead on the shipped strategy and the
            # "one bad transaction is not a dead sensor" tolerance did not apply to it at all.
            return self._note_bus_failure(exception)

    def read_distance_mm(self):
        return self.read_last_distance_mm()

    def arm_for_sleep(self):
        """Clear the latched interrupt, so the chip does not wake instantly on the one we saw."""
        self._driver.clear_interrupt()
        return True

    def acknowledge_wake(self):
        self._driver.clear_interrupt()


class InfraredBurstSensor(ProximitySensor):
    """
    The fallback that fits the bin's existing lid holes: an IR LED pulsed at 38 kHz and a
    TSOP-style receiver.

    These receivers have automatic gain control that suppresses a *continuous* carrier, so the
    LED is sent in short bursts with gaps — hence `burst_us`. The receiver's output is low while
    it hears the carrier, so a reflection off a hand reads as 0.

    It reports no distance: sensitivity is set by LED current and aiming, in hardware.
    """

    CARRIER_DUTY = 32768  # 50% of DUTY_MAX, which is what these receivers expect

    def __init__(self, emitter_pwm, receiver_pin, burst_us=600, carrier_hz=38000, **kwargs):
        super().__init__(**kwargs)
        self._emitter = emitter_pwm
        self._receiver = receiver_pin
        self._burst_us = burst_us
        self._emitter.freq(carrier_hz)
        self._emitter.duty_u16(0)

    def _senses_hand(self):
        self._emitter.duty_u16(self.CARRIER_DUTY)
        timing.sleep_us(self._burst_us)
        heard_reflection = self._receiver.value() == 0
        self._emitter.duty_u16(0)
        return heard_reflection


class ButtonOnlySensor(ProximitySensor):
    """
    No proximity sensing at all: the bin opens on the button.

    Not a stub — it is the honest configuration for a bin with no sensor fitted, and what the
    firmware falls back to when a sensor cannot be brought up.
    """

    def _senses_hand(self):
        return False
