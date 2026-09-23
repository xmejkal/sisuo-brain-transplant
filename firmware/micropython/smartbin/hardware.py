"""
Every device the bin can command or read, constructed in one place.

THE RULE, because it was not obvious before: **hardware owns devices, not decisions.**

    a device      knows how to talk to a physical thing: the motor driver, the LED, a button,
                  the MP3 module, the rangefinder chip. It has no opinion about the lid.
    a strategy    makes a decision using devices: "is that a hand?", "is the lid shut?",
                  "should we sleep?" Those live in sensors.py, closing.py and power.py, and are
                  assembled in factory.py.

So the rangefinder *chip* is here next to the motor, while "is a hand there?" is not — that is a
judgement, and which judgement you want is a config choice.

With platform.py this is the only module that touches `machine`, which is what lets everything
else be tested on a PC. Constructing it moves nothing: pins go to their resting state, no more.

Pin numbers are ESP32-C6 GPIO numbers, not XIAO D-numbers; config.py maps between them.
"""

from machine import ADC, I2C, PWM, Pin, UART

from . import audio, log, motor, ui


class Hardware:
    """
    The bin's devices.

    Which of them exist depends on which parts are fitted, so these are None when they are not:
    `sensor_bus`, `rangefinder`, `rangefinder_interrupt`, `ir_emitter`, `ir_receiver`,
    `current_sense`, `limit_switch`.
    """

    def __init__(self, config):
        self.config = config

        # Always fitted.
        self.motor = self._build_motor(config)
        self.button_open, self.button_mode, self.led = self._build_controls(config)
        self.player = self._build_player(config)

        # Fitted only in some configurations; see the class docstring.
        self.sensor_bus = None
        self.rangefinder = None
        self.rangefinder_interrupt = None
        self.ir_emitter = None
        self.ir_receiver = None
        self.current_sense = None
        self.limit_switch = None
        self._build_proximity_devices(config)
        self._build_close_detection_devices(config)

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
        """Buttons wire to ground and use the internal pull-ups, so a pressed button reads 0."""
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

    def _build_proximity_devices(self, config):
        """
        The rangefinder or the IR pair — never both. They share D4/D5 physically, which is why
        config.py gives those pins two names and only one set is ever constructed.
        """
        if config.SENSOR_STRATEGY in ("tof", "tof_interrupt"):
            self.sensor_bus = I2C(
                0,
                sda=Pin(config.PIN_I2C_SDA),
                scl=Pin(config.PIN_I2C_SCL),
                freq=config.I2C_FREQ_HZ,
            )
            self.rangefinder = self._build_rangefinder(config)
            if config.SENSOR_STRATEGY == "tof_interrupt":
                # No internal pull: the breakout pulls its interrupt pin to its own 2.8 V, and a
                # pull the other way would fight it.
                self.rangefinder_interrupt = Pin(config.PIN_TOF_INTERRUPT, Pin.IN)
        elif config.SENSOR_STRATEGY == "ir":
            self.ir_emitter = PWM(
                Pin(config.PIN_IR_EMITTER), freq=config.IR_CARRIER_HZ, duty_u16=0
            )
            self.ir_receiver = Pin(config.PIN_IR_RECEIVER, Pin.IN)

    def _build_rangefinder(self, config):
        """The VL6180X, with whatever this particular bin has been calibrated to."""
        from .vl6180x import VL6180X

        rangefinder = VL6180X(self.sensor_bus, offset=config.TOF_OFFSET_MM)
        if config.TOF_CROSSTALK:
            rangefinder.crosstalk = config.TOF_CROSSTALK
        if config.TOF_RANGE_IGNORE:
            rangefinder.set_range_ignore(config.TOF_RANGE_IGNORE)
        return rangefinder

    def _build_close_detection_devices(self, config):
        if config.CLOSE_DETECTOR == "stall":
            self.current_sense = ADC(Pin(config.PIN_SHUNT_ADC))
            self.current_sense.atten(ADC.ATTN_11DB)  # the full ~0-3.1 V span
        elif config.CLOSE_DETECTOR == "limit":
            self.limit_switch = Pin(config.PIN_LIMIT_SWITCH, Pin.IN, Pin.PULL_UP)

    # ----------------------------------------------------------------- bench helpers
    def scan_i2c(self):
        """`b.hardware.scan_i2c()` should list 0x29 when the rangefinder is wired."""
        if self.sensor_bus is None:
            log.warn("no I2C bus in %s sensor configuration", self.config.SENSOR_STRATEGY)
            return []
        return [hex(address) for address in self.sensor_bus.scan()]

    def enter_safe_state(self):
        """Motor stopped, LED dark, IR emitter off. On shutdown, before sleep, and by hand."""
        self.motor.stop()
        self.led.set(ui.OFF)
        if self.ir_emitter is not None:
            self.ir_emitter.duty_u16(0)
