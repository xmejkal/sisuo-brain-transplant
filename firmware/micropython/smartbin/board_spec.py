"""
DFRobot FireBeetle 2 ESP32-S3 — the facts, generated from boards/firebeetle2-esp32s3.json.

DO NOT EDIT. Run `make` after changing the board definition; `make check` fails if this is stale.

The silkscreen label is not the GPIO number on this board — D9 is GPIO0 — which is the
single easiest mistake to make here, and the reason this table exists in exactly one place.

# Pins with a second job:
#   D9, D2: D9 is GPIO0, the BOOT pin - held low at reset it enters the bootloader, so nothing may drive it low during power-up. D2 is GPIO3, the JTAG source select strap. Both are usable as ordinary I/O once running; neither is safe for something that idles low.
#   A5, D12, D11, D10, MOSI, MISO, SCK, D6, GPIO19, GPIO20: on ADC2, which shares hardware with the radio. A5 (GPIO11) is the one that matters here: it is labelled analogue but cannot be read with WiFi active. Use A0-A4 or D5/D7 for analogue instead.
#   TX: U0TXD - the ROM bootloader prints its log here on every reset. Safe for a button, never for a module that parses serial.
#   D13: the on-board user LED, silkscreened D13. Usable, but it will blink whatever you put on it.
#   D14: the on-board user button, silkscreened D14. Already has a button on it, and cannot wake the chip from deep sleep.
#   D3, TX, RX, D14: outside the RTC domain, so these cannot wake the chip however they are configured. Everything else on the header can.
"""

NAME = "DFRobot FireBeetle 2 ESP32-S3"
CHIP = "esp32s3"

#: Silkscreen label -> GPIO number.
PINS = {
    "D9": 0,
    "SDA": 1,
    "SCL": 2,
    "D2": 3,
    "A0": 4,
    "A1": 5,
    "A2": 6,
    "D5": 7,
    "A3": 8,
    "D7": 9,
    "A4": 10,
    "SS": 10,
    "A5": 11,
    "D12": 12,
    "D11": 13,
    "D10": 14,
    "MOSI": 15,
    "MISO": 16,
    "SCK": 17,
    "D6": 18,
    "D13": 21,
    "D3": 38,
    "TX": 43,
    "RX": 44,
    "D14": 47,
}

#: GPIOs that can wake the chip from deep sleep. On this board that is every pin except D3, TX, RX, D14.
WAKE_CAPABLE_GPIO = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21)

#: GPIOs with an analogue input.
ADC_GPIO = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)


def label_for(gpio):
    """The silkscreen label for a GPIO, for log messages a person has to read."""
    for label, number in PINS.items():
        if number == gpio:
            return label
    return "GPIO%d" % gpio
