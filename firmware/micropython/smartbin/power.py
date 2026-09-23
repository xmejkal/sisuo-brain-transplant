"""
Power strategies — "what should the bin do while nothing is happening?"

Staying awake and sleeping deeply are not the same program: deep sleep on the ESP32 is a reset,
so "waking" means booting, asking why, and acting on the answer. All of that is confined to this
module, behind one interface:

    prepare(bin)   -> called once at start-up; turns a wake reason into a trigger
    async idle(bin)-> called from the main loop; may sleep the chip, or may do nothing

`config.POWER` picks one. Nothing else in the firmware knows which is in use — the lid, the state
machine and the sensors are identical either way.

Facts this is built on (ESP32-C6, MicroPython, verified 2026-09-23):
  * deep sleep draws ~15 uA on the XIAO, but ~300 uA if the LiPo sags near 3.3 V (the XIAO's
    regulator changes mode);
  * only GPIO0-7 can wake the chip, which on the XIAO means D0, D1 and D2 and nothing else;
  * `esp32.wake_on_ext0` does not exist on the C6, and `Pin.irq(wake=DEEPSLEEP)` silently does
    nothing — `wake_on_ext1` is the call that works;
  * low-level wake has an open MicroPython bug (#17334, "stuck pin"), so wake is configured
    active-HIGH here;
  * waking is a full reset: only `machine.RTC().memory()` survives, and boot costs ~100-300 ms.
"""

from . import compat, log, states


class AlwaysOnPolicy:
    """
    Never sleeps. What you want on USB, on the bench, and while calibrating: the REPL stays
    alive, timing is honest, and nothing reboots underneath you.
    """

    name = "always_on"
    wakes_on_sensor = False

    def prepare(self, bin_):
        return None

    async def idle(self, bin_):
        await compat.async_sleep_ms(bin_.config.IDLE_TICK_MS)


class DeepSleepPolicy:
    """
    Sleeps the chip when the bin has been idle, and is woken by the ToF sensor's interrupt pin or
    the OPEN button.

    The sensor keeps ranging on its own while the chip is off, so the idle current becomes the
    sensor's (~170 uA at one reading per second, ~340 uA at two) rather than the ESP32's ~15 uA.
    That is the real budget; months on a 1000 mAh cell rather than days.

    Waking is a reset, so `prepare()` runs before anything else and converts "which pin woke us"
    into a trigger — which is why a hand at a sleeping bin opens the lid immediately instead of
    waiting for the first poll.
    """

    name = "deep_sleep"
    wakes_on_sensor = True

    def __init__(self):
        self._idle_since = None
        self._clock = compat.Clock()

    # ----------------------------------------------------------------- waking
    def prepare(self, bin_):
        """Turn the reason we booted into a trigger, if it was a wake rather than a power-on."""
        import machine

        reason = machine.wake_reason()
        if reason not in (getattr(machine, "EXT1_WAKE", -1), getattr(machine, "PIN_WAKE", -2)):
            log.info("power: cold boot")
            return None

        pins = self._wake_pins()
        log.info("power: woken by %s", pins)

        if bin_.config.PIN_BUTTON_OPEN in pins:
            return states.OPEN_PRESSED
        if bin_.config.PIN_TOF_INTERRUPT in pins:
            bin_.sensor.acknowledge_wake()
            return states.HAND_DETECTED
        return None

    @staticmethod
    def _wake_pins():
        """
        Which GPIO woke us. `machine.wake_pins()` arrived in MicroPython 1.29; on older builds we
        only know that *something* did, and the caller falls back to treating it as a hand.
        """
        import machine

        if hasattr(machine, "wake_pins"):
            return tuple(machine.wake_pins())
        log.warn("power: MicroPython too old for wake_pins(); assuming the sensor")
        return ()

    # ----------------------------------------------------------------- sleeping
    async def idle(self, bin_):
        await compat.async_sleep_ms(bin_.config.IDLE_TICK_MS)

        if bin_.lid.state != states.IDLE:
            self._idle_since = None
            return

        if self._idle_since is None:
            self._idle_since = self._clock.now_ms()
            return

        if self._clock.elapsed_ms(self._idle_since) < bin_.config.SLEEP_AFTER_MS:
            return

        self.sleep_now(bin_)

    def sleep_now(self, bin_):
        """
        Arm the wake pins and stop the chip. Does not return: the next thing that runs is boot.py.

        Everything is put in its resting state first — a motor left driving through a deep sleep
        would run until the battery died.
        """
        import esp32
        import machine
        from machine import Pin

        bin_.hw.all_off()
        bin_.sensor.arm_for_sleep()

        wake_pins = [Pin(number, Pin.IN) for number in self._wake_pin_numbers(bin_.config)]
        log.info("power: sleeping, wake on %s", [pin for pin in wake_pins])

        # Active-high on purpose: low-level wake is the case with the open "stuck pin" bug.
        esp32.wake_on_ext1(pins=wake_pins, level=esp32.WAKEUP_ANY_HIGH)
        machine.deepsleep()

    @staticmethod
    def _wake_pin_numbers(config):
        """
        Only GPIO0-7 can wake this chip; MicroPython refuses anything else with ValueError.
        Keeping the check here makes a bad pin map fail loudly at the right moment.
        """
        numbers = [config.PIN_BUTTON_OPEN]
        if config.SENSOR == "tof_interrupt":
            numbers.append(config.PIN_TOF_INTERRUPT)

        for number in numbers:
            if not 0 <= number <= 7:
                raise ValueError(
                    "GPIO%d cannot wake an ESP32-C6 (only GPIO0-7 can)" % number
                )
        return numbers


POLICIES = {
    AlwaysOnPolicy.name: AlwaysOnPolicy,
    DeepSleepPolicy.name: DeepSleepPolicy,
}


def build(config):
    """The strategy choice, from one config line."""
    policy = POLICIES.get(config.POWER)
    if policy is None:
        log.warn("unknown power policy %s; staying awake", config.POWER)
        return AlwaysOnPolicy()
    return policy()
