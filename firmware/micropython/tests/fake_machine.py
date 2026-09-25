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
    """Collects everything written, which is how the DFR0534 strategy's frames are inspected."""

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


class FakeI2S:
    """
    Collects everything written, which is how a cue's samples are inspected.

    Modelled as a stream because that is how the firmware drives it: `asyncio.StreamWriter`
    wraps this object, so it needs the two methods a stream needs. `write` returning the full
    length means a single drain completes it, which is the behaviour of a driver whose ring
    buffer is bigger than the cue — the configured case.
    """

    TX = "tx"
    RX = "rx"
    MONO = "mono"
    STEREO = "stereo"

    instances = []

    def __init__(self, i2s_id, sck=None, ws=None, sd=None, mode=None,
                 bits=16, format=None, rate=None, ibuf=None):
        self.i2s_id = i2s_id
        self.sck, self.ws, self.sd = sck, ws, sd
        self.mode, self.bits, self.format, self.rate, self.ibuf = mode, bits, format, rate, ibuf
        self.written = bytearray()
        self.deinitialised = False
        FakeI2S.instances.append(self)

    def write(self, data):
        self.written.extend(data)
        return len(data)

    def deinit(self):
        self.deinitialised = True

    # asyncio.StreamWriter asks for these when it wraps a stream.
    def ioctl(self, request, argument):
        return 0


class BusSilent(Exception):
    """Raised by a fake device that has stopped answering, to model a knocked-loose cable."""


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
        if getattr(device, "unplugged", False):
            raise OSError("fake I2C device at 0x%02X is not answering" % address)
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
    I2S = FakeI2S
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
    try:
        import config
        FakeVL6180X.interrupt_gpio = config.PIN_TOF_INTERRUPT
    except (ImportError, AttributeError):
        pass    # a caller testing something else entirely; the interrupt is simply not modelled
    return FakeMachineModule


def reset():
    """Forget every pin, device and armed wake between tests."""
    FakePin.by_number.clear()
    FakeUART.instances.clear()
    FakeI2S.instances.clear()
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

    #: Registers this fake needs to model the INTERRUPT, not just the bus.
    SYSTEM_MODE_GPIO1 = 0x011
    SYSRANGE_THRESH_LOW = 0x01A
    GPIO1_ACTIVE_HIGH = 0x30

    #: Which GPIO this chip's interrupt line is wired to, so the fake can find the pin the
    #: FIRMWARE built rather than one made here that nothing reads. Set once by `install()` from
    #: the project's own config, because five call sites threading a pin through would be five
    #: chances to forget one — and a forgotten one is a test that silently stops checking.
    interrupt_gpio = None

    def __init__(self, distance_mm=50, status=0, interrupt_pin=None):
        #: The pin this chip drives when something comes within its threshold.
        #:
        #: Modelled because it was not, and the omission hid a passing test that proved nothing.
        #: The firmware builds the interrupt pin with NO pull — correct, since the board carries
        #: an external one — so in these fakes it simply read 0. The strategy was configured
        #: active-LOW at the time, so "0" meant asserted, and the bring-up script's WAVE phase
        #: passed on a pin nothing had ever driven. Flipping the wake polarity to HIGH is what
        #: exposed it: the same test went red without anything about the sensor changing.
        self.interrupt_pin = interrupt_pin
        self._distance_mm = distance_mm
        #: Range status, as the real chip reports it: 0 is a good reading, 7 is "could not
        #: converge", which is what an empty field of view produces.
        self.status = status
        self.writes = {}
        self.fresh_out_of_reset = 1
        #: Set True to model the cable coming out: every transaction then raises OSError.
        self.unplugged = False

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

    @property
    def distance_mm(self):
        return self._distance_mm

    @distance_mm.setter
    def distance_mm(self, value):
        self._distance_mm = value
        self._drive_interrupt()

    def _drive_interrupt(self):
        """
        Assert the line when something is within the threshold the firmware asked for.

        Polarity and threshold both come from what the driver WROTE, so this follows the
        firmware's own configuration rather than a second copy of it that could disagree.
        """
        pin = self.interrupt_pin
        if pin is None and self.interrupt_gpio is not None:
            # Resolved late: the firmware constructs its pins after the sensor exists.
            pin = FakePin.by_number.get(self.interrupt_gpio)
        if pin is None:
            return
        threshold = self.writes.get(self.SYSRANGE_THRESH_LOW)
        if threshold is None:
            return
        active_high = self.writes.get(self.SYSTEM_MODE_GPIO1) == self.GPIO1_ACTIVE_HIGH
        asserted = 1 if active_high else 0
        within = self._distance_mm is not None and self._distance_mm <= threshold
        pin.value(asserted if within else 1 - asserted)

    def write_register(self, register, data):
        self.writes[register] = data[0] if len(data) == 1 else (data[0] << 8) | data[1]
        if register == self.FRESH_OUT_OF_RESET:
            self.fresh_out_of_reset = data[0]
        if register in (self.SYSTEM_MODE_GPIO1, self.SYSRANGE_THRESH_LOW):
            self._drive_interrupt()
