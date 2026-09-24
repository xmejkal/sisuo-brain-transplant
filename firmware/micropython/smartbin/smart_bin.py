"""
The running bin: the tasks, and the messages between the hardware and the lid.

For how the whole thing fits together, read `smartbin/__init__.py` first — this file is one
chapter of it.

Three tasks, each doing one thing and firing triggers at the lid's state machine:
  * the sensor poll   -> HAND_DETECTED, or SENSOR_FAILED when a sensor has really gone
  * the button poll   -> OPEN_PRESSED, and the MODE button cycles sound profiles
  * the fault blinker -> visible evidence that the bin needs a human

None of them contains lid logic; what a trigger *means* is decided by the table in states.py.
Composition happens in assembly.py, so adding a listener never means editing this file.
"""

from . import board, events, log, proximity, states
from .timing import async_sleep_ms
from .lid import Lid

try:
    import asyncio
except ImportError:
    import uasyncio as asyncio


class SmartBin:
    """The assembled bin. `build()` constructs one; it starts nothing by itself."""

    def __init__(self, hardware, config, bus, sensor, close_detector, power_policy,
                 listeners=(), save_setting=None):
        self.hardware = hardware
        self.config = config
        self.bus = bus
        self.sensor = sensor
        self.close_detector = close_detector
        self.power_policy = power_policy
        self.lid = Lid(hardware.motor, close_detector, config, bus)

        self.listeners = list(listeners)
        for listener in self.listeners:
            bus.subscribe(listener)

        # Persistence is injected so the bin is not tied to a particular storage mechanism, and
        # so tests can watch what it would have saved.
        self._save_setting = save_setting or (lambda values: False)

    # ----------------------------------------------------------------- tasks
    async def poll_sensor(self):
        """Ask the sensor for a decision, and turn a sensor that has really died into a fault."""
        while True:
            try:
                if self.sensor.hand_detected():
                    self.lid.fire(states.HAND_DETECTED)
            except proximity.SensorFailure as failure:
                self._report_sensor_failure(failure)
                return
            except Exception as exception:  # noqa: BLE001 - a task dying silently is worse
                self._report_sensor_failure(exception)
                return
            await async_sleep_ms(self.config.SENSOR_POLL_MS)

    def _report_sensor_failure(self, reason):
        """
        FAULT is latched, so the bin shows red and waits for a button rather than pretending to
        watch. Pressing OPEN clears the fault and `restart_sensor_polling()` starts this task
        again — recovery is deliberate, not automatic, because a flapping sensor should be seen.
        """
        log.error("sensor failed: %s", reason)
        self.bus.emit(events.SENSOR_FAILED, reason=str(reason))
        self.lid.fire(states.SENSOR_FAILED)

    async def poll_buttons(self):
        """
        The buttons are the only way out of FAULT, so this task must outlive anything it touches:
        a listener that raises while announcing a mode change would otherwise take the bin's last
        recovery path with it.
        """
        while True:
            try:
                self._poll_buttons_once()
            except Exception as exception:  # noqa: BLE001 - see docstring
                log.error("button handling failed: %s", exception)
            await async_sleep_ms(self.config.BUTTON_POLL_MS)

    def _poll_buttons_once(self):
        """One look at both buttons. OPEN also clears a fault, which is what restarts sensing."""
        if self.hardware.button_open.pressed_edge():
            was_faulted = self.lid.state == states.FAULT
            self.lid.fire(states.OPEN_PRESSED)
            if was_faulted:
                self.restart_sensor_polling()

        if self.hardware.button_mode.pressed_edge():
            self.next_sound_profile()

    async def blink_fault(self):
        """The one piece of feedback with its own clock, so it is a task rather than a listener."""
        while True:
            if self.lid.state == states.FAULT:
                self.hardware.led.toggle()
                await async_sleep_ms(self.config.FAULT_BLINK_MS)
            else:
                await async_sleep_ms(self.config.FAULT_IDLE_POLL_MS)

    # ----------------------------------------------------------------- behaviour
    def next_sound_profile(self):
        """Cycle the MODE button's sound profile and remember the choice for next boot."""
        audio_feedback = self.audio
        if audio_feedback is None:
            return None
        name = audio_feedback.next_profile()
        self.bus.emit(events.MODE_CHANGED, profile=name)
        self._save_setting({"ACTIVE_PROFILE": name})
        return name

    @property
    def audio(self):
        """The audio listener, if one is fitted — the MODE button and the REPL both want it."""
        for listener in self.listeners:
            if hasattr(listener, "next_profile"):
                return listener
        return None

    def restart_sensor_polling(self):
        """
        Start the sensor task again after a fault has been cleared.

        The new task replaces the old one in `self._tasks` as well, so shutdown still cancels
        everything it started — a restarted task that nothing tracks would outlive `main()`.
        """
        if self._sensor_task is not None:
            self._sensor_task.cancel()
            if self._sensor_task in self._tasks:
                self._tasks.remove(self._sensor_task)

        log.info("restarting sensor polling")
        self._sensor_task = asyncio.create_task(self.poll_sensor())
        self._tasks.append(self._sensor_task)

    def sleep_now(self):
        """Bench helper: sleep immediately, to measure idle current without waiting."""
        return self.power_policy.sleep_now(self)

    # ----------------------------------------------------------------- lifecycle
    _sensor_task = None
    _tasks: list = []

    async def _start_audio(self):
        """Power the MP3 rail, wait for the module to boot, then configure it."""
        await self.hardware.power_up_audio()
        self.hardware.player.initialize()

    async def main(self):
        """Run the bin. Returns only on cancellation; everything is left safe on the way out."""
        # Audio comes up in the background. The MP3 rail is switched now, and the module boots
        # from cold every time it returns — a few hundred milliseconds during which it cannot be
        # talked to. Awaiting that here would hold the whole bin closed while a speaker warms up,
        # which is the wrong trade: a lid that opens late is worse than a chirp that plays late.
        asyncio.create_task(self._start_audio())
        log.info(
            "smartbin ready: sensor=%s close=%s power=%s",
            self.config.SENSOR_STRATEGY,
            self.config.CLOSE_DETECTOR,
            self.power_policy.name,
        )

        # If this boot is a wake from deep sleep rather than a power-on, act on whatever woke us
        # straight away: the hand that woke the bin should not have to wave twice.
        wake_trigger = self.power_policy.trigger_for_wake(self)
        if wake_trigger is not None:
            self.lid.fire(wake_trigger)

        self._start_tasks()
        try:
            await self._run_idle_loop()
        finally:
            for task in self._tasks:
                if task is not None:
                    task.cancel()
            self.hardware.enter_safe_state()

    def _start_tasks(self):
        self._sensor_task = asyncio.create_task(self.poll_sensor())
        self._tasks = [
            self._sensor_task,
            asyncio.create_task(self.poll_buttons()),
            asyncio.create_task(self.blink_fault()),
        ]
        repl_task = self._start_repl()
        if repl_task is not None:
            self._tasks.append(repl_task)
        return self._tasks

    async def _run_idle_loop(self):
        """
        Keeps `main()` alive, feeds the watchdog, and lets the power policy have its say — which
        is where a battery-powered bin decides to deep-sleep and never returns from.

        The watchdog is started here rather than in `build()` on purpose: it cannot be stopped
        once started, so one created at construction time would reset the board while you were
        thinking at the REPL.
        """
        watchdog = None
        if self.config.WATCHDOG_MS:
            watchdog = board.start_watchdog(self.config.WATCHDOG_MS)

        while True:
            if watchdog is not None:
                watchdog.feed()
            await self.power_policy.tick_while_idle(self)

    def _start_repl(self):
        """
        The live REPL, if `aiorepl` is installed (`mpremote mip install aiorepl`).

        The namespace is built explicitly rather than passing `globals()`, which would hand the
        REPL this module's imports instead of the bin, and leave `b` undefined.
        """
        try:
            import aiorepl
        except ImportError:
            log.warn("aiorepl not installed; no live REPL (mpremote mip install aiorepl)")
            return None
        namespace = {"b": self, "bin": self, "lid": self.lid, "hardware": self.hardware,
                     "config": self.config, "states": states, "states": states}
        log.info("live REPL available; the bin is `b`")
        return asyncio.create_task(aiorepl.task(namespace))
