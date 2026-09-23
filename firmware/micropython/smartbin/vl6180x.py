"""
VL6180X time-of-flight driver for MicroPython.

Ported from Adafruit's maintained CircuitPython driver (MIT licensed) rather than using the only
existing MicroPython one, which was last touched in 2017 and raises on every soft reset that does
not power-cycle the sensor, and never checks the range status — so a sensor error is
indistinguishable from a genuine 255 mm reading.

Changes from the CircuitPython original:
  * I2C through `machine.I2C` with `addrsize=16`, so it works on hardware I2C.
  * `range()` checks RESULT__RANGE_STATUS and raises `RangeError` rather than returning nonsense.
  * The calibration registers the lid needs are exposed: offset, crosstalk and range-ignore.
    Behind the bin's window a reflection off the plastic reads as a permanent "hand", and
    range-ignore is what suppresses it. See parts/SENSOR_OPTIONS.md for the procedures.

The sensor is a 2.8 V part. Breakouts with a regulator and level shifter (Adafruit, Pololu) are
safe on 3.3 V; a bare board may not be.
"""

from . import log

DEFAULT_ADDRESS = 0x29
MODEL_ID = 0xB4

# --- registers (16-bit addresses) ------------------------------------------------------------
_IDENTIFICATION_MODEL_ID = 0x000
_SYSTEM_MODE_GPIO1 = 0x011
_SYSTEM_GROUPED_PARAMETER_HOLD = 0x017
_SYSRANGE_THRESH_HIGH = 0x019
_SYSRANGE_THRESH_LOW = 0x01A
_SYSTEM_INTERRUPT_CONFIG = 0x014
_SYSTEM_INTERRUPT_CLEAR = 0x015
_SYSTEM_FRESH_OUT_OF_RESET = 0x016
_SYSRANGE_START = 0x018
_SYSRANGE_INTERMEASUREMENT_PERIOD = 0x01B
_SYSRANGE_CROSSTALK_COMPENSATION_RATE = 0x01E
_SYSRANGE_PART_TO_PART_RANGE_OFFSET = 0x024
_SYSRANGE_RANGE_IGNORE_THRESHOLD = 0x026
_SYSRANGE_RANGE_CHECK_ENABLES = 0x02D
_RESULT_RANGE_STATUS = 0x04D
_RESULT_INTERRUPT_STATUS_GPIO = 0x04F
_RESULT_RANGE_VAL = 0x062
_RESULT_RANGE_RETURN_RATE = 0x066

# Range status codes worth naming; anything non-zero means "do not trust the number".
ERROR_NONE = 0
ERROR_NOCONVERGE = 7
ERROR_RANGEIGNORE = 8

# SYSTEM__INTERRUPT_CONFIG_GPIO, bits[2:0]: when GPIO1 should be asserted.
INT_DISABLED = 0
INT_LEVEL_LOW = 1      # closer than THRESH_LOW - this is the "a hand appeared" case
INT_LEVEL_HIGH = 2
INT_OUT_OF_WINDOW = 3
INT_NEW_SAMPLE = 4

# ST's recommended "private register" tuning block, applied once after reset. The values are
# undocumented by design; they come from the datasheet's mandatory init sequence.
_TUNING = (
    (0x0207, 0x01), (0x0208, 0x01), (0x0096, 0x00), (0x0097, 0xFD), (0x00E3, 0x00),
    (0x00E4, 0x04), (0x00E5, 0x02), (0x00E6, 0x01), (0x00E7, 0x03), (0x00F5, 0x02),
    (0x00D9, 0x05), (0x00DB, 0xCE), (0x00DC, 0x03), (0x00DD, 0xF8), (0x009F, 0x00),
    (0x00A3, 0x3C), (0x00B7, 0x00), (0x00BB, 0x3C), (0x00B2, 0x09), (0x00CA, 0x09),
    (0x0198, 0x01), (0x01B0, 0x17), (0x01AD, 0x00), (0x00FF, 0x05), (0x0100, 0x05),
    (0x0199, 0x05), (0x01A6, 0x1B), (0x01AC, 0x3E), (0x01A7, 0x1F), (0x0030, 0x00),
)

