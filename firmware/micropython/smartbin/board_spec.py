"""
Seeed XIAO ESP32-C6 — the facts, generated from boards/xiao-esp32-c6.json.

DO NOT EDIT. Run `make` after changing the board definition; `make check` fails if this is stale.

The silkscreen label is not the GPIO number on this board — D3 is GPIO21 — which is the
single easiest mistake to make here, and the reason this table exists in exactly one place.

# Pins with a second job:
#   GPIO16: U0TXD - the ROM bootloader prints its log here on every reset. Safe for a button, never for a module that parses serial.
#   GPIO15: the on-board user LED (not on the header)
"""

NAME = "Seeed XIAO ESP32-C6"
CHIP = "esp32c6"

#: Silkscreen label -> GPIO number.
PINS = {
    "D0": 0,
    "D1": 1,
    "D2": 2,
    "D6": 16,
    "D7": 17,
    "D10": 18,
    "D8": 19,
    "D9": 20,
    "D3": 21,
    "D4": 22,
    "D5": 23,
}

#: GPIOs that can wake the chip from deep sleep. On this board that is D0, D1, D2 and nothing else.
WAKE_CAPABLE_GPIO = (0, 1, 2, 3, 4, 5, 6, 7)

#: GPIOs with an analogue input.
ADC_GPIO = (0, 1, 2)


def label_for(gpio):
    """The silkscreen label for a GPIO, for log messages a person has to read."""
    for label, number in PINS.items():
        if number == gpio:
            return label
    return "GPIO%d" % gpio
