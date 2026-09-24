"""
Every device the bin can command or read, constructed in one place.

THE RULE, because it was not obvious before: **hardware owns devices, not decisions.**

    a device      knows how to talk to a physical thing: the motor driver, the LED, a button,
                  the MP3 module, the rangefinder chip. It has no opinion about the lid.
    a strategy    makes a decision using devices: "is that a hand?", "is the lid shut?",
                  "should we sleep?" Those live in proximity.py, close_detection.py and power.py, and are
                  assembled in assembly.py.

So the rangefinder *chip* is here next to the motor, while "is a hand there?" is not — that is a
judgement, and which judgement you want is a config choice.

With board.py this is the only module that touches `machine`, which is what lets everything
else be tested on a PC. Constructing it moves nothing: pins go to their resting state, no more.

Pin numbers here are raw GPIO numbers. The silkscreen label each one corresponds to is a
fact about the board and lives in boards/<id>.json, reaching this code through board_spec.py;
config.py says which GPIO carries which function.
"""

from machine import ADC, I2C, PWM, Pin, UART

from . import audio, buttons, log, motor, status_led, timing


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
        #
        # The MP3 rail's switch comes first because building the player powers the module, and
        # the P-channel gate is ACTIVE LOW: `value=1` at construction is OFF, which is the state
        # the gate resistor already holds through reset. Constructing this changes nothing.
        self.mp3_power = Pin(config.PIN_MP3_ENABLE, Pin.OUT, value=1)
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
        button_open = buttons.Button(
            Pin(config.PIN_BUTTON_OPEN, Pin.IN, Pin.PULL_UP), config.BUTTON_DEBOUNCE_MS
        )
        button_mode = buttons.Button(
            Pin(config.PIN_BUTTON_MODE, Pin.IN, Pin.PULL_UP), config.BUTTON_DEBOUNCE_MS
        )
        led = status_led.StatusLed(
            Pin(config.PIN_LED_RED, Pin.OUT, value=0),
            Pin(config.PIN_LED_GREEN, Pin.OUT, value=0),
        )
        return button_open, button_mode, led

    def _build_player(self, config):
        """
        The MP3 module, or silence.

        A bin that cannot make a noise still empties itself, so nothing here is allowed to stop
        the firmware starting. `rx=-1` should mean "leave the receive pin alone" on this port,
        but it is unverified on hardware, and a ValueError at this point would take the whole bin
        down over a speaker.
        """
        if not config.AUDIO_ENABLED:
            return audio.SilentPlayer()

        try:
            uart = self._open_mp3_uart(config)
        except Exception as exception:  # noqa: BLE001 - see docstring
            log.error("no MP3 module (%s); the bin will run silently", exception)
            return audio.SilentPlayer()

        return audio.Dfr0534Player(uart, config.VOLUME)

    def _open_mp3_uart(self, config):
        """Transmit only: the module's TXD is deliberately unwired (see audio.Dfr0534Player)."""
        try:
            return UART(config.MP3_UART_ID, baudrate=config.MP3_BAUD, tx=config.PIN_MP3_TX, rx=-1)
        except (ValueError, TypeError):
            # Some ports will not accept -1 for "no pin". Fall back to letting the port pick its
            # own receive pin: we never read it, and an unused input is harmless.
            log.warn("this port rejects rx=-1; opening the MP3 UART with its default receive pin")
            return UART(config.MP3_UART_ID, baudrate=config.MP3_BAUD, tx=config.PIN_MP3_TX)

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
            # 0 dB (~0-0.95 V), not 11 dB (~0-3.1 V). The board's shunt is 0.1 ohm, so even a
            # 2 A stall develops only 200 mV — the signal cannot reach the rail, and putting it
            # against a 0.95 V span instead of a 3.1 V one recovers more than three times the
            # counts. The ESP32's ADC is also at its worst in the bottom tenth of its range,
            # which is exactly where the old combination put both the running and stall points.
            self.current_sense.atten(ADC.ATTN_0DB)
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
        """Motor stopped, LED dark, IR emitter off, MP3 rail cut. Before sleep, and by hand."""
        self.motor.stop()
        self.led.set(status_led.OFF)
        if self.ir_emitter is not None:
            self.ir_emitter.duty_u16(0)
        self.set_mp3_power(False)

    async def power_up_audio(self):
        """
        Bring the MP3 module's rail up and give it time to boot, before its first frame.

        Separate from construction on purpose. `Hardware(...)` is required to move nothing — it
        puts pins in their resting state and stops — and powering a module and then blocking for
        its boot is both of the things that rule forbids. It is also asynchronous rather than a
        blocking sleep, so the bin is answering buttons while the module wakes up.
        """
        if self.mp3_power is None:
            return
        self.set_mp3_power(True)
        await timing.async_sleep_ms(self.config.MP3_POWER_ON_MS)

    def set_mp3_power(self, on):
        """
        Switch the MP3 module's rail.

        The DFR0534 has no enable pin and its idle draw has never been measured; its class idles
        around 15-25 mA, which would be roughly forty times everything else on this board put
        together. Rather than wait for that measurement, the board carries a high-side switch and
        this cuts the rail whenever the bin sleeps — so the answer changes how much is saved, not
        whether the design works.

        The switch is P-channel on the high side, so the GPIO is ACTIVE LOW.
        """
        if self.mp3_power is None:
            return
        self.mp3_power.value(0 if on else 1)
