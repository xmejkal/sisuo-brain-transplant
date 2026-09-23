"""
Test doubles, so the lid's behaviour can be tested on a Mac with no hardware and no waiting.

The seam is `Lid(motor, close_detector, config, bus, clock, spawn)`: every collaborator is
injected, so the same state machine that runs on the bin runs here against a fake motor and a
clock that jumps.
"""

import sys
from os import path

sys.path.insert(0, path.dirname(path.dirname(path.abspath(__file__))))


class FakeClock:
    """A clock that only moves when the test says so."""

    def __init__(self):
        self.millis = 0

    def now_ms(self):
        return self.millis

    def elapsed_ms(self, since):
        return self.millis - since

    def advance(self, milliseconds):
        self.millis += milliseconds


class FakeMotor:
    """Records what it was asked to do, and how long it was actually running."""

    def __init__(self, clock):
        self._clock = clock
        self.calls = []
        self.running_since = None
        self.longest_run_ms = 0

    @property
    def is_running(self):
        return self.running_since is not None

    def drive(self, open_direction, speed):
        self.calls.append(("drive", open_direction, speed))
        if self.running_since is None:
            self.running_since = self._clock.now_ms()

    def stop(self):
        self.calls.append(("stop",))
        self._note_run()

    def brake(self):
        self.calls.append(("brake",))
        self._note_run()

    def _note_run(self):
        if self.running_since is not None:
            run = self._clock.now_ms() - self.running_since
            self.longest_run_ms = max(self.longest_run_ms, run)
            self.running_since = None


class StepRunner:
    """
    Stands in for asyncio: collects the coroutines the lid spawns, and `step()` advances the
    clock and lets them run, so a whole open/hold/close cycle takes microseconds.
    """

    def __init__(self, clock):
        self._clock = clock
        self._tasks = []

    def sleep(self, milliseconds):
        """
        The awaitable the lid gets instead of asyncio.sleep. It suspends until the *fake* clock
        has advanced far enough, so a 4 second hold really does take 4 simulated seconds — just
        no real ones.
        """
        return _SleepUntil(self._clock, milliseconds)

    def spawn(self, coroutine):
        task = _Task(coroutine)
        self._tasks.append(task)
        task.step()  # run up to the first await, as create_task effectively does
        return task

    def step(self, milliseconds=10):
        """Advance time, then let every live task run to its next await."""
        self._clock.advance(milliseconds)
        for task in list(self._tasks):
            if task.done or task.cancelled:
                self._tasks.remove(task)
            else:
                task.step()

    def run(self, steps=200, milliseconds=10):
        for _ in range(steps):
            self.step(milliseconds)


class _SleepUntil:
    """Suspends a coroutine until the fake clock passes a deadline."""

    def __init__(self, clock, milliseconds):
        self._clock = clock
        self._deadline = clock.now_ms() + milliseconds

    def __await__(self):
        while self._clock.now_ms() < self._deadline:
            yield


class _Task:
    """The minimum of a task: it can be stepped, and it can be cancelled."""

    def __init__(self, coroutine):
        self._coroutine = coroutine
        self.done = False
        self.cancelled = False

    def step(self):
        if self.done or self.cancelled:
            return
        try:
            self._coroutine.send(None)
        except StopIteration:
            self.done = True

    def cancel(self):
        """
        Mirror asyncio: cancelling a task that is *currently running* (a stroke cancels itself
        when it fires the trigger that transitions away) does not tear it down underneath itself.
        Real asyncio defers to the next await; here the coroutine is about to return anyway, and
        its `finally` — the one that stops the motor — runs as it does.
        """
        if self.done or self.cancelled:
            return
        self.cancelled = True
        try:
            self._coroutine.close()
        except ValueError:
            pass  # "coroutine already executing": it will unwind on its own


class FakeConfig:
    """Only what Lid reads. Tests override single attributes as needed."""

    LID_OPEN_RUN_MS = 900
    LID_CLOSE_RUN_MS = 950
    LID_OPEN_HOLD_MS = 4000
    MOTOR_MAX_RUN_MS = 1500
    MOTOR_OPEN_SPEED = 220
    MOTOR_CLOSE_SPEED = 200
    MAX_CLOSE_RETRIES = 3
    MOTION_POLL_MS = 10


class RecordingListener:
    """Collects every event the bus publishes, for asserting on what the bin announced."""

    def __init__(self):
        self.events = []

    def __call__(self, event, **data):
        self.events.append(event)
