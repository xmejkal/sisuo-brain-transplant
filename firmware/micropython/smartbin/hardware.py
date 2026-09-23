"""
Every peripheral, constructed in one place.

With platform.py, this is the only module that touches `machine`. Everything else receives what
it needs, which is what lets the logic run under CPython in tests and what makes the sensor
wiring a config choice rather than a rewrite.

Constructing this moves nothing: pins are set to their resting state and that is all.

Pin numbers are ESP32-C6 GPIO numbers, not XIAO D-numbers; config.py maps between them.
"""

from machine import ADC, I2C, PWM, Pin, UART

from . import audio, log, motor, ui


class Hardware:
    """
    The bin's peripherals. Attributes that depend on which parts are fitted are None when they
    are not — `sensor_bus`, `tof_interrupt`, `ir_emitter`, `ir_receiver`, `shunt_adc`,
    `limit_switch`.
    """

    def __init__(self, config):
        self.config = config

        self.sensor_bus = None
        self.tof_interrupt = None
        self.ir_emitter = None
        self.ir_receiver = None
        self.shunt_adc = None
        self.limit_switch = None

        self.motor = self._build_motor(config)
        self.button_open, self.button_mode, self.led = self._build_controls(config)
        self.player = self._build_player(config)
        self._build_sensor_pins(config)
        self._build_close_detection_pins(config)

    # ----------------------------------------------------------------- construction
    def _build_motor(self, config):
        """
        Both L9110S inputs are PWM-capable, because either one is the driven pin depending on
        direction. They are pulled low in hardware too (10k), which is what keeps the motor still
        during the ~300 ms between reset and this code running.
        """
        self.motor_pwm_a = PWM(Pin(config.PIN_MOTOR_IA), freq=config.MOTOR_PWM_FREQ_HZ, duty_u16=0)
        self.motor_pwm_b = PWM(Pin(config.PIN_MOTOR_IB), freq=config.MOTOR_PWM_FREQ_HZ, duty_u16=0)
        return motor.L9110MotorDriver(self.motor_pwm_a, self.motor_pwm_b)

    def _build_controls(self, config):
        """Buttons wire to ground and use the internal pull-ups, so pressed reads 0."""
        button_open = ui.Button(
            Pin(config.PIN_BUTTON_OPEN, Pin.IN, Pin.PULL_UP), config.BUTTON_DEBOUNCE_MS
        )
        button_mode = ui.Button(
            Pin(config.PIN_BUTTON_MODE, Pin.IN, Pin.PULL_UP), config.BUTTON_DEBOUNCE_MS
        )
        led = ui.StatusLed(
            Pin(config.PIN_LED_RED, Pin.OUT, value=0),
            Pin(config.PIN_LED_GREEN, Pin.OUT, value=0),
        )
        return button_open, button_mode, led

    def _build_player(self, config):
        if not config.AUDIO_ENABLED:
            return audio.SilentPlayer()
        uart = UART(
            config.MP3_UART_ID,
            baudrate=config.MP3_BAUD,
            tx=config.PIN_MP3_TX,
            rx=-1,  # the module's TXD is deliberately not wired; see audio.Dfr0534Player
        )
        return audio.Dfr0534Player(uart, config.VOLUME)

    def _build_sensor_pins(self, config):
        """
        The ToF and IR wirings share D4/D5 physically, so only one can be fitted at a time —
        which is why config.py gives those pins two names and this builds only one of them.
        """
        if config.SENSOR_STRATEGY in ("tof", "tof_interrupt"):
            self.sensor_bus = I2C(
                0,
                sda=Pin(config.PIN_I2C_SDA),
                scl=Pin(config.PIN_I2C_SCL),
                freq=config.I2C_FREQ_HZ,
            )
            if config.SENSOR_STRATEGY == "tof_interrupt":
                # No internal pull: the breakout pulls its interrupt pin to its own 2.8 V, and a
                # pull the other way would fight it.
                self.tof_interrupt = Pin(config.PIN_TOF_INTERRUPT, Pin.IN)
        elif config.SENSOR_STRATEGY == "ir":
            self.ir_emitter = PWM(
                Pin(config.PIN_IR_EMITTER), freq=config.IR_CARRIER_HZ, duty_u16=0
            )
            self.ir_receiver = Pin(config.PIN_IR_RECEIVER, Pin.IN)

    def _build_close_detection_pins(self, config):
        if config.CLOSE_DETECTOR == "stall":
            self.shunt_adc = ADC(Pin(config.PIN_SHUNT_ADC))
            self.shunt_adc.atten(ADC.ATTN_11DB)  # the full ~0-3.1 V span
        elif config.CLOSE_DETECTOR == "limit":
            self.limit_switch = Pin(config.PIN_LIMIT_SWITCH, Pin.IN, Pin.PULL_UP)

    # ----------------------------------------------------------------- bench helpers
    def scan_i2c(self):
        """`b.hardware.scan_i2c()` should list 0x29 when the ToF sensor is wired."""
        if self.sensor_bus is None:
            log.warn("no I2C bus in %s sensor configuration", self.config.SENSOR_STRATEGY)
            return []
        return [hex(address) for address in self.sensor_bus.scan()]

    def enter_safe_state(self):
        """Motor stopped, LED dark, IR emitter off. Called on shutdown, before sleep, and by hand."""
        self.motor.stop()
        self.led.set(ui.OFF)
        if self.ir_emitter is not None:
            self.ir_emitter.duty_u16(0)
