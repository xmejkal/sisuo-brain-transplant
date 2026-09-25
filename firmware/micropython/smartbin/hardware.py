"""
Every device the bin can command or read, constructed in one place.

THE RULE, because it was not obvious before: **hardware owns devices, not decisions.**

    a device      knows how to talk to a physical thing: the motor driver, the LED, a button,
                  the amplifier, the rangefinder chip. It has no opinion about the lid.
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

from machine import ADC, I2C, I2S, PWM, Pin, UART

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
        # The amplifier's shutdown line comes first because building the player will drive it,
        # and `value=0` at construction is OFF — 0.6 uA. It is an output from the first
        # instruction so it is never left floating, which the module reads as "pick a channel"
        # rather than "be quiet".
        self.audio_shutdown = Pin(config.PIN_AUDIO_SD, Pin.OUT, value=0)
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
        """
        The two buttons are wired in OPPOSITE directions, on purpose.

        OPEN is a deep-sleep wake source, and every armed wake pin shares one trigger level, so
        it goes to 3V3 behind a pull-down and reads 1 when pressed. MODE cannot wake this chip
        (GPIO47 is outside the RTC range) and needs no external part, so it keeps the cheaper
        arrangement: to ground, through the internal pull-up, reading 0 when pressed.

        `WAKE_ON_HIGH` is the single statement of that direction, and the board follows it —
        which is why this reads it rather than hard-coding either level.
        """
        pressed_high = 1 if config.WAKE_ON_HIGH else 0
        button_open = buttons.Button(
            Pin(config.PIN_BUTTON_OPEN, Pin.IN,
                Pin.PULL_DOWN if config.WAKE_ON_HIGH else Pin.PULL_UP),
            config.BUTTON_DEBOUNCE_MS, pressed_level=pressed_high
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
        The audio hardware named by `config.AUDIO_STRATEGY`, or silence.

        A bin that cannot make a noise still empties itself, so nothing here is allowed to stop
        the firmware starting: a peripheral that will not open — a pin already claimed, a port
        built without I2S, a UART id this chip does not have — costs a chirp and not the lid.

        The two strategies want DIFFERENT BOARDS, which is why each builder asks for the pins it
        needs rather than assuming they exist. Selecting `dfr0534` on the v4 design would
        otherwise send frames into a pin carrying the amplifier's shutdown line: no error, no
        sound, and a shutdown pin being driven with serial data.
        """
        if not config.AUDIO_ENABLED:
            return audio.SilentPlayer()

        strategy = getattr(config, "AUDIO_STRATEGY", "i2s")
        builder = {"i2s": self._build_i2s_player, "dfr0534": self._build_dfr0534_player}.get(strategy)
        if builder is None:
            log.error("unknown AUDIO_STRATEGY %r; the bin will run silently", strategy)
            return audio.SilentPlayer()

        try:
            return builder(config)
        except Exception as exception:  # noqa: BLE001 - see docstring
            log.error("no %s audio (%s); the bin will run silently", strategy, exception)
            return audio.SilentPlayer()

    def _build_i2s_player(self, config):
        return audio.I2sTonePlayer(self._open_i2s(config), self.audio_shutdown, config.VOLUME)

    def _build_dfr0534_player(self, config):
        """
        The v3 board's UART module.

        `PIN_MP3_TX` does not exist in a v4 configuration, and that absence is the check: the
        pin map IS the statement of which board is fitted, so asking it is more honest than a
        second flag that could disagree with it.
        """
        transmit = getattr(config, "PIN_MP3_TX", None)
        if transmit is None:
            raise ValueError(
                "AUDIO_STRATEGY is 'dfr0534' but this configuration has no PIN_MP3_TX. That "
                "module needs the v3 board (board-v3-dfr0534.tsx); the current pin map gives "
                "D3 to the I2S amplifier's shutdown line")
        return audio.Dfr0534Player(
            UART(config.MP3_UART_ID, baudrate=config.MP3_BAUD, tx=transmit, rx=-1),
            config.VOLUME)

    def _open_i2s(self, config):
        """
        Transmit-only mono I2S at the tone generator's own rate.

        `ibuf` is the driver's ring buffer. It has to hold more than one write's worth or the
        write blocks the event loop waiting for the peripheral to drain, which is the whole
        reason cues are rendered in a task: 4 KB covers the longest cue in the table.
        """
        return I2S(
            config.I2S_ID,
            sck=Pin(config.PIN_I2S_BCLK),
            ws=Pin(config.PIN_I2S_LRC),
            sd=Pin(config.PIN_I2S_DIN),
            mode=I2S.TX,
            bits=16,
            format=I2S.MONO,
            rate=audio.TONE_RATE_HZ,
            ibuf=config.I2S_BUFFER_BYTES,
        )

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
        """Motor stopped, LED dark, IR emitter off, amplifier shut down. Before sleep, and by hand."""
        self.motor.stop()
        self.led.set(status_led.OFF)
        if self.ir_emitter is not None:
            self.ir_emitter.duty_u16(0)
        self.silence_audio()

    def silence_audio(self):
        """
        Shut the amplifier down: 0.6 uA, not the 340 uA of a clock-stopped standby.

        WHAT THIS REPLACED, and why the replacement is smaller. There used to be an async
        `power_up_audio()` that switched a P-channel FET feeding the MP3 module and then waited
        400 ms for it to boot, plus a `set_mp3_power()` to cut that rail before sleep. The
        DFR0534 had no enable pin and an idle draw nobody had measured, so the board carried a
        high-side switch to make the unmeasured number not matter.

        The MAX98357A has a shutdown pin, so the rail, the switch, the gate resistor, the
        reservoir capacitor and the boot delay all go away, and what is left is one line. The
        amplifier has no firmware to boot, so there is nothing to wait for and nothing to
        sequence — which is why `smart_bin` no longer awaits anything before its first cue.
        """
        self.audio_shutdown.value(0)
