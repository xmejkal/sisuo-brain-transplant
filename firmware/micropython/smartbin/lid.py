"""
The lid: the state machine's hooks, and the motion that runs between transitions.

The split that keeps this honest — the state machine decides *what* state we are in, and the
coroutines here only drive the motor and report what happened (`STROKE_FINISHED`,
`SAFETY_CAP_TRIPPED`, `CLOSE_CONFIRMED`). No motion decides where to go next; the table in
states.py does.

The safety cap lives here, inside the motion loop, and is checked before anything else. It is not
a policy a detector can override: whatever the sensors say, the motor stops after
`MOTOR_MAX_RUN_MS`. The `finally` stops it again if the stroke is cancelled or raises.
"""

from . import log, states, timing
from .state_machine import StateMachine
from .timing import async_sleep_ms


class Lid:
    """
    Owns the lid's state machine, the motor and the close detector.

    `clock`, `spawn` and `sleep` are injected so the tests can run the real state machine with no
    event loop and no waiting: a clock that jumps, a task runner stepped by hand, and a sleep
    that yields. On the device they default to asyncio and real ticks.
    """

    def __init__(self, motor, close_detector, config, bus, clock=None, spawn=None, sleep=None):
        self._motor = motor
        self._close_detector = close_detector
        self._config = config
        self._clock = clock or timing.Clock()
        self._spawn = spawn or timing.asyncio.create_task
        self._sleep = sleep or async_sleep_ms
        self._motion_task = None
        self._hold_task = None
        self._failed_close_attempts = 0

        self.machine = StateMachine(
            states.TRANSITIONS, states.IDLE, bus=bus, clock=self._clock, name="lid"
        )
        self._register_hooks()

    # ----------------------------------------------------------------- inspection (REPL)
    @property
    def state(self):
        return self.machine.state

    @property
    def history(self):
        return self.machine.history

    @property
    def failed_close_attempts(self):
        """How many times the current close has been obstructed; reset by reaching IDLE."""
        return self._failed_close_attempts

    def fire(self, trigger, **event_data):
        """Drive the machine by hand — how you test behaviour with no sensor connected."""
        return self.machine.fire(trigger, **event_data)

    # ----------------------------------------------------------------- hooks
    def _register_hooks(self):
        self.machine.on_enter(states.IDLE, self._on_idle)
        self.machine.on_enter(states.OPENING, self._on_opening)
        self.machine.on_enter(states.OPEN, self._on_open)
        self.machine.on_exit(states.OPEN, self._cancel_hold_timer)
        self.machine.on_enter(states.CLOSING, self._on_closing)
        self.machine.on_enter(states.OBSTRUCTED, self._on_obstructed)
        self.machine.on_enter(states.FAULT, self._on_fault)
        for state in states.STATES_WITH_MOTION:
            self.machine.on_exit(state, self._cancel_stroke)

    def _on_idle(self):
        self._failed_close_attempts = 0
        self._motor.stop()

    def _on_opening(self):
        self._start_stroke(opening=True, run_ms=self._config.LID_OPEN_RUN_MS)

    def _on_open(self):
        self._motor.stop()
        self._cancel_hold_timer()
        self._hold_task = self._spawn(self._hold_then_close())

    def _on_closing(self):
        self._close_detector.start()
        self._start_stroke(
            opening=False,
            run_ms=self._config.LID_CLOSE_RUN_MS,
            close_detector=self._close_detector,
        )

    def _on_obstructed(self):
        self._failed_close_attempts += 1
        if self._failed_close_attempts > self._config.MAX_CLOSE_RETRIES:
            log.warn("lid: %d close attempts failed; faulting", self._failed_close_attempts)
            # Queued by the machine, because we are inside a transition right now.
            self.machine.fire(states.RETRY_LIMIT_REACHED)
            return
        log.info("lid: obstructed, reopening (attempt %d)", self._failed_close_attempts)
        self._start_stroke(opening=True, run_ms=self._config.LID_OPEN_RUN_MS)

    def _on_fault(self):
        self._cancel_stroke()
        self._motor.stop()

    # ----------------------------------------------------------------- motion
    def _start_stroke(self, opening, run_ms, close_detector=None):
        self._cancel_stroke()
        self._motion_task = self._spawn(self._stroke(opening, run_ms, close_detector))

    def _cancel_stroke(self):
        """
        Stop the motor now, then cancel the stroke task.

        Order matters twice over. Stopping first is what makes "the lid stops now" true now,
        because cancellation only takes effect when the task is next scheduled. And the handle is
        cleared *before* cancelling because a stroke usually cancels **itself**: it fires the
        trigger that transitions the lid away, and this runs as the exit hook of that transition.
        MicroPython raises `RuntimeError("can't cancel self")` in that case, and the stroke is
        returning anyway — its `finally` stops the motor a second time.
        """
        self._motor.stop()
        self._motion_task = _cancel_safely(self._motion_task)

    def _cancel_hold_timer(self):
        """The same self-cancellation case: the hold timer is what fires HOLD_EXPIRED."""
        self._hold_task = _cancel_safely(self._hold_task)

    async def _stroke(self, opening, run_ms, close_detector=None):
        """
        One motor run. Reports how it ended and never decides what happens next.

        The cap is checked before the detector and before the calibrated time, so a detector that
        never fires, or a run time calibrated too long, still cannot burn the motor.
        """
        started_at = self._clock.now_ms()
        self._motor.drive(opening, self._speed_for(opening))
        try:
            while True:
                elapsed_ms = self._clock.elapsed_ms(started_at)

                if elapsed_ms >= self._config.MOTOR_MAX_RUN_MS:
                    log.warn("lid: safety cap at %d ms", elapsed_ms)
                    self.machine.fire(states.SAFETY_CAP_TRIPPED, elapsed_ms=elapsed_ms)
                    return

                if close_detector is not None and close_detector.is_closed(elapsed_ms):
                    self.machine.fire(states.CLOSE_CONFIRMED, elapsed_ms=elapsed_ms)
                    return

                if elapsed_ms >= run_ms:
                    self.machine.fire(states.STROKE_FINISHED, elapsed_ms=elapsed_ms)
                    return

                await self._sleep(self._config.MOTION_POLL_MS)
        finally:
            self._motor.stop()

    async def _hold_then_close(self):
        await self._sleep(self._config.LID_OPEN_HOLD_MS)
        self.machine.fire(states.HOLD_EXPIRED)

    def _speed_for(self, opening):
        return self._config.MOTOR_OPEN_SPEED if opening else self._config.MOTOR_CLOSE_SPEED


def _cancel_safely(task):
    """
    Cancel `task` unless it is the one running right now, and return None to store back.
    Self-cancellation is normal here rather than an error — see `Lid._cancel_stroke`.
    """
    if task is None:
        return None
    try:
        task.cancel()
    except RuntimeError:
        log.debug("lid: task is cancelling itself; letting it return")
    return None
