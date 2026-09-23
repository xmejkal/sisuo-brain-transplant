"""
A small, explicit state machine.

Deliberately hand-written rather than pulled from a library: the whole job is a dict lookup,
entry/exit hooks and an event publish, and a dependency would add indirection without removing
work. What it buys over scattered `if` statements:

  * one authoritative `machine.state`, inspectable from the REPL,
  * illegal transitions are refused and logged instead of silently doing something odd,
  * **events cannot be forgotten** — the machine publishes them, not the programmer,
  * `history` for the bench, and a table the tests and the diagram tool read directly.

Re-entrancy: a hook may fire another trigger (the obstruction retry counter does). Those are
queued and applied after the current transition finishes, so the machine is never half-way
through two transitions at once.
"""

from . import events, log


class StateMachine:
    """
    Owns the current state, the legal transitions, and per-state entry/exit hooks.

    `table` maps state -> {trigger: next_state} (see `states.TRANSITIONS`).
    Hooks are plain callables taking no arguments; register them with `on_enter`/`on_exit`.
    """

    HISTORY_LENGTH = 20

    def __init__(self, table, initial, bus=None, clock=None, name="fsm"):
        self._table = table
        self._state = initial
        self._bus = bus or events.EventBus()
        self._clock = clock
        self._name = name
        self._enter_hooks = {}
        self._exit_hooks = {}
        self._queued_triggers = []
        self._dispatching = False
        self.history = []

    # ----------------------------------------------------------------- inspection
    @property
    def state(self):
        return self._state

    @property
    def bus(self):
        return self._bus

    def can_fire(self, trigger):
        """True when `trigger` would cause a transition from the current state."""
        return trigger in self._table.get(self._state, {})

    # ----------------------------------------------------------------- wiring
    def on_enter(self, state, hook):
        """Run `hook()` after entering `state`. One hook per state, by design."""
        self._enter_hooks[state] = hook
        return hook

    def on_exit(self, state, hook):
        """Run `hook()` while leaving `state` — this is where motion tasks get cancelled."""
        self._exit_hooks[state] = hook
        return hook

    # ----------------------------------------------------------------- the machine
    def fire(self, trigger, **event_data):
        """
        Apply `trigger`. Returns True if it caused a transition.

        An unknown trigger for the current state is not an error: the table says it does not
        apply here, which is exactly how "hand waved while already opening" is handled.
        """
        if self._dispatching:
            self._queued_triggers.append((trigger, event_data))
            return False

        self._dispatching = True
        try:
            fired = self._transition(trigger, event_data)
            while self._queued_triggers:
                queued_trigger, queued_data = self._queued_triggers.pop(0)
                self._transition(queued_trigger, queued_data)
            return fired
        finally:
            # A hook that raised must not leave a trigger queued to surprise a later, unrelated
            # transition.
            self._queued_triggers = []
            self._dispatching = False

    def _transition(self, trigger, event_data):
        destination = self._table.get(self._state, {}).get(trigger)
        if destination is None:
            log.debug("%s: %s ignored in %s", self._name, trigger, self._state)
            return False

        previous = self._state
        log.info("%s: %s --%s--> %s", self._name, previous, trigger, destination)

        # The state is set before any hook runs, so that a hook which raises cannot leave the
        # machine claiming to be somewhere it has already left — and so a hook can read the
        # state it is entering.
        self._state = destination
        self._record(previous, trigger, destination)

        self._run_hook(self._exit_hooks.get(previous), "exit", previous)
        self._run_hook(self._enter_hooks.get(destination), "enter", destination)

        self._bus.emit(
            events.state_entered(destination), previous=previous, trigger=trigger, **event_data
        )
        return True

    def _run_hook(self, hook, kind, state):
        """
        Hooks drive hardware, so one raising is possible. The transition still completes: a
        half-applied transition is far more dangerous than a missed hook, because the machine
        would then refuse every trigger the new state expects.
        """
        if hook is None:
            return
        try:
            hook()
        except Exception as exception:  # noqa: BLE001 - see docstring
            log.error("%s: %s hook for %s failed: %s", self._name, kind, state, exception)

    def _record(self, previous, trigger, destination):
        timestamp_ms = self._clock.now_ms() if self._clock is not None else None
        self.history.append((timestamp_ms, previous, trigger, destination))
        if len(self.history) > self.HISTORY_LENGTH:
            self.history.pop(0)

    def force_state(self, state):
        """Set the state with no transition, no hooks, no event. Bench escape hatch only."""
        log.warn("%s: forced %s -> %s", self._name, self._state, state)
        self._state = state
