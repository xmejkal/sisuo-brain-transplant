"""
Power policies — "what should the bin do while nothing is happening?"

Staying awake and sleeping deeply are not the same program: deep sleep on this chip is a reset,
so "waking" means booting, asking why, and acting on the answer. All of that is confined here,
behind `PowerPolicy`, and `config.POWER_POLICY` picks one. Nothing else in the firmware knows
which is in use — the lid, the state machine and the sensors are identical either way.

Board and port specifics (wake pins, sleep, watchdog) live in board.py.
"""

from . import board, log, states, timing


class PowerPolicy:
    """
    What the application needs from a power policy:

        trigger_for_wake(smart_bin)     the trigger to fire because of how we booted, or None
        await tick_while_idle(bin)      called repeatedly; may sleep the chip and never return
        sleep_now(smart_bin)            sleep immediately, if this policy can

    Policies may read the bin's state, but must not drive the lid themselves.
    """

    name = "policy"
    sleeps = False

    def trigger_for_wake(self, smart_bin):
        return None

    async def tick_while_idle(self, smart_bin):
        raise NotImplementedError

    def sleep_now(self, smart_bin):
        log.warn("power: %s never sleeps", self.name)
        return False


class StayAwakePolicy(PowerPolicy):
    """
    Never sleeps. What you want on USB, on the bench and while calibrating: the REPL stays alive,
    timing is honest, and nothing reboots underneath you.
    """

    name = "always_on"

    async def tick_while_idle(self, smart_bin):
        await timing.async_sleep_ms(smart_bin.config.IDLE_TICK_MS)


class DeepSleepPolicy(PowerPolicy):
    """
    Sleeps the chip once the bin has been idle, waking on the sensor's interrupt or the OPEN
    button.

    The sensor keeps ranging while the chip is off, so idle current becomes the sensor's
    (~170 uA at one reading per second) rather than the ESP32's ~15 uA. That is the real budget:
    months on a 1000 mAh cell rather than days.

    Requirements this policy checks rather than assumes:
      * the sensor must be able to watch while asleep (`SENSOR_STRATEGY = "tof_interrupt"`);
      * every wake pin must be wake-capable — D0/D1/D2 on this board;
      * every wake source must share the polarity in `config.WAKE_ON_HIGH`, because the chip
        applies one level to all of them. A pull-up button (idle high, pressed low) with
        wake-on-high would wake the instant it slept, forever.
    """

    name = "deep_sleep"
    sleeps = True

    def __init__(self, clock=None):
        self._idle_since_ms = None
        self._clock = clock or timing.Clock()

    # ----------------------------------------------------------------- waking
    def trigger_for_wake(self, smart_bin):
        """Turn the reason we booted into a trigger, so a wake acts immediately."""
        if not board.woke_from_sleep():
            log.info("power: cold boot")
            return None

        gpio_numbers = board.wake_gpio_numbers()
        log.info("power: woken by GPIO %s", gpio_numbers or "(port cannot say)")

        if not gpio_numbers:
            return self._trigger_by_reading_pins(smart_bin)

        if smart_bin.config.PIN_BUTTON_OPEN in gpio_numbers:
            return states.OPEN_PRESSED
        if smart_bin.config.PIN_TOF_INTERRUPT in gpio_numbers:
            smart_bin.sensor.acknowledge_wake()
            return states.HAND_DETECTED
        return None

    def _trigger_by_reading_pins(self, smart_bin):
        """
        Fallback for MicroPython builds that report only *that* we woke, not from which pin:
        look at the pins ourselves. The signal is still asserted this early after a wake.
        """
        if smart_bin.hardware.button_open.is_pressed:
            return states.OPEN_PRESSED
        smart_bin.sensor.acknowledge_wake()
        return states.HAND_DETECTED

    # ----------------------------------------------------------------- sleeping
    async def tick_while_idle(self, smart_bin):
        await timing.async_sleep_ms(smart_bin.config.IDLE_TICK_MS)

        if not self._may_sleep(smart_bin):
            self._idle_since_ms = None
            return

        if self._idle_since_ms is None:
            self._idle_since_ms = self._clock.now_ms()
            return

        idle_for_ms = self._clock.elapsed_ms(self._idle_since_ms)
        if idle_for_ms >= self._sleep_after_ms(smart_bin):
            self.sleep_now(smart_bin)

    def _may_sleep(self, smart_bin):
        """
        A faulted bin sleeps too, just later: blinking red until the cell is flat helps nobody,
        and waking on the button is how the fault gets cleared anyway.
        """
        return smart_bin.lid.state in (states.IDLE, states.FAULT)

    def _sleep_after_ms(self, smart_bin):
        if smart_bin.lid.state == states.FAULT:
            return smart_bin.config.SLEEP_AFTER_FAULT_MS
        return smart_bin.config.SLEEP_AFTER_MS

    def sleep_now(self, smart_bin):
        """
        Put everything in its resting state, arm the wake pins, and stop the chip. Does not
        return — the next thing that runs is boot.py.
        """
        config = smart_bin.config
        smart_bin.hardware.enter_safe_state()

        if not smart_bin.sensor.arm_for_sleep():
            log.warn("power: sensor cannot watch while asleep; only the button will wake the bin")

        wake_gpio = self.wake_gpio_numbers(config, smart_bin.sensor)
        log.info("power: sleeping, wake on GPIO %s", wake_gpio)
        board.deep_sleep(wake_gpio, wake_on_high=config.WAKE_ON_HIGH)
        return True

    @staticmethod
    def wake_gpio_numbers(config, sensor):
        """Which pins are armed. Separate from `sleep_now` so a test or the REPL can check it."""
        numbers = [config.PIN_BUTTON_OPEN]
        if sensor.watches_while_asleep:
            numbers.append(config.PIN_TOF_INTERRUPT)
        board.assert_wake_capable(numbers)
        return numbers


POLICIES = {
    StayAwakePolicy.name: StayAwakePolicy,
    DeepSleepPolicy.name: DeepSleepPolicy,
}


def build_policy(config):
    """The strategy choice, from one config line. An unknown name stays awake, loudly."""
    policy_class = POLICIES.get(config.POWER_POLICY)
    if policy_class is None:
        log.warn("unknown power policy %r; staying awake", config.POWER_POLICY)
        return StayAwakePolicy()
    return policy_class()
