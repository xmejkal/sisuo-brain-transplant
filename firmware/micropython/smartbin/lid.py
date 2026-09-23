"""
The lid: the state machine's hooks, and the motion that runs between transitions.

The split that keeps this honest — the state machine decides *what* state we are in, and the
coroutines here only drive the motor and report what happened (`STROKE_DONE`, `CAP_TRIPPED`,
`CLOSED_CONFIRMED`). No motion decides where to go next; the table in states.py does.

The safety cap lives here, inside the motion loop, and is checked before anything else. It is not
a policy a detector can override: whatever the sensors say, the motor stops after
`MOTOR_MAX_RUN_MS`. The `finally` stops it again if the task is cancelled or raises.
"""

from . import compat, fsm, log, states
from .compat import async_sleep_ms


class Lid:
    """
    Owns the lid's state machine, the motor and the close detector.

    `clock`, `spawn` and `sleep` are injected so the tests can run the real state machine with no
    event loop and no waiting: a clock that jumps, a task runner that steps by hand, and a sleep
    that yields once. On the device they default to asyncio and real ticks.
    """

    def __init__(self, motor, close_detector, config, bus, clock=None, spawn=None, sleep=None):
        self._motor = motor
        self._close_detector = close_detector
        self._config = config
        self._clock = clock or compat.Clock()
        self._spawn = spawn or compat.asyncio.create_task
        self._sleep = sleep or async_sleep_ms
        self._motion_task = None
        self._hold_task = None
        self._retries = 0

        self.machine = fsm.StateMachine(
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
    def retries(self):
        return self._retries

    def fire(self, trigger, **data):
        """Drive the machine by hand — how you test behaviour with no sensor connected."""
        return self.machine.fire(trigger, **data)

    # ----------------------------------------------------------------- hooks
    def _register_hooks(self):
        self.machine.on_enter(states.IDLE, self._enter_idle)
        self.machine.on_enter(states.OPENING, self._enter_opening)
        self.machine.on_enter(states.OPEN, self._enter_open)
        self.machine.on_exit(states.OPEN, self._cancel_hold)
        self.machine.on_enter(states.CLOSING, self._enter_closing)
        self.machine.on_enter(states.OBSTRUCTED, self._enter_obstructed)
        self.machine.on_enter(states.FAULT, self._enter_fault)
        for state in states.MOVING_STATES:
            self.machine.on_exit(state, self._cancel_motion)

    def _enter_idle(self):
        self._retries = 0
        self._motor.stop()

    def _enter_opening(self):
        self._start_motion(open_direction=True, run_ms=self._config.LID_OPEN_RUN_MS)

    def _enter_open(self):
        self._motor.stop()
        self._cancel_hold()
        self._hold_task = self._spawn(self._hold())

    def _enter_closing(self):
        self._close_detector.start()
        self._start_motion(
            open_direction=False,
            run_ms=self._config.LID_CLOSE_RUN_MS,
            detector=self._close_detector,
        )

    def _enter_obstructed(self):
        self._retries += 1
        if self._retries > self._config.MAX_CLOSE_RETRIES:
            log.warn("lid: %d close attempts failed; faulting", self._retries)
            # Queued by the machine: we are inside a transition right now.
            self.machine.fire(states.RETRY_EXHAUSTED)
            return
        log.info("lid: obstructed, reopening (attempt %d)", self._retries)
        self._start_motion(open_direction=True, run_ms=self._config.LID_OPEN_RUN_MS)

    def _enter_fault(self):
        self._cancel_motion()
        self._motor.stop()

    # ----------------------------------------------------------------- motion
    def _start_motion(self, open_direction, run_ms, detector=None):
        self._cancel_motion()
        self._motion_task = self._spawn(self._stroke(open_direction, run_ms, detector))

    def _cancel_motion(self):
        """
        Stop the motor first, then cancel the task.

        Order matters: cancelling only takes effect when the task is next scheduled, so stopping
        the motor here is what makes "the lid stops now" true now.
        """
        self._motor.stop()
        if self._motion_task is not None:
            self._motion_task.cancel()
            self._motion_task = None

    def _cancel_hold(self):
        if self._hold_task is not None:
            self._hold_task.cancel()
            self._hold_task = None

    async def _stroke(self, open_direction, run_ms, detector=None):
        """
        One motor run. Reports how it ended and never decides what happens next.

        The cap is checked before the detector and before the calibrated time, so a detector that
        never fires, or a run time calibrated too long, still cannot burn the motor.
        """
        started = self._clock.now_ms()
        self._motor.drive(open_direction, self._speed(open_direction))
        try:
            while True:
                elapsed = self._clock.elapsed_ms(started)

                if elapsed >= self._config.MOTOR_MAX_RUN_MS:
                    log.warn("lid: safety cap at %d ms", elapsed)
                    self.machine.fire(states.CAP_TRIPPED, elapsed_ms=elapsed)
                    return

                if detector is not None and detector.closed(elapsed):
                    self.machine.fire(states.CLOSED_CONFIRMED, elapsed_ms=elapsed)
                    return

                if elapsed >= run_ms:
                    self.machine.fire(states.STROKE_DONE, elapsed_ms=elapsed)
                    return

                await self._sleep(self._config.MOTION_POLL_MS)
        finally:
            self._motor.stop()

    async def _hold(self):
        await self._sleep(self._config.LID_OPEN_HOLD_MS)
        self.machine.fire(states.HOLD_EXPIRED)

    def _speed(self, open_direction):
        return (
            self._config.MOTOR_OPEN_SPEED if open_direction else self._config.MOTOR_CLOSE_SPEED
        )
