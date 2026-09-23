"""
A stand-in for MicroPython's `machine` and `esp32` modules, so the device layer can be tested on
a Mac.

The Mac tests otherwise stop at the strategies: `hardware.py` imports `machine`, so nothing that
constructs a real device could run under CPython. With this installed into `sys.modules`, the
whole firmware — device construction, the VL6180X driver's register conversation, the tasks —
runs in-process, and a test can press a button by setting a pin's level.

It models behaviour the firmware actually depends on, and nothing more:
  * pins remember their level and pulls, and inputs read what the test sets,
  * PWM remembers duty, which is how a test sees the motor run,
  * I2C dispatches to fake devices by address, with 16-bit registers as the VL6180X uses,
  * deep sleep raises instead of stopping the world, so a test can assert that it was requested.

Call `install()` before importing anything from `smartbin` that reaches the hardware.
"""

import sys

PULL_UP = "pull_up"
PULL_DOWN = "pull_down"


class FakePin:
    IN = "in"
    OUT = "out"
    PULL_UP = PULL_UP
    PULL_DOWN = PULL_DOWN

    # Every pin ever constructed, so a test can find one by GPIO number and drive it.
    by_number = {}

    def __init__(self, number, mode=None, pull=None, value=None):
        self.number = number
        self.mode = mode
        self.pull = pull
        # An input with a pull-up idles high, which is what makes "pressed == 0" true.
        self.level = value if value is not None else (1 if pull == PULL_UP else 0)
        FakePin.by_number[number] = self

    def value(self, level=None):
        if level is None:
            return self.level
        self.level = level
        return None

    def __repr__(self):
        return "FakePin(%d, level=%d)" % (self.number, self.level)


class FakePWM:
    def __init__(self, pin, freq=None, duty_u16=0):
        self.pin = pin
        self.frequency = freq
        self.duty = duty_u16

    def freq(self, hertz=None):
        if hertz is None:
            return self.frequency
        self.frequency = hertz
        return None

    def duty_u16(self, duty=None):
        if duty is None:
            return self.duty
        self.duty = duty
        return None


class FakeUART:
    """Collects everything written, which is how the MP3 frames are inspected."""

    instances = []

    def __init__(self, uart_id, baudrate=9600, tx=None, rx=None):
        self.uart_id = uart_id
        self.baudrate = baudrate
        self.tx = tx
        self.rx = rx
        self.written = bytearray()
        FakeUART.instances.append(self)

    def write(self, data):
        self.written.extend(data)
        return len(data)

    def read(self, count=None):
        return None


class FakeI2C:
    """
    Dispatches to fake devices by address. Registers are 16-bit, as the VL6180X uses them.

    `devices` maps address -> object with `read_register(register, length)` and
    `write_register(register, data)`.
    """

    devices = {}

    def __init__(self, bus_id=0, sda=None, scl=None, freq=400000):
        self.bus_id = bus_id
        self.sda = sda
        self.scl = scl
        self.freq = freq

    def scan(self):
        return sorted(FakeI2C.devices)

    def readfrom_mem(self, address, register, length, addrsize=8):
        device = self._device(address)
        return device.read_register(register, length)

    def writeto_mem(self, address, register, data, addrsize=8):
        device = self._device(address)
        device.write_register(register, bytes(data))

    def _device(self, address):
        device = FakeI2C.devices.get(address)
        if device is None:
            raise OSError("no fake I2C device at 0x%02X" % address)
        return device


class FakeADC:
    ATTN_11DB = "11db"

    def __init__(self, pin):
        self.pin = pin
        self.counts = 0
        self.attenuation = None

    def atten(self, attenuation):
        self.attenuation = attenuation

    def read_u16(self):
        return self.counts


class FakeWDT:
    instances = []

    def __init__(self, timeout=0):
        self.timeout = timeout
        self.feeds = 0
        FakeWDT.instances.append(self)

    def feed(self):
        self.feeds += 1


class DeepSleepRequested(Exception):
    """Raised instead of sleeping, so a test can assert on the request and its wake pins."""

    def __init__(self, wake_pins, level):
        super().__init__("deep sleep requested")
        self.wake_pins = wake_pins
        self.level = level


class FakeMachineModule:
    """The subset of `machine` the firmware uses."""

    Pin = FakePin
    PWM = FakePWM
    UART = FakeUART
    I2C = FakeI2C
    ADC = FakeADC
    WDT = FakeWDT

    EXT1_WAKE = 3
    PIN_WAKE = 2

    # Set by a test to say how this boot started: 0 is a cold boot.
    wake_reason_value = 0
    wake_pins_value = ()
    armed_wake = None

    @classmethod
    def wake_reason(cls):
        return cls.wake_reason_value

    @classmethod
    def wake_pins(cls):
        return cls.wake_pins_value

    @classmethod
    def deepsleep(cls, milliseconds=None):
        raise DeepSleepRequested(*(cls.armed_wake or ((), None)))


class FakeEsp32Module:
    """The subset of `esp32` the firmware uses."""

    WAKEUP_ANY_HIGH = "any_high"
    WAKEUP_ALL_LOW = "all_low"

    @staticmethod
    def wake_on_ext1(pins, level):
        FakeMachineModule.armed_wake = (tuple(pin.number for pin in pins), level)


def install():
    """Put the fakes in `sys.modules` and hand back the machine module for a test to drive."""
    sys.modules["machine"] = FakeMachineModule
    sys.modules["esp32"] = FakeEsp32Module
    return FakeMachineModule


def reset():
    """Forget every pin, device and armed wake between tests."""
    FakePin.by_number.clear()
    FakeUART.instances.clear()
    FakeWDT.instances.clear()
    FakeI2C.devices.clear()
    FakeMachineModule.wake_reason_value = 0
    FakeMachineModule.wake_pins_value = ()
    FakeMachineModule.armed_wake = None


class FakeVL6180X:
    """
    Enough of the real chip for the driver to talk to it: the model ID it checks, a range value
    the test chooses, and a status of "sample ready".

    Registers the driver writes are recorded rather than interpreted, so a test can assert that
    (say) continuous ranging was started, without this becoming a second implementation.
    """

    MODEL_ID_REGISTER = 0x000
    FRESH_OUT_OF_RESET = 0x016
    INTERRUPT_STATUS = 0x04F
    RANGE_VALUE = 0x062
    RANGE_STATUS = 0x04D
    RETURN_RATE = 0x066

    def __init__(self, distance_mm=50, status=0):
        self.distance_mm = distance_mm
        self.status = status
        self.writes = {}
        self.fresh_out_of_reset = 1

    def read_register(self, register, length):
        if register == self.MODEL_ID_REGISTER:
            value = 0xB4
        elif register == self.FRESH_OUT_OF_RESET:
            value = self.fresh_out_of_reset
        elif register == self.INTERRUPT_STATUS:
            value = 0x04            # "new sample ready"
        elif register == self.RANGE_VALUE:
            value = self.distance_mm
        elif register == self.RANGE_STATUS:
            value = self.status << 4
        elif register == self.RETURN_RATE:
            return bytes((0x00, 0x10))
        else:
            value = self.writes.get(register, 0)
        return bytes((value,)) if length == 1 else bytes((0, value))

    def write_register(self, register, data):
        self.writes[register] = data[0] if len(data) == 1 else (data[0] << 8) | data[1]
        if register == self.FRESH_OUT_OF_RESET:
            self.fresh_out_of_reset = data[0]
