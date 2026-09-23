"""
Every peripheral, constructed in one place.

This is the only module that imports `machine`. Everything else receives what it needs, which is
what lets the logic run under CPython in tests and what makes the two sensor wirings (ToF or IR)
a config choice rather than a rewrite.

Pin numbers here are ESP32-C6 GPIO numbers, not XIAO D-numbers; `config.py` maps between them.
"""

from machine import ADC, I2C, PWM, Pin, UART

from . import audio, log, motor, ui


class Hardware:
    """Constructs peripherals from config. Constructing this does not move anything."""

    def __init__(self, config):
        self.config = config

        # Motor: both L9110S inputs are PWM-capable, because either one is the driven pin
        # depending on direction. Pulled low in hardware too (10k), which is what protects the
        # motor during the window between reset and this code running.
        self.pwm_a = PWM(Pin(config.PIN_MOTOR_IA), freq=config.MOTOR_PWM_FREQ_HZ, duty_u16=0)
        self.pwm_b = PWM(Pin(config.PIN_MOTOR_IB), freq=config.MOTOR_PWM_FREQ_HZ, duty_u16=0)
        self.motor = motor.L9110Driver(self.pwm_a, self.pwm_b)

        self.button_open = ui.Button(
            Pin(config.PIN_BUTTON_OPEN, Pin.IN, Pin.PULL_UP), config.BUTTON_DEBOUNCE_MS
        )
        self.button_mode = ui.Button(
            Pin(config.PIN_BUTTON_MODE, Pin.IN, Pin.PULL_UP), config.BUTTON_DEBOUNCE_MS
        )
        self.led = ui.StatusLed(
            Pin(config.PIN_LED_RED, Pin.OUT, value=0), Pin(config.PIN_LED_GREEN, Pin.OUT, value=0)
        )

        self.player = self._build_player()
        self.i2c = None
        self.ir_emitter = None
        self.ir_receiver = None
        self.shunt_adc = None
        self.limit_switch = None
        self._build_sensor_pins()
        self._build_close_detection_pins()

    def _build_player(self):
        if not self.config.AUDIO_ENABLED:
            return audio.NullPlayer()
        uart = UART(
            self.config.MP3_UART_ID,
            baudrate=self.config.MP3_BAUD,
            tx=self.config.PIN_MP3_TX,
            rx=-1,  # the module's TXD is deliberately not wired; see audio.Dfr0534
        )
        return audio.Dfr0534(uart, self.config.VOLUME)

    def _build_sensor_pins(self):
        """The two sensor wirings share pins D4/D5, so only one can exist at a time."""
        if self.config.SENSOR == "tof":
            self.i2c = I2C(
                0,
                sda=Pin(self.config.PIN_I2C_SDA),
                scl=Pin(self.config.PIN_I2C_SCL),
                freq=self.config.I2C_FREQ_HZ,
            )
        elif self.config.SENSOR == "ir":
            self.ir_emitter = PWM(
                Pin(self.config.PIN_IR_EMITTER), freq=self.config.IR_CARRIER_HZ, duty_u16=0
            )
            self.ir_receiver = Pin(self.config.PIN_IR_RECEIVER, Pin.IN)

    def _build_close_detection_pins(self):
        if self.config.CLOSE_DETECT == "stall":
            self.shunt_adc = ADC(Pin(self.config.PIN_SHUNT_ADC))
            self.shunt_adc.atten(ADC.ATTN_11DB)  # full ~0-3.1 V span
        elif self.config.CLOSE_DETECT == "limit":
            self.limit_switch = Pin(self.config.PIN_LIMIT_SWITCH, Pin.IN, Pin.PULL_UP)

    def scan_i2c(self):
        """Bench helper: `b.hw.scan_i2c()` should show 0x29 for the VL6180X."""
        if self.i2c is None:
            log.warn("no I2C bus in %s sensor config", self.config.SENSOR)
            return []
        return [hex(address) for address in self.i2c.scan()]

    def all_off(self):
        """Everything to its safe resting state. Called on shutdown and from the REPL."""
        self.motor.stop()
        self.led.set(ui.OFF)
        if self.ir_emitter is not None:
            self.ir_emitter.duty_u16(0)
