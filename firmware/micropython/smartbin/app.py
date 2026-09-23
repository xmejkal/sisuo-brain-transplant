"""
SmartBin: wires the parts together and runs the tasks.

Three tasks, each doing one thing and firing triggers at the lid's state machine:
  * the sensor poll   -> HAND_DETECTED, or SENSOR_FAILED when a sensor keeps failing
  * the button poll   -> OPEN_PRESSED, and the MODE button cycles sound profiles
  * the fault blinker -> visible feedback that the bin needs attention

None of them contains any lid logic; what a trigger means is decided by the table in states.py.
"""

try:
    import asyncio
except ImportError:
    import uasyncio as asyncio

from . import events, feedback, lid as lid_module, log, power, sensors, states, ui


class SmartBin:
    """The assembled bin. `build()` in __init__.py constructs one; it starts nothing by itself."""

    def __init__(self, hw, config, bus, sensor, close_detector, power_policy=None):
        self.hw = hw
        self.config = config
        self.bus = bus
        self.sensor = sensor
        self.close_detector = close_detector
        self.power = power_policy or power.AlwaysOnPolicy()
        self.lid = lid_module.Lid(hw.motor, close_detector, config, bus)

        self.audio = feedback.AudioFeedback(
            hw.player, config.SOUND_PROFILES, config.ACTIVE_PROFILE, config.VOLUME
        )
        self.leds = feedback.LedFeedback(hw.led, feedback.DEFAULT_LED_COLOURS)
        bus.subscribe(self.audio)
        bus.subscribe(self.leds)
        if config.LOG_EVENTS:
            bus.subscribe(feedback.LogFeedback())

    # ----------------------------------------------------------------- tasks
    async def poll_sensor(self):
        while True:
            try:
                if self.sensor.detected():
                    self.lid.fire(states.HAND_DETECTED)
            except sensors.SensorFailure as failure:
                log.error("sensor failed: %s", failure)
                self.bus.emit(events.SENSOR_FAILED, reason=str(failure))
                self.lid.fire(states.SENSOR_FAILED)
                return
            await asyncio.sleep_ms(self.config.SENSOR_POLL_MS)

    async def poll_buttons(self):
        while True:
            if self.hw.button_open.pressed_edge():
                self.lid.fire(states.OPEN_PRESSED)
            if self.hw.button_mode.pressed_edge():
                self._next_sound_profile()
            await asyncio.sleep_ms(self.config.BUTTON_POLL_MS)

    async def blink_fault(self):
        """The only feedback that needs its own clock, so it is a task rather than a listener."""
        while True:
            if self.lid.state == states.FAULT:
                self.hw.led.toggle()
                await asyncio.sleep_ms(self.config.FAULT_BLINK_MS)
            else:
                await asyncio.sleep_ms(self.config.FAULT_BLINK_MS * 2)

    # ----------------------------------------------------------------- behaviour
    def _next_sound_profile(self):
        name = self.audio.next_profile()
        self.bus.emit(events.MODE_CHANGED, profile=name)
        self.config.save({"ACTIVE_PROFILE": name})

    # ----------------------------------------------------------------- lifecycle
    async def main(self):
        """Start everything. Returns only on cancellation; the motor is stopped on the way out."""
        self.hw.player.begin()
        self.hw.led.set(ui.GREEN)
        log.info(
            "smartbin ready: sensor=%s close=%s power=%s",
            self.config.SENSOR,
            self.config.CLOSE_DETECT,
            self.power.name,
        )

        # If we got here by waking from deep sleep rather than by being switched on, act on what
        # woke us straight away — the hand that woke the bin should not have to wave twice.
        wake_trigger = self.power.prepare(self)
        if wake_trigger is not None:
            self.lid.fire(wake_trigger)

        tasks = [
            asyncio.create_task(self.poll_sensor()),
            asyncio.create_task(self.poll_buttons()),
            asyncio.create_task(self.blink_fault()),
        ]
        if self.config.REPL_ENABLED:
            tasks.append(self._start_repl())

        try:
            await self._idle_loop()
        finally:
            for task in tasks:
                if task is not None:
                    task.cancel()
            self.hw.all_off()

    async def _idle_loop(self):
        """
        Keeps `main()` alive, feeds the watchdog, and lets the power policy have its say — which
        is where the bin may decide to deep-sleep and never return from.

        The WDT is created here rather than in `build()` on purpose: on ESP32 it cannot be
        stopped once started, so a watchdog created at construction time would reset the board
        while you were thinking at the REPL.
        """
        watchdog = None
        if self.config.WATCHDOG_MS:
            from machine import WDT

            watchdog = WDT(timeout=self.config.WATCHDOG_MS)

        while True:
            if watchdog is not None:
                watchdog.feed()
            await self.power.idle(self)

    def sleep_now(self):
        """Bench helper: deep-sleep immediately, to measure idle current without waiting."""
        if hasattr(self.power, "sleep_now"):
            return self.power.sleep_now(self)
        log.warn("power policy %s does not sleep", self.power.name)
        return None

    def _start_repl(self):
        """
        The live REPL, if `aiorepl` is installed (`mpremote mip install aiorepl`).

        With it you can inspect and drive the bin while it runs:
            >>> b.lid.state
            >>> b.sensor.read()
            >>> b.lid.fire("open_pressed")
        """
        try:
            import aiorepl
        except ImportError:
            log.warn("aiorepl not installed; no live REPL (mpremote mip install aiorepl)")
            return None
        log.info("live REPL available")
        return asyncio.create_task(aiorepl.task(globals()))