# Public registers, from the same sequence.
_DEFAULTS = (
    (0x0011, 0x10),  # poll for "new sample ready"
    (0x010A, 0x30),  # averaging sample period
    (0x003F, 0x46),  # light and dark gain
    (0x0031, 0xFF),  # auto-calibrate every N measurements
    (0x0040, 0x63),  # ALS integration time 100 ms
    (0x002E, 0x01),  # one temperature calibration
    (0x001B, 0x09),  # ranging inter-measurement period 100 ms
    (0x003E, 0x31),  # ALS inter-measurement period 500 ms
    (0x0014, 0x24),  # interrupt on new sample ready
)


class RangeError(Exception):
    """The sensor reported a measurement error; the distance value is meaningless."""

    def __init__(self, status):
        super().__init__("VL6180X range status %d" % status)
        self.status = status


class VL6180X:
    """Single-shot ranging driver. `i2c` is a machine.I2C; reads raise OSError if it is unwired."""

    def __init__(self, i2c, address=DEFAULT_ADDRESS, offset=None, poll_limit=100):
        self._i2c = i2c
        self._address = address
        self._poll_limit = poll_limit

        model = self._read8(_IDENTIFICATION_MODEL_ID)
        if model != MODEL_ID:
            raise RuntimeError("Not a VL6180X at 0x%02X (model id 0x%02X)" % (address, model))

        # Only load the tuning block on a freshly reset part, as ST specifies — but unlike the
        # 2017 driver, not finding it fresh is normal (a soft reset of the board leaves the
        # sensor configured) and must not be an error.
        if self._read8(_SYSTEM_FRESH_OUT_OF_RESET) == 1:
            self._load_settings()
            self._write8(_SYSTEM_FRESH_OUT_OF_RESET, 0x00)
        else:
            log.debug("VL6180X already configured; skipping tuning block")

        if offset is not None:
            self.offset = offset

    # ----------------------------------------------------------------- I2C
    def _write8(self, register, value):
        self._i2c.writeto_mem(self._address, register, bytes((value,)), addrsize=16)

    def _write16(self, register, value):
        self._i2c.writeto_mem(
            self._address, register, bytes(((value >> 8) & 0xFF, value & 0xFF)), addrsize=16
        )

    def _read8(self, register):
        return self._i2c.readfrom_mem(self._address, register, 1, addrsize=16)[0]

    def _read16(self, register):
        data = self._i2c.readfrom_mem(self._address, register, 2, addrsize=16)
        return (data[0] << 8) | data[1]

    def _load_settings(self):
        for register, value in _TUNING:
            self._write8(register, value)
        for register, value in _DEFAULTS:
            self._write8(register, value)

    # ----------------------------------------------------------------- ranging
    def range(self):
        """
        One measurement, in millimetres. Raises `RangeError` if the sensor flags a problem.

        Polling is bounded: a sensor that never signals "ready" raises rather than hanging the
        firmware, which matters because this runs inside the lid's event loop.
        """
        self._write8(_SYSRANGE_START, 0x01)

        for _ in range(self._poll_limit):
            if self._read8(_RESULT_INTERRUPT_STATUS_GPIO) & 0x04:
                break
            _sleep_ms(1)
        else:
            raise OSError("VL6180X timed out waiting for a sample")

        distance = self._read8(_RESULT_RANGE_VAL)
        status = self._read8(_RESULT_RANGE_STATUS) >> 4
        self._write8(_SYSTEM_INTERRUPT_CLEAR, 0x07)

        if status != ERROR_NONE:
            raise RangeError(status)
        return distance

    def range_or_none(self):
        """`range()` without the exception — None when the reading is not trustworthy."""
        try:
            return self.range()
        except RangeError as exception:
            log.debug("VL6180X range error %d", exception.status)
            return None

    @property
    def return_rate(self):
        """RESULT__RANGE_RETURN_RATE, needed by the crosstalk calibration procedure."""
        return self._read16(_RESULT_RANGE_RETURN_RATE)

    # ----------------------------------------------------------------- autonomous ranging
    def configure_interrupt(self, threshold_low_mm, mode=INT_LEVEL_LOW, active_high=True):
        """
        Make GPIO1 assert when a reading crosses a threshold, with no host involvement.

        This is what lets the ESP32 deep-sleep: the sensor keeps ranging by itself and only
        wakes the chip when something is closer than `threshold_low_mm`.

        `active_high` matters on this board — MicroPython's low-level deep-sleep wake on the C6
        has an open "stuck pin" bug, so the wake signal is configured high-going. Note the pin is
        open-drain: asserted-high relies on the breakout's pull-up (both Adafruit and Pololu have
        one, to 2.8 V, which clears the C6's input threshold).
        """
        self._write8(_SYSTEM_MODE_GPIO1, 0x30 if active_high else 0x10)
        self._write8(_SYSTEM_GROUPED_PARAMETER_HOLD, 0x01)
        self._write8(_SYSRANGE_THRESH_LOW, threshold_low_mm & 0xFF)
        self._write8(_SYSRANGE_THRESH_HIGH, 0xFF)
        self._write8(_SYSTEM_INTERRUPT_CONFIG, mode)
        self._write8(_SYSTEM_GROUPED_PARAMETER_HOLD, 0x00)
        self.clear_interrupt()

    def start_continuous(self, period_ms=500):
        """
        Range repeatedly on the sensor's own clock. The period sets the idle current: roughly
        1.7 mA at 10 Hz, scaling down with rate, so ~340 uA at 500 ms and ~170 uA at 1 s.
        Maximum is 2550 ms.
        """
        self._write8(_SYSRANGE_INTERMEASUREMENT_PERIOD, max(0, min(254, period_ms // 10)))
        self._write8(_SYSRANGE_START, 0x03)

    def stop_continuous(self):
        if self._read8(_SYSRANGE_START) & 0x02:
            self._write8(_SYSRANGE_START, 0x01)

    def interrupt_pending(self):
        return bool(self._read8(_RESULT_INTERRUPT_STATUS_GPIO) & 0x07)

    def clear_interrupt(self):
        """The interrupt latches until this is called, so it always follows a wake."""
        self._write8(_SYSTEM_INTERRUPT_CLEAR, 0x07)

    def last_range(self):
        """The most recent continuous-mode reading, without starting a new measurement."""
        return self._read8(_RESULT_RANGE_VAL)

    # ----------------------------------------------------------------- calibration
    @property
    def offset(self):
        value = self._read8(_SYSRANGE_PART_TO_PART_RANGE_OFFSET)
        return value - 256 if value > 127 else value

    @offset.setter
    def offset(self, millimetres):
        self._write8(_SYSRANGE_PART_TO_PART_RANGE_OFFSET, millimetres & 0xFF)

    @property
    def crosstalk(self):
        """Crosstalk compensation, in 9.7 fixed point (Mcps * 128)."""
        return self._read16(_SYSRANGE_CROSSTALK_COMPENSATION_RATE)

    @crosstalk.setter
    def crosstalk(self, fixed_point):
        self._write16(_SYSRANGE_CROSSTALK_COMPENSATION_RATE, fixed_point)

    def set_range_ignore(self, threshold_fixed_point):
        """
        Ignore returns weaker than `threshold_fixed_point` (9.7 fixed point).

        This is what stops the lid's own window — or dust on it — from reading as a hand. ST
        recommends at least 1.2x the measured crosstalk. Pass 0 to disable.
        """
        enables = self._read8(_SYSRANGE_RANGE_CHECK_ENABLES)
        if threshold_fixed_point:
            self._write16(_SYSRANGE_RANGE_IGNORE_THRESHOLD, threshold_fixed_point)
            self._write8(_SYSRANGE_RANGE_CHECK_ENABLES, enables | 0x02)
        else:
            self._write8(_SYSRANGE_RANGE_CHECK_ENABLES, enables & ~0x02)


def _sleep_ms(milliseconds):
    from .compat import sleep_ms

    sleep_ms(milliseconds)
