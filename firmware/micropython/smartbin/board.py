"""
What this chip can do, and how to ask it.

The *facts* — which pins exist, which can wake it, which have an ADC — come from
`boards/<id>.json` via the generated `board_spec.py`. This module is the behaviour built on
them: sleeping, waking, the watchdog. Together they are the only board-specific code in the
firmware, which is what makes changing board a bounded job (see boards/README.md).

`machine` is imported lazily inside the functions so this module can be imported on a PC.
"""

from . import log
from .board_spec import ADC_GPIO, CHIP, NAME, PINS, WAKE_CAPABLE_GPIO, label_for

# The facts about which board this is live in boards/<id>.json and reach the firmware through
# board_spec.py, which is generated from it. This module is the behaviour built on them.
__all__ = ["ADC_GPIO", "CHIP", "NAME", "PINS", "WAKE_CAPABLE_GPIO", "label_for",
           "supports_wake", "assert_wake_capable", "woke_from_sleep", "wake_gpio_numbers",
           "deep_sleep", "start_watchdog", "HAS_USABLE_COPROCESSOR"]

# The chip has a second RISC-V core, but it is a 20 MHz low-power coprocessor, not an application
# core, and MicroPython exposes no way to run code on it. Noted here so nobody goes looking.
HAS_USABLE_COPROCESSOR = False


def supports_wake(gpio_number):
    return gpio_number in WAKE_CAPABLE_GPIO


def assert_wake_capable(gpio_numbers):
    """Fail loudly at configuration time rather than mysteriously failing to ever wake."""
    for number in gpio_numbers:
        if not supports_wake(number):
            wake_labels = ", ".join(label_for(gpio) for gpio in WAKE_CAPABLE_GPIO if
                                    gpio in PINS.values())
            raise ValueError(
                "%s (GPIO%d) cannot wake this chip; only %s can"
                % (label_for(number), number, wake_labels)
            )


def woke_from_sleep():
    """True when this boot is a wake from deep sleep rather than a power-on or reset."""
    import machine

    return machine.wake_reason() != 0  # 0 == ESP_SLEEP_WAKEUP_UNDEFINED, i.e. a cold boot


def wake_gpio_numbers():
    """
    Which GPIOs woke the chip, or () when the port cannot say.

    `machine.wake_pins()` is recent; on a build without it the caller has to work out what woke
    the bin by reading the pins itself, which is why this returns a tuple rather than raising.
    """
    import machine

    if hasattr(machine, "wake_pins"):
        return tuple(machine.wake_pins())
    log.debug("platform: this MicroPython has no wake_pins(); falling back to reading pins")
    return ()


def deep_sleep(wake_gpio_numbers, wake_on_high):
    """
    Stop the chip until one of `wake_gpio_numbers` is asserted. Does not return: waking is a
    full reset, so execution resumes at boot.py.

    Uses `esp32.wake_on_ext1`, which is the one call that works on every chip this project has
    run on. Two expensive mistakes it avoids: `esp32.wake_on_ext0` does not exist at all on the
    ESP32-C6 (it does on the S3), and `Pin.irq(wake=machine.DEEPSLEEP)` silently does nothing on
    either.

    All ext1 wake pins share one polarity, which is why `config.WAKE_ON_HIGH` has to agree with
    how the buttons and the sensor interrupt are wired. On the S3 that is a hardware constraint
    — it has no per-pin trigger mode. On the C6 the silicon does support per-pin levels, but
    MicroPython's API takes a single level for the whole mask, so the constraint holds there too.
    """
    import esp32
    import machine
    from machine import Pin

    assert_wake_capable(wake_gpio_numbers)

    # The pull has to oppose the asserted level, or the pin floats while the chip sleeps and
    # wakes it at random.
    pull = Pin.PULL_DOWN if wake_on_high else Pin.PULL_UP
    pins = [Pin(number, Pin.IN, pull) for number in wake_gpio_numbers]

    level = esp32.WAKEUP_ANY_HIGH if wake_on_high else esp32.WAKEUP_ALL_LOW
    esp32.wake_on_ext1(pins=pins, level=level)
    machine.deepsleep()


def start_watchdog(timeout_ms):
    """
    Start the hardware watchdog. It cannot be stopped again, which is why this is called only
    from the running application and never at import or from `build()`.
    """
    from machine import WDT

    log.info("platform: watchdog armed at %d ms", timeout_ms)
    return WDT(timeout=timeout_ms)
